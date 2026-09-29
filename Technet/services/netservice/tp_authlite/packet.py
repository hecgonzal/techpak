"""Typed request/response packets with signed immutable content."""

from __future__ import annotations

import time
import uuid
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

from .canonical import canonical_bytes, decode_signature, encode_signature, require_text, validate_json_value, validate_packet_shape
from .errors import PacketError, SignatureError

PACKET_VERSION = 1
MAX_OPERATION_LENGTH = 128
_MISSING = object()


def _request_signed_content(packet: dict[str, Any]) -> dict[str, Any]:
    msgbus = packet["msgbus"]
    authorization = packet["authorization"]
    return {
        "packet_version": packet["packet_version"],
        "kind": packet["kind"],
        "msgbus": {
            key: msgbus[key]
            for key in ("request_id", "source_device_id", "destination_device_id")
        },
        "authorization": {
            key: authorization[key]
            for key in (
                "authority_id", "authority_public_key", "token", "audience",
                "capability", "nonce", "sequence",
            )
        },
        "payload": packet["payload"],
    }


def _response_signed_content(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "packet_version": packet["packet_version"],
        "kind": packet["kind"],
        "msgbus": {
            key: packet["msgbus"][key]
            for key in ("request_id", "source_device_id", "destination_device_id")
        },
        "authorization": {
            "signer_device_id": packet["authorization"]["signer_device_id"],
        },
        "payload": packet["payload"],
    }


def build_request_packet(
    signing_key: Ed25519PrivateKey,
    *,
    authority_id: str,
    authority_public_key: Ed25519PublicKey,
    token: dict[str, Any],
    source_device_id: str,
    destination_device_id: str,
    audience: str,
    capability: str,
    operation: str,
    arguments: dict[str, Any],
    sequence: int,
    request_id: str | None = None,
    nonce: str | None = None,
    netlink: dict[str, Any] | None = None,
    source_device_alias: str = "",
    destination_device_alias: str = "",
    priority: str = "normal",
) -> dict[str, Any]:
    require_text(source_device_id, "source_device_id")
    require_text(destination_device_id, "destination_device_id")
    require_text(authority_id, "authority_id")
    require_text(audience, "audience")
    require_text(capability, "capability")
    require_text(operation, "operation", limit=MAX_OPERATION_LENGTH)
    generated_nonce = nonce or uuid.uuid4().hex
    require_text(generated_nonce, "nonce", limit=128)
    if not isinstance(arguments, dict):
        raise PacketError("arguments must be an object")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise PacketError("sequence must be a positive integer")
    payload = {
        "payload_type": "service.request",
        "payload_version": 1,
        "operation": operation,
        "arguments": arguments,
    }
    packet: dict[str, Any] = {
        "packet_version": PACKET_VERSION,
        "kind": "request",
        "msgbus": {
            "request_id": require_text(request_id or str(uuid.uuid4()), "request_id"),
            "source_device_id": source_device_id,
            "source_device_alias": source_device_alias,
            "destination_device_id": destination_device_id,
            "destination_device_alias": destination_device_alias,
            "priority": priority,
        },
        "netlink": dict(netlink or {}),
        "authorization": {
            "authority_id": authority_id,
            "authority_public_key": encode_signature(
                authority_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ),
            "token": token,
            "audience": audience,
            "capability": capability,
            "nonce": generated_nonce,
            "sequence": sequence,
            # Ed25519 signatures are 64 bytes, encoded as 86 unpadded base64url characters.
            "signature": "A" * 86,
        },
        "payload": payload,
    }
    validate_packet_shape(packet)
    signed = _request_signed_content(packet)
    packet["authorization"]["signature"] = encode_signature(signing_key.sign(canonical_bytes(signed)))
    validate_packet_shape(packet)
    return packet


