"""Typed failures raised by the Authlite prototype."""


class AuthliteError(Exception):
    """Base class for safe-to-report authentication failures."""

    code = "auth_error"

    def __init__(self, message: str = "Request rejected") -> None:
        super().__init__(message)
        self.message = message


class PacketError(AuthliteError):
    code = "malformed_packet"


class UnknownDevice(AuthliteError):
    code = "unknown_device"


class DeviceNotActive(AuthliteError):
    code = "device_not_active"


class TokenError(AuthliteError):
    code = "invalid_token"


class WrongAudience(AuthliteError):
    code = "wrong_audience"


class MissingCapability(AuthliteError):
    code = "missing_capability"


class ReplayDetected(AuthliteError):
    code = "replay_detected"


class EnrollmentError(AuthliteError):
    code = "enrollment_error"


class StorageError(AuthliteError):
    code = "protected_storage_error"


class SignatureError(AuthliteError):
    code = "invalid_signature"


class ServiceNotFound(AuthliteError):
    code = "service_not_found"
