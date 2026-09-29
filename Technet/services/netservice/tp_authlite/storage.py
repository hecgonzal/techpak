"""SQLite-backed device, policy, enrollment, and durable replay state."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from .errors import (
    DeviceNotActive,
    EnrollmentError,
    MissingCapability,
    ReplayDetected,
    StorageError,
    TokenError,
    UnknownDevice,
)


class SQLiteAuthStore:
    """Small local store intended to be opened by one service process."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            target = Path(self.path)
            try:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if os.name == "posix" and target.parent.stat().st_mode & 0o077:
                    raise StorageError("Authlite storage directory permissions are too broad")
                if target.is_symlink():
                    raise StorageError("Authlite database path must not be a symbolic link")
                if (
                    target.exists()
                    and os.name == "posix"
                    and target.stat().st_mode & 0o077
                ):
                    raise StorageError("Authlite database permissions are too broad")
            except OSError as error:
                raise StorageError("Unable to create protected Authlite storage") from error
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                self.path,
                timeout=10,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 10000")
            if self.path != ":memory:" and os.name == "posix":
                os.chmod(self.path, 0o600)
            self._create_schema()
        except (OSError, sqlite3.Error) as error:
            raise StorageError("Unable to initialize protected Authlite storage") from error

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            with self._lock:
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    yield self._connection
                except Exception:
                    self._connection.rollback()
                    raise
                else:
                    self._connection.commit()
        except sqlite3.Error as error:
            raise StorageError("Protected Authlite storage operation failed") from error

    def _create_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            public_key BLOB NOT NULL,
            alias TEXT NOT NULL,
            device_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
            enrolled_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS authorities (
            authority_id TEXT PRIMARY KEY,
            public_key BLOB NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'revoked'))
        );
        CREATE TABLE IF NOT EXISTS capabilities (
            device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
            audience TEXT NOT NULL,
            capability TEXT NOT NULL,
            PRIMARY KEY (device_id, audience, capability)
        );
        CREATE TABLE IF NOT EXISTS pending_enrollments (
            session_id TEXT PRIMARY KEY,
            public_key BLOB NOT NULL,
            alias TEXT NOT NULL,
            device_type TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0,
            challenge BLOB,
            challenge_expires_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_id TEXT PRIMARY KEY,
            revoked_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS replay_state (
            device_id TEXT PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
            last_sequence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outgoing_sequences (
            device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
            peer_device_id TEXT NOT NULL,
            last_sequence INTEGER NOT NULL,
            PRIMARY KEY (device_id, peer_device_id)
        );
        CREATE TABLE IF NOT EXISTS consumed_requests (
            device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
            request_id TEXT NOT NULL,
            nonce TEXT NOT NULL,
            token_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            PRIMARY KEY (device_id, request_id),
            UNIQUE (device_id, nonce)
        );
        CREATE INDEX IF NOT EXISTS consumed_requests_expiry ON consumed_requests(expires_at);
        CREATE TABLE IF NOT EXISTS security_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            device_id TEXT,
            request_id TEXT,
            capability TEXT,
            result TEXT NOT NULL,
            reason_code TEXT
        );
        """
        try:
            with self._lock:
                self._connection.executescript(schema)
                event_columns = {
                    row["name"]
                    for row in self._connection.execute("PRAGMA table_info(security_events)")
                }
                if "capability" not in event_columns:
                    self._connection.execute(
                        "ALTER TABLE security_events ADD COLUMN capability TEXT"
                    )
        except sqlite3.Error as error:
            raise StorageError("Unable to initialize Authlite tables") from error

    def create_pending_enrollment(
        self,
        *,
        session_id: str,
        public_key: bytes,
        alias: str,
        device_type: str,
        expires_at: int,
    ) -> None:
        try:
            with self._transaction() as connection:
                if connection.execute(
                    "SELECT 1 FROM devices WHERE public_key = ? AND status = 'active' "
                    "UNION ALL SELECT 1 FROM pending_enrollments WHERE public_key = ? LIMIT 1",
                    (public_key, public_key),
                ).fetchone() is not None:
                    raise EnrollmentError("This public key is already enrolled or pending")
                connection.execute(
                    "INSERT INTO pending_enrollments "
                    "(session_id, public_key, alias, device_type, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, public_key, alias, device_type, expires_at),
                )
        except sqlite3.IntegrityError as error:
            raise EnrollmentError("Enrollment session already exists") from error

    def register_authority(self, authority_id: str, public_key: bytes) -> None:
        """Pin the expected BrainBoard token-signing public key in local state."""
        try:
            with self._transaction() as connection:
                row = connection.execute(
                    "SELECT public_key FROM authorities WHERE authority_id = ?",
                    (authority_id,),
                ).fetchone()
                if row is not None and row["public_key"] != public_key:
                    raise StorageError("Pinned authority key cannot be silently replaced")
                connection.execute(
                    "INSERT OR IGNORE INTO authorities (authority_id, public_key, status) "
                    "VALUES (?, ?, 'active')",
                    (authority_id, public_key),
                )
        except sqlite3.IntegrityError as error:
            raise StorageError("Unable to pin Authlite authority key") from error

    def verify_authority_key(self, authority_id: str, public_key: bytes) -> bool:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT public_key, status FROM authorities WHERE authority_id = ?",
                    (authority_id,),
                ).fetchone()
            except sqlite3.Error as error:
                raise StorageError("Unable to read pinned authority key") from error
        return row is not None and row["status"] == "active" and row["public_key"] == public_key

    def approve_enrollment(self, session_id: str, now: int) -> None:
        with self._transaction() as connection:
            result = connection.execute(
                "UPDATE pending_enrollments SET approved = 1 "
                "WHERE session_id = ? AND expires_at > ? AND approved = 0",
                (session_id, now),
            )
            if result.rowcount != 1:
                raise EnrollmentError("Enrollment session is missing or expired")
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, request_id, result, reason_code) "
                "VALUES (?, 'enrollment_approval', ?, 'approved', NULL)",
                (now, session_id),
            )

    def prepare_challenge(
        self,
        session_id: str,
        *,
        challenge: bytes,
        now: int,
        challenge_expires_at: int,
    ) -> None:
        with self._transaction() as connection:
            result = connection.execute(
                "UPDATE pending_enrollments SET challenge = ?, challenge_expires_at = ? "
                "WHERE session_id = ? AND approved = 1 AND expires_at > ? AND challenge IS NULL",
                (challenge, challenge_expires_at, session_id, now),
            )
            if result.rowcount != 1:
                raise EnrollmentError("Enrollment is not approved or has expired")

    def fail_enrollment(self, session_id: str, *, now: int, reason_code: str) -> None:
        """Consume an enrollment session after a local proof failure."""
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT session_id FROM pending_enrollments WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return
            connection.execute(
                "DELETE FROM pending_enrollments WHERE session_id = ?", (session_id,)
            )
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, request_id, result, reason_code) "
                "VALUES (?, 'enrollment_failure', ?, 'denied', ?)",
                (now, session_id, reason_code),
            )

    def complete_enrollment(self, session_id: str, *, signature_verified: bool, now: int) -> str:
        if not signature_verified:
            raise EnrollmentError("Enrollment challenge signature is invalid")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM pending_enrollments WHERE session_id = ? "
                "AND approved = 1 AND expires_at > ? AND challenge_expires_at > ?",
                (session_id, now, now),
            ).fetchone()
            if row is None or row["challenge"] is None:
                raise EnrollmentError("Enrollment challenge is missing or expired")
            device_id = "device-" + session_id
            connection.execute(
                "INSERT INTO devices (device_id, public_key, alias, device_type, status, enrolled_at) "
                "VALUES (?, ?, ?, ?, 'active', ?)",
                (device_id, row["public_key"], row["alias"], row["device_type"], now),
            )
            connection.execute(
                "INSERT INTO replay_state (device_id, last_sequence) VALUES (?, 0)",
                (device_id,),
            )
            connection.execute("DELETE FROM pending_enrollments WHERE session_id = ?", (session_id,))
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, device_id, request_id, result, reason_code) "
                "VALUES (?, 'enrollment_completion', ?, ?, 'completed', NULL)",
                (now, device_id, session_id),
            )
            return device_id

    def get_pending_enrollment(self, session_id: str, now: int) -> sqlite3.Row:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT * FROM pending_enrollments WHERE session_id = ? AND expires_at > ?",
                    (session_id, now),
                ).fetchone()
            except sqlite3.Error as error:
                raise StorageError("Unable to read pending enrollment") from error
        if row is None:
            raise EnrollmentError("Enrollment session is missing or expired")
        return row

    def get_device(self, device_id: str) -> sqlite3.Row:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT * FROM devices WHERE device_id = ?", (device_id,)
                ).fetchone()
            except sqlite3.Error as error:
                raise StorageError("Unable to read device registry") from error
        if row is None:
            raise UnknownDevice("Device is not enrolled")
        if row["status"] != "active":
            raise DeviceNotActive("Device is revoked or inactive")
        return row

    def set_capabilities(
        self,
        device_id: str,
        audience: str,
        capabilities: list[str],
        *,
        now: int,
    ) -> None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if row is None:
                raise UnknownDevice("Device is not enrolled")
            if row["status"] != "active":
                raise DeviceNotActive("Device is revoked or inactive")
            connection.execute(
                "DELETE FROM capabilities WHERE device_id = ? AND audience = ?",
                (device_id, audience),
            )
            connection.executemany(
                "INSERT INTO capabilities (device_id, audience, capability) VALUES (?, ?, ?)",
                [(device_id, audience, capability) for capability in sorted(set(capabilities))],
            )
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, device_id, request_id, capability, result, reason_code) "
                "VALUES (?, 'policy_update', ?, ?, ?, 'updated', NULL)",
                (now, device_id, audience, ",".join(sorted(set(capabilities)))[:512]),
            )

    def get_capabilities(self, device_id: str, audience: str) -> frozenset[str]:
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT capability FROM capabilities WHERE device_id = ? AND audience = ?",
                    (device_id, audience),
                ).fetchall()
            except sqlite3.Error as error:
                raise StorageError("Unable to read device policy") from error
        return frozenset(row["capability"] for row in rows)

    def token_is_revoked(self, token_id: str) -> bool:
        with self._lock:
            try:
                return self._connection.execute(
                    "SELECT 1 FROM revoked_tokens WHERE token_id = ?", (token_id,)
                ).fetchone() is not None
            except sqlite3.Error as error:
                raise StorageError("Unable to read token revocation state") from error

    def revoke_token(self, token_id: str, now: int) -> None:
        with self._transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO revoked_tokens (token_id, revoked_at) VALUES (?, ?)",
                (token_id, now),
            )
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, request_id, result, reason_code) "
                "VALUES (?, 'token_revocation', ?, 'revoked', NULL)",
                (now, token_id),
            )

    def revoke_device(self, device_id: str, now: int) -> None:
        with self._transaction() as connection:
            result = connection.execute(
                "UPDATE devices SET status = 'revoked' WHERE device_id = ?", (device_id,)
            )
            if result.rowcount != 1:
                raise UnknownDevice("Device is not enrolled")
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, device_id, result, reason_code) "
                "VALUES (?, 'device_revocation', ?, 'revoked', NULL)",
                (now, device_id),
            )

    def next_outgoing_sequence(self, device_id: str, peer_device_id: str) -> int:
        """Atomically allocate a monotonically increasing per-peer sequence."""
        with self._transaction() as connection:
            device = connection.execute(
                "SELECT status FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if device is None:
                raise UnknownDevice("Local device is not enrolled")
            if device["status"] != "active":
                raise DeviceNotActive("Local device is revoked or inactive")
            row = connection.execute(
                "SELECT last_sequence FROM outgoing_sequences "
                "WHERE device_id = ? AND peer_device_id = ?",
                (device_id, peer_device_id),
            ).fetchone()
            receiver = connection.execute(
                "SELECT status FROM devices WHERE device_id = ?", (peer_device_id,)
            ).fetchone()
            if receiver is None:
                raise UnknownDevice("Sequence destination is not enrolled")
            if receiver["status"] != "active":
                raise DeviceNotActive("Sequence destination is revoked or inactive")
            next_sequence = 1 if row is None else row["last_sequence"] + 1
            connection.execute(
                "INSERT INTO outgoing_sequences (device_id, peer_device_id, last_sequence) "
                "VALUES (?, ?, ?) ON CONFLICT(device_id, peer_device_id) "
                "DO UPDATE SET last_sequence = excluded.last_sequence",
                (device_id, peer_device_id, next_sequence),
            )
            return next_sequence

    def consume_request(
        self,
        *,
        device_id: str,
        audience: str,
        capability: str,
        request_id: str,
        nonce: str,
        token_id: str,
        token_expires_at: int,
        sequence: int,
        now: int,
        token_capabilities: frozenset[str],
        required_policy_capability: str,
    ) -> None:
        """Atomically enforce current policy and persist replay state before dispatch."""
        with self._transaction() as connection:
            device = connection.execute(
                "SELECT status FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if device is None:
                raise UnknownDevice("Device is not enrolled")
            if device["status"] != "active":
                raise DeviceNotActive("Device is revoked or inactive")
            if connection.execute(
                "SELECT 1 FROM revoked_tokens WHERE token_id = ?", (token_id,)
            ).fetchone() is not None:
                raise TokenError("Token has been revoked")
            if token_expires_at <= now:
                raise TokenError("Token expired before replay state was committed")
            allowed = connection.execute(
                "SELECT 1 FROM capabilities WHERE device_id = ? AND audience = ? AND capability = ?",
                (device_id, audience, required_policy_capability),
            ).fetchone()
            if allowed is None:
                raise MissingCapability("Device policy does not grant this capability")
            if required_policy_capability not in token_capabilities:
                raise MissingCapability("Token does not grant the registered operation")
            replay = connection.execute(
                "SELECT last_sequence FROM replay_state WHERE device_id = ?", (device_id,)
            ).fetchone()
            if replay is None or sequence <= replay["last_sequence"]:
                raise ReplayDetected("Request sequence is not newer than the last accepted sequence")
            connection.execute("DELETE FROM consumed_requests WHERE expires_at <= ?", (now,))
            try:
                connection.execute(
                    "INSERT INTO consumed_requests (device_id, request_id, nonce, token_id, expires_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (device_id, request_id, nonce, token_id, token_expires_at),
                )
            except sqlite3.IntegrityError as error:
                raise ReplayDetected("Request ID or nonce has already been used") from error
            connection.execute(
                "UPDATE replay_state SET last_sequence = ? WHERE device_id = ?",
                (sequence, device_id),
            )
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, device_id, request_id, capability, result, reason_code) "
                "VALUES (?, 'request_authorization', ?, ?, ?, 'accepted', NULL)",
                (now, device_id, request_id, capability),
            )

    def record_security_event(
        self,
        *,
        timestamp: int,
        event_type: str,
        device_id: str | None,
        request_id: str | None,
        capability: str | None = None,
        result: str,
        reason_code: str | None,
    ) -> None:
        """Persist a metadata-only security outcome, never packet contents."""
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO security_events "
                "(timestamp, event_type, device_id, request_id, capability, result, reason_code) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, event_type, device_id, request_id, capability, result, reason_code),
            )

    def read_security_events(self) -> list[dict]:
        """Return audit metadata for local administration/testing only."""
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT timestamp, event_type, device_id, request_id, capability, result, reason_code "
                    "FROM security_events ORDER BY event_id"
                ).fetchall()
            except sqlite3.Error as error:
                raise StorageError("Unable to read Authlite security audit events") from error
        return [dict(row) for row in rows]