def verify_request_signature(packet: object, verification_key: Ed25519PublicKey) -> dict[str, Any]:
    packet = validate_packet_shape(packet)
    if packet["kind"] != "request":
        raise PacketError("Expected a request packet")
    required_auth = {
        "authority_id", "authority_public_key", "token", "audience",
        "capability", "nonce", "sequence", "signature",
    }
    if set(packet["authorization"]) != required_auth:
        raise PacketError("Request authorization fields are invalid")
    msgbus = packet["msgbus"]
    for field in ("request_id", "source_device_id", "destination_device_id"):
        require_text(msgbus.get(field), f"msgbus.{field}")
    require_text(packet["authorization"].get("audience"), "authorization.audience")
    require_text(packet["authorization"].get("authority_id"), "authorization.authority_id")
    authority_public_key = decode_signature(packet["authorization"].get("authority_public_key"))
    if len(authority_public_key) != 32:
        raise PacketError("Authority public key encoding is invalid")
    require_text(packet["authorization"].get("capability"), "authorization.capability")
    require_text(packet["authorization"].get("nonce"), "authorization.nonce", limit=128)
    sequence = packet["authorization"].get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise PacketError("authorization.sequence must be a positive integer")
    payload = packet["payload"]
    if (
        payload.get("payload_type") != "service.request"
        or isinstance(payload.get("payload_version"), bool)
        or payload.get("payload_version") != 1
        or not isinstance(payload.get("arguments"), dict)
    ):
        raise PacketError("Request payload is invalid")
    require_text(payload.get("operation"), "payload.operation", limit=MAX_OPERATION_LENGTH)
    try:
        verification_key.verify(
            decode_signature(packet["authorization"]["signature"]),
            canonical_bytes(_request_signed_content(packet)),
        )
    except InvalidSignature as error:
        raise SignatureError("Request signature is invalid") from error
    return packet


def build_response_packet(
    signing_key: Ed25519PrivateKey,
    *,
    signer_device_id: str,
    request_packet: dict[str, Any],
    result: Any = _MISSING,
    error: dict[str, str] | None = None,
    netlink: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = validate_packet_shape(request_packet)
    if request["kind"] != "request":
        raise PacketError("A response must refer to a request packet")
    if (result is _MISSING) == (error is None):
        raise PacketError("Response must contain exactly one of result or error")
    if error is not None and (
        not isinstance(error, dict)
        or set(error) != {"code", "message"}
        or not isinstance(error.get("code"), str)
        or not error["code"]
        or len(error["code"]) > 256
        or not isinstance(error.get("message"), str)
        or not error["message"]
        or len(error["message"]) > 512
    ):
        raise PacketError("Response error must contain non-empty code and message strings")
    response_payload: dict[str, Any] = {
        "payload_type": "service.response",
        "payload_version": 1,
        "in_reply_to": request["msgbus"]["request_id"],
    }
    if error is None:
        validate_json_value(result)
        response_payload["result"] = result
    else:
        response_payload["error"] = error
    response: dict[str, Any] = {
        "packet_version": PACKET_VERSION,
        "kind": "response",
        "msgbus": {
            "request_id": request["msgbus"]["request_id"],
            "source_device_id": signer_device_id,
            "destination_device_id": request["msgbus"]["source_device_id"],
        },
        "netlink": dict(netlink or {}),
        "authorization": {"signer_device_id": signer_device_id, "signature": "A" * 86},
        "payload": response_payload,
    }
    validate_packet_shape(response)
    response["authorization"]["signature"] = encode_signature(
        signing_key.sign(canonical_bytes(_response_signed_content(response)))
    )
    return response


def verify_response_packet(
    packet: object,
    verification_key: Ed25519PublicKey,
    *,
    expected_signer_device_id: str,
    expected_recipient_device_id: str,
    expected_request_id: str,
) -> dict[str, Any]:
    packet = validate_packet_shape(packet)
    if packet["kind"] != "response":
        raise PacketError("Expected a response packet")
    if set(packet["authorization"]) != {"signer_device_id", "signature"}:
        raise PacketError("Response authorization fields are invalid")
    if packet["authorization"]["signer_device_id"] != expected_signer_device_id:
        raise SignatureError("Response signer does not match expected destination")
    require_text(packet["authorization"]["signer_device_id"], "authorization.signer_device_id")
    if packet["msgbus"].get("source_device_id") != expected_signer_device_id:
        raise SignatureError("Response source does not match its signer")
    if packet["msgbus"].get("destination_device_id") != expected_recipient_device_id:
        raise PacketError("Response is addressed to a different device")
    if packet["msgbus"].get("request_id") != expected_request_id:
        raise PacketError("Response request ID does not match the outstanding request")
    if packet["payload"].get("in_reply_to") != expected_request_id:
        raise PacketError("Response correlation field is invalid")
    if packet["payload"].get("payload_type") != "service.response":
        raise PacketError("Response payload type is invalid")
    if (
        isinstance(packet["payload"].get("payload_version"), bool)
        or packet["payload"].get("payload_version") != 1
    ):
        raise PacketError("Unsupported response payload version")
    try:
        verification_key.verify(
            decode_signature(packet["authorization"]["signature"]),
            canonical_bytes(_response_signed_content(packet)),
        )
    except InvalidSignature as error:
        raise SignatureError("Response signature is invalid") from error
    return packet


def utc_timestamp() -> int:
    return int(time.time())
