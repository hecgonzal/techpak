"""Canonical JSON and bounded packet helpers; never implement crypto here."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

import rfc8785

from .errors import PacketError

MAX_PACKET_BYTES = 256 * 1024
MAX_NESTING = 16
MAX_TEXT_LENGTH = 4096


def canonical_bytes(value: Any) -> bytes:
    """Encode JSON data deterministically for signing and hashing."""
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, rfc8785.CanonicalizationError) as error:
        raise PacketError("Value cannot be represented as canonical JSON") from error


def encode_signature(signature: bytes) -> str:
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def decode_signature(value: object) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise PacketError("Signature encoding is invalid")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, binascii.Error) as error:
        raise PacketError("Signature encoding is invalid") from error
    if encode_signature(decoded) != value:
        raise PacketError("Signature encoding is not canonical base64url")
    return decoded


def parse_packet(data: bytes | str) -> dict[str, Any]:
    """Decode one bounded JSON packet and reject ambiguous/invalid JSON."""
    if isinstance(data, bytes):
        if len(data) > MAX_PACKET_BYTES:
            raise PacketError("Packet exceeds the maximum size")
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise PacketError("Packet is not valid UTF-8") from error
    elif isinstance(data, str):
        try:
            encoded = data.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise PacketError("Packet contains invalid Unicode") from error
        if len(encoded) > MAX_PACKET_BYTES:
            raise PacketError("Packet exceeds the maximum size")
        text = data
    else:
        raise PacketError("Packet input must be UTF-8 bytes or text")

    def object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PacketError("Packet contains a duplicate object key")
            result[key] = value
        return result

    def reject_non_json_constant(value: str) -> None:
        raise PacketError(f"Non-JSON numeric constant is not allowed: {value}")

    try:
        packet = json.loads(
            text,
            object_pairs_hook=object_without_duplicates,
            parse_constant=reject_non_json_constant,
        )
    except PacketError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise PacketError("Packet is not valid JSON") from error
    return validate_packet_shape(packet)


def validate_json_value(value: Any, *, depth: int = 0) -> None:
    """Reject values that are unsafe or unbounded for the packet format."""
    if depth > MAX_NESTING:
        raise PacketError("Packet nesting is too deep")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise PacketError("Non-finite numbers are not allowed")
        return
    if isinstance(value, str):
        if len(value) > MAX_TEXT_LENGTH:
            raise PacketError("Text field exceeds the maximum length")
        return
    if isinstance(value, list):
        if len(value) > 4096:
            raise PacketError("List exceeds the maximum item count")
        for item in value:
            validate_json_value(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 4096 or not all(isinstance(key, str) for key in value):
            raise PacketError("Object keys or item count are invalid")
        for key, item in value.items():
            if len(key) > 128:
                raise PacketError("Object key exceeds the maximum length")
            validate_json_value(item, depth=depth + 1)
        return
    raise PacketError(f"Unsupported JSON value type: {type(value).__name__}")


def require_text(value: object, name: str, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise PacketError(f"{name} must be a non-empty string up to {limit} characters")
    return value


def validate_packet_shape(packet: object) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise PacketError("Packet must be a JSON object")
    validate_json_value(packet)
    if len(canonical_bytes(packet)) > MAX_PACKET_BYTES:
        raise PacketError("Packet exceeds the maximum size")
    if set(packet) != {"packet_version", "kind", "msgbus", "netlink", "authorization", "payload"}:
        raise PacketError("Packet fields are missing or unexpected")
    if isinstance(packet.get("packet_version"), bool) or packet.get("packet_version") != 1:
        raise PacketError("Unsupported packet version")
    if not isinstance(packet.get("kind"), str) or packet["kind"] not in {"request", "response"}:
        raise PacketError("Packet kind must be request or response")
    for section in ("msgbus", "netlink", "authorization", "payload"):
        if not isinstance(packet.get(section), dict):
            raise PacketError(f"Packet section '{section}' must be an object")
    msgbus = packet["msgbus"]
    required_msgbus = {"request_id", "source_device_id", "destination_device_id"}
    optional_msgbus = {
        "source_device_alias", "destination_device_alias", "priority",
    }
    if not required_msgbus.issubset(msgbus) or set(msgbus) - required_msgbus - optional_msgbus:
        raise PacketError("MsgBus fields are missing or unexpected")
    for field in required_msgbus:
        require_text(msgbus[field], f"msgbus.{field}")
    for field in ("source_device_alias", "destination_device_alias"):
        if field in msgbus and (not isinstance(msgbus[field], str) or len(msgbus[field]) > 128):
            raise PacketError(f"msgbus.{field} is invalid")
    if "priority" in msgbus and (
        not isinstance(msgbus["priority"], str)
        or msgbus["priority"] not in {"low", "normal", "high"}
    ):
        raise PacketError("msgbus.priority is invalid")
    if len(packet["netlink"]) > 32:
        raise PacketError("Netlink route metadata has too many fields")
    if packet["kind"] == "request":
        expected_auth = {
            "authority_id", "authority_public_key", "token", "audience",
            "capability", "nonce", "sequence", "signature",
        }
        expected_payload = {"payload_type", "payload_version", "operation", "arguments"}
    else:
        expected_auth = {"signer_device_id", "signature"}
        expected_payload = {"payload_type", "payload_version", "in_reply_to"}
        allowed_payload = expected_payload | {"result", "error"}
        if set(packet["payload"]) - allowed_payload:
            raise PacketError("Response payload fields are unexpected")
        has_result = "result" in packet["payload"]
        has_error = "error" in packet["payload"]
        if has_result == has_error:
            raise PacketError("Response must contain exactly one result or error")
        if has_error:
            error = packet["payload"]["error"]
            if (
                not isinstance(error, dict)
                or set(error) != {"code", "message"}
                or not isinstance(error["code"], str)
                or not error["code"]
                or not isinstance(error["message"], str)
                or not error["message"]
                or len(error["message"]) > 512
            ):
                raise PacketError("Response error object is invalid")
    if set(packet["authorization"]) != expected_auth:
        raise PacketError("Authorization fields are missing or unexpected")
    if set(packet["payload"]) != expected_payload and packet["kind"] == "request":
        raise PacketError("Request payload fields are missing or unexpected")
    if not expected_payload.issubset(packet["payload"]):
        raise PacketError("Packet payload fields are missing")
    return packet
