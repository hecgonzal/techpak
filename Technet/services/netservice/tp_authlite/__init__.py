"""Techpack Authlite in-process MVP.

This package provides packet cryptography and receiver-side authorization only.
It does not create a network connection, TLS certificate, or production enrollment
hardware provider.
"""

from .authlite import (
    Authlite,
    DevelopmentCallbackConfirmation,
    DevelopmentCLIConfirmation,
    PhysicalConfirmationProvider,
)
from .dispatcher import AuthenticatedDispatcher
from .errors import (
    AuthliteError,
    DeviceNotActive,
    EnrollmentError,
    MissingCapability,
    PacketError,
    ReplayDetected,
    ServiceNotFound,
    SignatureError,
    StorageError,
    TokenError,
    UnknownDevice,
    WrongAudience,
)
from .keys import FileKeyStore
from .canonical import parse_packet
from .packet import (
    build_request_packet,
    build_response_packet,
    verify_request_signature,
    verify_response_packet,
)
from .storage import SQLiteAuthStore
from .tokens import issue_token, verify_token

__all__ = [
    "Authlite",
    "AuthenticatedDispatcher",
    "AuthliteError",
    "DevelopmentCallbackConfirmation",
    "DevelopmentCLIConfirmation",
    "DeviceNotActive",
    "EnrollmentError",
    "FileKeyStore",
    "MissingCapability",
    "PacketError",
    "PhysicalConfirmationProvider",
    "ReplayDetected",
    "SQLiteAuthStore",
    "ServiceNotFound",
    "SignatureError",
    "StorageError",
    "TokenError",
    "UnknownDevice",
    "WrongAudience",
    "build_request_packet",
    "build_response_packet",
    "issue_token",
    "parse_packet",
    "verify_request_signature",
    "verify_response_packet",
    "verify_token",
]
