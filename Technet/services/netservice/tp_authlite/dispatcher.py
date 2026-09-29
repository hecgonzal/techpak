"""Receiving-side verify/authorize/validate/execute boundary for in-process MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from ...packservice.tp_ruppertlog import TechServicesLog
from .authlite import Authlite
from .errors import AuthliteError, MissingCapability, PacketError, ServiceNotFound, SignatureError, StorageError
from .packet import build_response_packet


@dataclass(frozen=True)
class ServiceHandler:
    audience: str
    operation: str
    capability: str
    handler: Callable[[dict[str, Any]], Any]
    validate_arguments: Callable[[dict[str, Any]], None] | None = None


class AuthenticatedDispatcher:
    """Never invokes an operation until Authlite and policy checks succeed."""

    def __init__(
        self,
        *,
        authlite: Authlite,
        local_device_id: str,
        response_signing_key: Ed25519PrivateKey,
        service_log: TechServicesLog | None = None,
        clock=time.time,
    ) -> None:
        self.authlite = authlite
        self.local_device_id = local_device_id
        self.response_signing_key = response_signing_key
        registered_device = self.authlite.store.get_device(local_device_id)
        response_public_key = response_signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if response_public_key != registered_device["public_key"]:
            raise SignatureError("Response signing key does not match the local registered device")
        self.service_log = service_log or TechServicesLog()
        self._clock = clock
        self._handlers: dict[tuple[str, str], ServiceHandler] = {}

    def register(
        self,
        *,
        audience: str,
        operation: str,
        capability: str,
        handler: Callable[[dict[str, Any]], Any],
        validate_arguments: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        key = (audience, operation)
        if key in self._handlers:
            raise ValueError(f"Handler already registered for {audience}:{operation}")
        self._handlers[key] = ServiceHandler(
            audience=audience,
            operation=operation,
            capability=capability,
            handler=handler,
            validate_arguments=validate_arguments,
        )

    def dispatch(self, packet: object) -> dict[str, Any]:
        """Return an authenticated response; rejected requests never invoke handlers."""
        request_id = self._request_id(packet)
        source_device_id = self._source_device_id(packet)
        try:
            if not isinstance(packet, dict):
                raise PacketError("Packet must be an object")
            authorization = packet.get("authorization")
            audience = authorization.get("audience") if isinstance(authorization, dict) else None
            if not isinstance(audience, str):
                raise PacketError("Packet audience is missing")
            from .canonical import validate_packet_shape

            validated_packet = validate_packet_shape(packet)
            payload = validated_packet["payload"]
            handler_spec = self._handlers.get((audience, payload.get("operation")))
            context = self.authlite.verify_and_consume_request(
                packet,
                local_device_id=self.local_device_id,
                expected_audience=audience,
            )
            if handler_spec is None:
                raise ServiceNotFound("No service operation is registered for this request")
            if context["capability"] != handler_spec.capability:
                raise MissingCapability("Request capability does not match the registered operation")
            if handler_spec.validate_arguments is not None:
                try:
                    handler_spec.validate_arguments(context["arguments"])
                except AuthliteError:
                    raise
                except Exception as error:
                    raise PacketError("Service arguments failed validation") from error

            call_id = str(uuid.uuid4())
            started_at = self._clock()
            if not self._record_service_event(
                handler_spec, "started", request_id, call_id=call_id
            ):
                raise StorageError("Unable to record service-call start")
            try:
                result = handler_spec.handler(context["arguments"])
                success_response = build_response_packet(
                    self.response_signing_key,
                    signer_device_id=self.local_device_id,
                    request_packet=packet,
                    result=result,
                )
            except Exception:
                self._record_service_event(
                    handler_spec,
                    "error",
                    request_id,
                    call_id=call_id,
                    duration_ms=(self._clock() - started_at) * 1000,
                    error="service_execution_failed",
                )
                return build_response_packet(
                    self.response_signing_key,
                    signer_device_id=self.local_device_id,
                    request_packet=packet,
                    error={"code": "service_execution_failed", "message": "Service execution failed"},
                )
            if not self._record_service_event(
                handler_spec,
                "success",
                request_id,
                call_id=call_id,
                duration_ms=(self._clock() - started_at) * 1000,
            ):
                # The service ran; report a failure rather than claiming an audited success.
                return build_response_packet(
                    self.response_signing_key,
                    signer_device_id=self.local_device_id,
                    request_packet=packet,
                    error={"code": "service_audit_failed", "message": "Service result could not be recorded"},
                )
            return success_response
        except AuthliteError as error:
            if source_device_id or request_id:
                authorization = packet.get("authorization") if isinstance(packet, dict) else None
                capability = (
                    authorization.get("capability")
                    if isinstance(authorization, dict)
                    and isinstance(authorization.get("capability"), str)
                    and len(authorization["capability"]) <= 256
                    else None
                )
                self.authlite.store.record_security_event(
                    timestamp=int(self._clock()),
                    event_type="request_authorization",
                    device_id=source_device_id,
                    request_id=request_id,
                    capability=capability,
                    result="denied",
                    reason_code=error.code,
                )
            if not isinstance(packet, dict):
                raise
            return build_response_packet(
                self.response_signing_key,
                signer_device_id=self.local_device_id,
                request_packet=packet,
                error={"code": error.code, "message": error.message},
            )

    def _record_service_event(
        self,
        handler: ServiceHandler,
        status: str,
        request_id: str | None,
        *,
        call_id: str,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> bool:
        try:
            return self.service_log.record(
                handler.audience,
                handler.operation,
                status=status,
                phase="start" if status == "started" else "finish",
                duration_ms=duration_ms,
                request_id=request_id,
                call_id=call_id,
                error=error,
            )
        except Exception:
            return False

    @staticmethod
    def _request_id(packet: object) -> str | None:
        if isinstance(packet, dict) and isinstance(packet.get("msgbus"), dict):
            value = packet["msgbus"].get("request_id")
            return value if isinstance(value, str) else None
        return None

    @staticmethod
    def _source_device_id(packet: object) -> str | None:
        if isinstance(packet, dict) and isinstance(packet.get("msgbus"), dict):
            value = packet["msgbus"].get("source_device_id")
            return value if isinstance(value, str) else None
        return None
