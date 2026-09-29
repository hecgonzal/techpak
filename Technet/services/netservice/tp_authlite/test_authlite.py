from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from Technet.services.packservice.tp_ruppertlog import TechServicesLog
from Technet.services.netservice.tp_msgbus import attach_route_metadata

from . import (
    AuthenticatedDispatcher,
    Authlite,
    DevelopmentCallbackConfirmation,
    EnrollmentError,
    FileKeyStore,
    MissingCapability,
    PacketError,
    ReplayDetected,
    SQLiteAuthStore,
    SignatureError,
    StorageError,
    TokenError,
    WrongAudience,
    build_request_packet,
    parse_packet,
    verify_response_packet,
    verify_token,
)
from .canonical import canonical_bytes, decode_signature


class MutableClock:
    def __init__(self, value: int = 1_800_000_000) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class AuthliteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.clock = MutableClock()
        self.store_path = self.root / "authlite.sqlite3"
        self.store = SQLiteAuthStore(self.store_path)
        self.addCleanup(self._close_store)
        self.authority_key = Ed25519PrivateKey.generate()
        self.authlite = Authlite(
            authority_device_id="brainboard-authority",
            authority_signing_key=self.authority_key,
            store=self.store,
            clock=self.clock,
        )
        self.client_key = Ed25519PrivateKey.generate()
        self.receiver_key = Ed25519PrivateKey.generate()
        self.client_id = self.enroll(self.client_key, "watch-1", "wearable")
        self.receiver_id = self.enroll(self.receiver_key, "brainboard", "brainboard")
        self.audience = "tp-sysinfo"
        self.capability = "telemetry.read"
        self.authlite.set_device_capabilities(
            self.client_id,
            self.audience,
            [self.capability],
        )
        self.token = self.authlite.issue_token(
            device_id=self.client_id,
            audience=self.audience,
            capabilities=[self.capability],
        )
        self.calls: list[dict] = []
        self.service_log = TechServicesLog(self.root / "TechServicesLog.jsonl")
        self.dispatcher = self.make_dispatcher()

    def _close_store(self) -> None:
        try:
            self.store.close()
        except Exception:
            pass

    @staticmethod
    def raw_public_key(key: Ed25519PrivateKey) -> bytes:
        return key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def enroll(self, key: Ed25519PrivateKey, alias: str, device_type: str) -> str:
        session_id = self.authlite.create_enrollment_request(
            public_key=self.raw_public_key(key),
            alias=alias,
            device_type=device_type,
        )
        self.authlite.approve_enrollment(session_id)
        challenge = self.authlite.begin_enrollment_challenge(
            session_id,
            DevelopmentCallbackConfirmation(lambda _session, _challenge: True),
        )
        return self.authlite.complete_enrollment(session_id, key.sign(challenge))

    def make_dispatcher(self, *, service_log=None) -> AuthenticatedDispatcher:
        dispatcher = AuthenticatedDispatcher(
            authlite=self.authlite,
            local_device_id=self.receiver_id,
            response_signing_key=self.receiver_key,
            service_log=service_log or self.service_log,
            clock=self.clock,
        )
        dispatcher.register(
            audience=self.audience,
            operation="sysinfo.get",
            capability=self.capability,
            handler=lambda arguments: self._handle(arguments),
            validate_arguments=self._validate_arguments,
        )
        return dispatcher

    def _handle(self, arguments: dict) -> dict:
        self.calls.append(arguments)
        return {"battery_percent": 87}

    @staticmethod
    def _validate_arguments(arguments: dict) -> None:
        if set(arguments) - {"fields"}:
            raise ValueError("Unexpected sysinfo argument")
        if "fields" in arguments and not isinstance(arguments["fields"], list):
            raise ValueError("fields must be a list")

    def make_packet(self, *, sequence: int = 1, **overrides) -> dict:
        values = {
            "authority_id": "brainboard-authority",
            "authority_public_key": self.authority_key.public_key(),
            "token": self.token,
            "source_device_id": self.client_id,
            "destination_device_id": self.receiver_id,
            "audience": self.audience,
            "capability": self.capability,
            "operation": "sysinfo.get",
            "arguments": {"fields": ["battery"]},
            "sequence": sequence,
            "netlink": {"hop_count": 2, "mesh_route": ["relay-a"]},
        }
        values.update(overrides)
        return build_request_packet(self.client_key, **values)

    def test_rfc8785_canonical_form_is_stable(self) -> None:
        self.assertEqual(canonical_bytes({"z": 1, "a": "é", "n": 1.0}), b'{"a":"\xc3\xa9","n":1,"z":1}')

    def test_packet_rejects_boolean_version_and_unexpected_fields(self) -> None:
        packet = self.make_packet()
        packet["packet_version"] = True
        with self.assertRaises(PacketError):
            self.authlite.verify_and_consume_request(
                packet,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )
        packet = self.make_packet(sequence=2)
        packet["unexpected"] = "not in the packet contract"
        with self.assertRaises(PacketError):
            self.authlite.verify_and_consume_request(
                packet,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

    def test_wire_parser_rejects_ambiguous_and_invalid_json(self) -> None:
        packet = self.make_packet()
        self.assertEqual(parse_packet(json.dumps(packet)), packet)
        with self.assertRaises(PacketError):
            parse_packet(b'{"packet_version":1,"packet_version":1}')
        with self.assertRaises(PacketError):
            parse_packet(b'{"value":NaN}')
        with self.assertRaises(PacketError):
            parse_packet(b"\xff")
        with self.assertRaises(PacketError):
            parse_packet(b" " * (256 * 1024 + 1))
        with self.assertRaises(PacketError):
            decode_signature("%%%not-base64%%")

    def test_enrollment_requires_approval_and_local_confirmation(self) -> None:
        key = Ed25519PrivateKey.generate()
        session = self.authlite.create_enrollment_request(
            public_key=self.raw_public_key(key),
            alias="unapproved",
            device_type="wearable",
        )
        with self.assertRaises(EnrollmentError):
            self.authlite.begin_enrollment_challenge(
                session,
                DevelopmentCallbackConfirmation(lambda _session, _challenge: True),
            )
        self.authlite.approve_enrollment(session)
        with self.assertRaises(EnrollmentError):
            self.authlite.begin_enrollment_challenge(
                session,
                DevelopmentCallbackConfirmation(lambda _session, _challenge: False),
            )
        with self.assertRaises(EnrollmentError):
            self.authlite.begin_enrollment_challenge(
                session,
                DevelopmentCallbackConfirmation(lambda _session, _challenge: True),
            )

    def test_enrollment_proves_possession_of_approved_private_key(self) -> None:
        key = Ed25519PrivateKey.generate()
        session = self.authlite.create_enrollment_request(
            public_key=self.raw_public_key(key),
            alias="new-watch",
            device_type="wearable",
        )
        self.authlite.approve_enrollment(session)
        challenge = self.authlite.begin_enrollment_challenge(
            session,
            DevelopmentCallbackConfirmation(lambda _session, _challenge: True),
        )
        enrolled = self.authlite.complete_enrollment(session, key.sign(challenge))
        self.assertEqual(self.store.get_device(enrolled)["alias"], "new-watch")

    def test_duplicate_public_key_cannot_start_another_enrollment(self) -> None:
        with self.assertRaises(EnrollmentError):
            self.authlite.create_enrollment_request(
                public_key=self.raw_public_key(self.client_key),
                alias="second-identity-for-same-key",
                device_type="wearable",
            )

    def test_policy_changes_are_recorded_in_security_audit(self) -> None:
        self.authlite.set_device_capabilities(
            self.client_id,
            self.audience,
            [self.capability],
        )
        events = self.store.read_security_events()
        policy_events = [event for event in events if event["event_type"] == "policy_update"]
        self.assertEqual(policy_events[-1]["device_id"], self.client_id)
        self.assertEqual(policy_events[-1]["capability"], self.capability)

    def test_invalid_enrollment_proof_consumes_pending_session(self) -> None:
        key = Ed25519PrivateKey.generate()
        session = self.authlite.create_enrollment_request(
            public_key=self.raw_public_key(key),
            alias="bad-proof",
            device_type="wearable",
        )
        self.authlite.approve_enrollment(session)
        challenge = self.authlite.begin_enrollment_challenge(
            session,
            DevelopmentCallbackConfirmation(lambda _session, _challenge: True),
        )
        wrong_key = Ed25519PrivateKey.generate()
        with self.assertRaises(EnrollmentError):
            self.authlite.complete_enrollment(session, wrong_key.sign(challenge))
        with self.assertRaises(EnrollmentError):
            self.authlite.complete_enrollment(session, key.sign(challenge))
        failed = [
            event for event in self.store.read_security_events()
            if event["event_type"] == "enrollment_failure"
        ]
        self.assertEqual(failed[-1]["reason_code"], "invalid_enrollment_proof")

    def test_file_key_store_reloads_same_key_and_uses_restrictive_permissions(self) -> None:
        key_dir = self.root / "private-keys"
        key_dir.mkdir(mode=0o700)
        if os.name == "posix":
            key_dir.chmod(0o700)
        key_store = FileKeyStore(key_dir)
        first = key_store.load_or_create("device-identity")
        second = key_store.load_or_create("device-identity")
        self.assertEqual(self.raw_public_key(first), self.raw_public_key(second))
        if os.name == "posix":
            self.assertEqual((key_dir / "device-identity.ed25519").stat().st_mode & 0o777, 0o600)

    def test_policy_limited_token_is_signed_and_tampering_is_rejected(self) -> None:
        claims = verify_token(
            self.token,
            self.authority_key.public_key(),
            expected_issuer="brainboard-authority",
            expected_audience=self.audience,
            now=self.clock.value,
        )
        self.assertEqual(claims["subject"], self.client_id)
        altered = dict(self.token)
        altered["capabilities"] = ["admin.root"]
        with self.assertRaises(TokenError):
            verify_token(
                altered,
                self.authority_key.public_key(),
                expected_issuer="brainboard-authority",
                expected_audience=self.audience,
                now=self.clock.value,
            )
        with self.assertRaises(MissingCapability):
            self.authlite.issue_token(
                device_id=self.client_id,
                audience=self.audience,
                capabilities=["admin.root"],
            )

    def test_receiver_verifies_brainboard_token_with_public_key_only(self) -> None:
        receiver_store_path = self.root / "separate-receiver.sqlite3"
        receiver_store = SQLiteAuthStore(receiver_store_path)
        self.addCleanup(receiver_store.close)
        receiver = Authlite(
            authority_device_id="brainboard-authority",
            authority_public_key=self.authority_key.public_key(),
            store=receiver_store,
            clock=self.clock,
        )
        self.assertIsNone(receiver.authority_signing_key)
        claims = verify_token(
            self.token,
            receiver.authority_public_key,
            expected_issuer="brainboard-authority",
            expected_audience=self.audience,
            now=self.clock.value,
        )
        self.assertEqual(claims["subject"], self.client_id)

    def test_expired_wrong_audience_and_revoked_tokens_are_rejected(self) -> None:
        packet = self.make_packet()
        self.clock.value += 3600
        with self.assertRaises(TokenError):
            self.authlite.verify_and_consume_request(
                packet,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

        self.clock.value -= 3600
        self.authlite.set_device_capabilities(
            self.client_id,
            "tp-other",
            ["telemetry.read"],
        )
        wrong_audience_token = self.authlite.issue_token(
            device_id=self.client_id,
            audience="tp-other",
            capabilities=["telemetry.read"],
        )
        wrong_audience_packet = self.make_packet(token=wrong_audience_token)
        with self.assertRaises(WrongAudience):
            self.authlite.verify_and_consume_request(
                wrong_audience_packet,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

        self.authlite.revoke_token(self.token["token_id"])
        with self.assertRaises(TokenError):
            self.authlite.verify_and_consume_request(
                self.make_packet(),
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

    def test_mutable_route_can_change_but_signed_payload_cannot(self) -> None:
        packet = self.make_packet()
        routed_packet = attach_route_metadata(
            packet,
            {"hop_count": 17, "mesh_route": ["other-relay"]},
        )
        self.assertNotEqual(packet["netlink"], routed_packet["netlink"])
        response = self.dispatcher.dispatch(routed_packet)
        verified = verify_response_packet(
            response,
            self.receiver_key.public_key(),
            expected_signer_device_id=self.receiver_id,
            expected_recipient_device_id=self.client_id,
            expected_request_id=packet["msgbus"]["request_id"],
        )
        self.assertEqual(verified["payload"]["result"], {"battery_percent": 87})
        self.assertEqual(len(self.calls), 1)

        altered = self.make_packet(sequence=2)
        altered["payload"]["arguments"]["fields"] = ["secrets"]
        with self.assertRaises(SignatureError):
            self.authlite.verify_and_consume_request(
                altered,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

    def test_missing_capability_and_bad_arguments_never_invoke_handler(self) -> None:
        packet = self.make_packet(capability="admin.root")
        response = self.dispatcher.dispatch(packet)
        self.assertEqual(response["payload"]["error"]["code"], "missing_capability")
        self.assertEqual(self.calls, [])

        invalid_args = self.make_packet(
            sequence=1,
            request_id="bad-args",
            nonce="bad-args-nonce",
            arguments={"fields": "battery"},
        )
        invalid_response = self.dispatcher.dispatch(invalid_args)
        self.assertEqual(invalid_response["payload"]["error"]["code"], "malformed_packet")
        self.assertEqual(self.calls, [])

    def test_replay_is_rejected_and_handler_runs_once(self) -> None:
        packet = self.make_packet()
        first_response = self.dispatcher.dispatch(packet)
        second_response = self.dispatcher.dispatch(packet)
        self.assertIn("result", first_response["payload"])
        self.assertEqual(second_response["payload"]["error"]["code"], "replay_detected")
        self.assertEqual(len(self.calls), 1)
        results = [event["result"] for event in self.store.read_security_events() if event["event_type"] == "request_authorization"]
        self.assertIn("accepted", results)
        self.assertIn("denied", results)

    def test_duplicate_nonce_or_request_id_is_rejected_even_with_new_sequence(self) -> None:
        original = self.make_packet(request_id="original-id", nonce="shared-nonce")
        self.authlite.verify_and_consume_request(
            original,
            local_device_id=self.receiver_id,
            expected_audience=self.audience,
        )
        duplicate_nonce = self.make_packet(
            sequence=2,
            request_id="different-id",
            nonce="shared-nonce",
        )
        with self.assertRaises(ReplayDetected):
            self.authlite.verify_and_consume_request(
                duplicate_nonce,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )
        duplicate_request_id = self.make_packet(
            sequence=2,
            request_id="original-id",
            nonce="different-nonce",
        )
        with self.assertRaises(ReplayDetected):
            self.authlite.verify_and_consume_request(
                duplicate_request_id,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

    def test_sequence_and_nonce_state_survive_store_reopen(self) -> None:
        self.assertEqual(self.authlite.next_sequence(self.client_id, self.receiver_id), 1)
        self.assertEqual(self.authlite.next_sequence(self.client_id, self.receiver_id), 2)
        packet = self.make_packet()
        self.dispatcher.dispatch(packet)
        self.store.close()
        self.store = SQLiteAuthStore(self.store_path)
        self.authlite = Authlite(
            authority_device_id="brainboard-authority",
            authority_public_key=self.authority_key.public_key(),
            store=self.store,
            clock=self.clock,
        )
        self.dispatcher = self.make_dispatcher()
        self.assertEqual(self.authlite.next_sequence(self.client_id, self.receiver_id), 3)
        with self.assertRaises(EnrollmentError):
            self.authlite.issue_token(
                device_id=self.client_id,
                audience=self.audience,
                capabilities=[self.capability],
            )
        with self.assertRaises(EnrollmentError):
            self.authlite.set_device_capabilities(
                self.client_id,
                self.audience,
                ["admin.root"],
            )
        with self.assertRaises(ReplayDetected):
            self.authlite.verify_and_consume_request(
                packet,
                local_device_id=self.receiver_id,
                expected_audience=self.audience,
            )

    def test_replay_storage_failure_fails_closed_before_handler(self) -> None:
        from unittest.mock import patch

        packet = self.make_packet()
        with patch.object(self.store, "consume_request", side_effect=StorageError()):
            response = self.dispatcher.dispatch(packet)
        self.assertEqual(response["payload"]["error"]["code"], "protected_storage_error")
        self.assertEqual(self.calls, [])

    def test_bad_response_signature_and_wrong_destination_are_rejected(self) -> None:
        packet = self.make_packet()
        response = self.dispatcher.dispatch(packet)
        altered = dict(response)
        altered["netlink"] = {"hop_count": 10}
        verify_response_packet(
            altered,
            self.receiver_key.public_key(),
            expected_signer_device_id=self.receiver_id,
            expected_recipient_device_id=self.client_id,
            expected_request_id=packet["msgbus"]["request_id"],
        )
        altered_payload = json.loads(json.dumps(response))
        altered_payload["payload"]["result"]["battery_percent"] = 1
        with self.assertRaises(SignatureError):
            verify_response_packet(
                altered_payload,
                self.receiver_key.public_key(),
                expected_signer_device_id=self.receiver_id,
                expected_recipient_device_id=self.client_id,
                expected_request_id=packet["msgbus"]["request_id"],
            )
        with self.assertRaises(PacketError):
            verify_response_packet(
                response,
                self.receiver_key.public_key(),
                expected_signer_device_id=self.receiver_id,
                expected_recipient_device_id="different-device",
                expected_request_id=packet["msgbus"]["request_id"],
            )

    def test_dispatcher_rejects_a_response_key_not_owned_by_local_device(self) -> None:
        with self.assertRaises(SignatureError):
            AuthenticatedDispatcher(
                authlite=self.authlite,
                local_device_id=self.receiver_id,
                response_signing_key=Ed25519PrivateKey.generate(),
                service_log=self.service_log,
                clock=self.clock,
            )

    def test_revoked_device_is_rejected(self) -> None:
        self.authlite.revoke_device(self.client_id)
        response = self.dispatcher.dispatch(self.make_packet())
        self.assertEqual(response["payload"]["error"]["code"], "device_not_active")
        self.assertEqual(self.calls, [])

    def test_packet_cannot_substitute_another_brainboard_key(self) -> None:
        attacker_authority = Ed25519PrivateKey.generate()
        packet = self.make_packet(authority_public_key=attacker_authority.public_key())
        response = self.dispatcher.dispatch(packet)
        self.assertEqual(response["payload"]["error"]["code"], "invalid_token")
        self.assertEqual(self.calls, [])

    def test_service_exception_returns_generic_signed_error(self) -> None:
        dispatcher = AuthenticatedDispatcher(
            authlite=self.authlite,
            local_device_id=self.receiver_id,
            response_signing_key=self.receiver_key,
            service_log=self.service_log,
            clock=self.clock,
        )
        dispatcher.register(
            audience=self.audience,
            operation="sysinfo.get",
            capability=self.capability,
            handler=lambda _arguments: (_ for _ in ()).throw(RuntimeError("private detail")),
        )
        response = dispatcher.dispatch(self.make_packet())
        self.assertEqual(response["payload"]["error"]["code"], "service_execution_failed")
        self.assertNotIn("private detail", response["payload"]["error"]["message"])
        verified = verify_response_packet(
            response,
            self.receiver_key.public_key(),
            expected_signer_device_id=self.receiver_id,
            expected_recipient_device_id=self.client_id,
            expected_request_id=response["msgbus"]["request_id"],
        )
        self.assertEqual(verified["payload"]["error"]["code"], "service_execution_failed")

    def test_non_json_service_result_becomes_generic_signed_error(self) -> None:
        dispatcher = AuthenticatedDispatcher(
            authlite=self.authlite,
            local_device_id=self.receiver_id,
            response_signing_key=self.receiver_key,
            service_log=self.service_log,
            clock=self.clock,
        )
        dispatcher.register(
            audience=self.audience,
            operation="sysinfo.get",
            capability=self.capability,
            handler=lambda arguments: self._return_non_json(arguments),
        )
        response = dispatcher.dispatch(self.make_packet())
        self.assertEqual(response["payload"]["error"]["code"], "service_execution_failed")
        self.assertEqual(self.calls, [])

    @staticmethod
    def _return_non_json(_arguments: dict) -> object:
        return object()

    def test_service_result_none_is_a_valid_signed_result(self) -> None:
        request = self.make_packet()
        response_key = Ed25519PrivateKey.generate()
        from .packet import build_response_packet

        response = build_response_packet(
            response_key,
            signer_device_id=self.receiver_id,
            request_packet=request,
            result=None,
        )
        self.assertIsNone(response["payload"]["result"])


if __name__ == "__main__":
    unittest.main()
