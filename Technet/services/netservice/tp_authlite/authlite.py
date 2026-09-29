"""In-process Authlite MVP: BrainBoard authority, enrollment, tokens and replay checks.

This module performs no network I/O. The caller is responsible for placing the
service behind an authenticated transport before exposing administrative APIs.
"""

from __future__ import annotations

import time
import uuid
import secrets
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .canonical import decode_signature, require_text
from .errors import EnrollmentError, MissingCapability, PacketError, SignatureError, TokenError, WrongAudience
from .packet import verify_request_signature
from .storage import SQLiteAuthStore
from .tokens import TOKEN_TTL_SECONDS, issue_token, verify_token

ENROLLMENT_TTL_SECONDS = 5 * 60
CONFIRMATION_TTL_SECONDS = 60


class PhysicalConfirmationProvider(Protocol):
    """Local confirmation interface; never invoke this through a remote packet."""

    def confirm(self, session_id: str, challenge: bytes) -> bool:
        """Return true only after the device's local physical confirmation."""


class DevelopmentCallbackConfirmation:
    """Development/test-only local callback; not evidence of physical presence."""

    def __init__(self, callback) -> None:
        self._callback = callback

    def confirm(self, session_id: str, challenge: bytes) -> bool:
        return self._callback(session_id, challenge) is True


class DevelopmentCLIConfirmation:
    """Interactive local development prompt; not proof of physical presence."""

    def confirm(self, session_id: str, challenge: bytes) -> bool:
        del challenge  # The user confirms a local pending session, not secret material.
        print("DEVELOPMENT ONLY: this prompt is not hardware physical confirmation.")
        answer = input(f"Approve local enrollment session {session_id}? Type YES: ")
        return answer.strip() == "YES"


class Authlite:
    def __init__(
        self,
        *,
        authority_device_id: str,
        store: SQLiteAuthStore,
        authority_signing_key: Ed25519PrivateKey | None = None,
        authority_public_key: Ed25519PublicKey | None = None,
        clock=time.time,
    ) -> None:
        self.authority_device_id = require_text(authority_device_id, "authority_device_id")
        if authority_signing_key is None and authority_public_key is None:
            raise ValueError("Provide an authority signing key or pinned public key")
        derived_public_key = authority_signing_key.public_key() if authority_signing_key else None
        if (
            derived_public_key is not None
            and authority_public_key is not None
            and derived_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            != authority_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        ):
            raise ValueError("Authority signing key and public key do not match")
        resolved_public_key = derived_public_key or authority_public_key
        if resolved_public_key is None:
            raise ValueError("Unable to resolve authority public key")
        self.authority_signing_key = authority_signing_key
        self.authority_public_key = resolved_public_key
        self.store = store
        self._clock = clock
        self.store.register_authority(
            self.authority_device_id,
            self.authority_public_key_bytes,
        )

    def _require_authority_signer(self) -> Ed25519PrivateKey:
        if self.authority_signing_key is None:
            raise EnrollmentError("This node has only the pinned authority public key")
        return self.authority_signing_key

    @property
    def authority_public_key_bytes(self) -> bytes:
        return self.authority_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def create_enrollment_request(
        self,
        *,
        public_key: bytes,
        alias: str,
        device_type: str,
    ) -> str:
        self._require_authority_signer()
        if not isinstance(public_key, bytes) or len(public_key) != 32:
            raise EnrollmentError("Enrollment requires a raw Ed25519 public key")
        require_text(alias, "alias", limit=128)
        require_text(device_type, "device_type", limit=128)
        session_id = str(uuid.uuid4())
        now = int(self._clock())
        self.store.create_pending_enrollment(
            session_id=session_id,
            public_key=public_key,
            alias=alias,
            device_type=device_type,
            expires_at=now + ENROLLMENT_TTL_SECONDS,
        )
        return session_id

    def approve_enrollment(self, session_id: str) -> None:
        """Approve one exact pending session; caller must be a local admin surface."""
        self._require_authority_signer()
        self.store.approve_enrollment(session_id, int(self._clock()))

    def begin_enrollment_challenge(
        self,
        session_id: str,
        confirmation_provider: PhysicalConfirmationProvider,
    ) -> bytes:
        self._require_authority_signer()
        now = int(self._clock())
        pending = self.store.get_pending_enrollment(session_id, now)
        if not pending["approved"]:
            raise EnrollmentError("Enrollment must be approved before local confirmation")
        challenge = secrets.token_bytes(32)
        try:
            confirmed = confirmation_provider.confirm(session_id, challenge)
        except Exception as error:
            self.store.fail_enrollment(
                session_id,
                now=int(self._clock()),
                reason_code="confirmation_provider_failed",
            )
            raise EnrollmentError("Local physical confirmation provider failed") from error
        if confirmed is not True:
            self.store.fail_enrollment(
                session_id,
                now=int(self._clock()),
                reason_code="physical_confirmation_denied",
            )
            raise EnrollmentError("Local physical confirmation was not provided")
        self.store.prepare_challenge(
            session_id,
            challenge=challenge,
            now=now,
            challenge_expires_at=now + CONFIRMATION_TTL_SECONDS,
        )
        return challenge

    def complete_enrollment(self, session_id: str, challenge_signature: bytes) -> str:
        self._require_authority_signer()
        now = int(self._clock())
        pending = self.store.get_pending_enrollment(session_id, now)
        challenge_expires_at = pending["challenge_expires_at"]
        if (
            not pending["approved"]
            or pending["challenge"] is None
            or challenge_expires_at is None
            or challenge_expires_at <= now
        ):
            raise EnrollmentError("Approved physical confirmation challenge is missing or expired")
        try:
            device_public_key = Ed25519PublicKey.from_public_bytes(pending["public_key"])
            device_public_key.verify(challenge_signature, pending["challenge"])
        except (InvalidSignature, ValueError, TypeError) as error:
            self.store.fail_enrollment(
                session_id,
                now=now,
                reason_code="invalid_enrollment_proof",
            )
            raise EnrollmentError("Enrollment challenge signature is invalid") from error
        return self.store.complete_enrollment(
            session_id,
            signature_verified=True,
            now=now,
        )

    def set_device_capabilities(self, device_id: str, audience: str, capabilities: list[str]) -> None:
        """Local administrator operation; not exposed as a packet handler."""
        self._require_authority_signer()
        require_text(audience, "audience")
        for capability in capabilities:
            require_text(capability, "capability")
        self.store.set_capabilities(
            device_id,
            audience,
            capabilities,
            now=int(self._clock()),
        )

    def next_sequence(self, device_id: str, peer_device_id: str) -> int:
        """Reserve the next durable sequence for an outgoing device-to-peer flow."""
        require_text(peer_device_id, "peer_device_id")
        return self.store.next_outgoing_sequence(device_id, peer_device_id)

    def issue_token(
        self,
        *,
        device_id: str,
        audience: str,
        capabilities: list[str],
        ttl_seconds: int = TOKEN_TTL_SECONDS,
    ) -> dict:
        """Issue for an enrolled device after local authenticated-session checks.

        The no-socket MVP cannot establish mTLS itself. Its eventual transport
        adapter must prove the authenticated peer is this device before calling.
        """
        authority_signing_key = self._require_authority_signer()
        device = self.store.get_device(device_id)
        allowed = self.store.get_capabilities(device_id, audience)
        if not isinstance(capabilities, list):
            raise MissingCapability("Requested capabilities must be a list")
        for capability in capabilities:
            require_text(capability, "capability")
        requested = set(capabilities)
        if not requested or not requested.issubset(allowed):
            raise MissingCapability("Requested token capabilities exceed device policy")
        token = issue_token(
            authority_signing_key,
            issuer=self.authority_device_id,
            subject=device["device_id"],
            audience=audience,
            capabilities=sorted(requested),
            now=int(self._clock()),
            ttl_seconds=ttl_seconds,
        )
        self.store.record_security_event(
            timestamp=int(self._clock()),
            event_type="token_issuance",
            device_id=device_id,
            request_id=token["token_id"],
            result="issued",
            reason_code=None,
        )
        return token

    def verify_and_consume_request(
        self,
        packet: object,
        *,
        local_device_id: str,
        expected_audience: str,
        required_capability: str | None = None,
    ) -> dict:
        """Authenticate and durably consume replay state before service dispatch."""
        from .canonical import validate_packet_shape

        packet = validate_packet_shape(packet)
        if packet["kind"] != "request":
            raise PacketError("Expected a request packet")
        msgbus = packet["msgbus"]
        source_device_id = require_text(msgbus.get("source_device_id"), "msgbus.source_device_id")
        destination_device_id = require_text(msgbus.get("destination_device_id"), "msgbus.destination_device_id")
        if destination_device_id != local_device_id:
            raise WrongAudience("Packet is addressed to a different device")
        self.store.get_device(local_device_id)
        authorization = packet["authorization"]
        if authorization.get("audience") != expected_audience:
            raise WrongAudience("Packet is addressed to a different service")
        capability = require_text(authorization.get("capability"), "authorization.capability")
        if required_capability is not None and capability != required_capability:
            raise MissingCapability("Request capability does not match the registered operation")
        token = authorization.get("token")
        if (
            authorization.get("authority_id") != self.authority_device_id
            or
            not isinstance(token, dict)
            or not isinstance(token.get("issuer"), str)
            or token.get("issuer") != self.authority_device_id
            or not self.store.verify_authority_key(
                authorization["authority_id"],
                decode_signature(authorization.get("authority_public_key")),
            )
            or decode_signature(authorization.get("authority_public_key")) != self.authority_public_key_bytes
        ):
            raise TokenError("Token issuer does not match the pinned BrainBoard authority")
        device = self.store.get_device(source_device_id)
        try:
            device_public_key = Ed25519PublicKey.from_public_bytes(device["public_key"])
        except (ValueError, TypeError) as error:
            raise SignatureError("Registered device public key is invalid") from error
        verify_request_signature(packet, device_public_key)
        claims = verify_token(
            authorization["token"],
            self.authority_public_key,
            expected_issuer=self.authority_device_id,
            expected_audience=expected_audience,
            now=int(self._clock()),
        )
        if claims["subject"] != source_device_id:
            raise TokenError("Token subject does not match the signing device")
        if self.store.token_is_revoked(claims["token_id"]):
            raise TokenError("Token has been revoked")
        if capability not in claims["capabilities"]:
            raise MissingCapability("Token does not grant the requested capability")
        sequence = authorization.get("sequence")
        nonce = require_text(authorization.get("nonce"), "authorization.nonce", limit=128)
        request_id = require_text(msgbus.get("request_id"), "msgbus.request_id")
        self.store.consume_request(
            device_id=source_device_id,
            audience=expected_audience,
            capability=capability,
            request_id=request_id,
            nonce=nonce,
            token_id=claims["token_id"],
            token_expires_at=claims["expires_at"],
            sequence=sequence,
            now=int(self._clock()),
            token_capabilities=frozenset(claims["capabilities"]),
            required_policy_capability=required_capability or capability,
        )
        return {
            "device_id": source_device_id,
            "audience": expected_audience,
            "capability": capability,
            "request_id": request_id,
            "operation": packet["payload"]["operation"],
            "arguments": packet["payload"]["arguments"],
            "token_id": claims["token_id"],
        }

    def revoke_device(self, device_id: str) -> None:
        self._require_authority_signer()
        self.store.revoke_device(device_id, int(self._clock()))

    def revoke_token(self, token_id: str) -> None:
        self._require_authority_signer()
        self.store.revoke_token(token_id, int(self._clock()))
