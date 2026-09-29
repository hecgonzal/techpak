"""BrainBoard-issued, short-lived, audience-scoped Ed25519 tokens."""

from __future__ import annotations

import time
import uuid
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import canonical_bytes, decode_signature, encode_signature
from .errors import TokenError, WrongAudience

TOKEN_VERSION = 1
TOKEN_TTL_SECONDS = 3600
TOKEN_CLAIMS = frozenset({
    "token_version", "issuer", "subject", "audience", "capabilities",
    "issued_at", "expires_at", "token_id", "signature",
})


def issue_token(
    signing_key: Ed25519PrivateKey,
    *,
    issuer: str,
    subject: str,
    audience: str,
    capabilities: list[str],
    now: int | None = None,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> dict[str, Any]:
    issued_at = int(time.time()) if now is None else int(now)
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError("Token lifetime must be an integer number of seconds")
    if ttl_seconds <= 0 or ttl_seconds > TOKEN_TTL_SECONDS:
        raise ValueError("Token lifetime must be between 1 second and one hour")
    for field, value in (("issuer", issuer), ("subject", subject), ("audience", audience)):
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(f"Token {field} must be a non-empty string up to 256 characters")
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("A token must contain at least one capability")
    if not all(isinstance(value, str) and value and len(value) <= 256 for value in capabilities):
        raise ValueError("Token capabilities must be non-empty bounded strings")
    if len(set(capabilities)) != len(capabilities):
        raise ValueError("Token capabilities must be unique")
    claims = {
        "token_version": TOKEN_VERSION,
        "issuer": issuer,
        "subject": subject,
        "audience": audience,
        "capabilities": sorted(set(capabilities)),
        "issued_at": issued_at,
        "expires_at": issued_at + ttl_seconds,
        "token_id": str(uuid.uuid4()),
    }
    return {**claims, "signature": encode_signature(signing_key.sign(canonical_bytes(claims)))}


def verify_token(
    token: object,
    verification_key: Ed25519PublicKey,
    *,
    expected_issuer: str,
    expected_audience: str,
    now: int | None = None,
) -> dict[str, Any]:
    if not isinstance(token, dict):
        raise TokenError("Token must be an object")
    if set(token) != TOKEN_CLAIMS:
        raise TokenError("Token claims are missing or unexpected")
    claims = {key: value for key, value in token.items() if key != "signature"}
    if isinstance(claims["token_version"], bool) or claims["token_version"] != TOKEN_VERSION:
        raise TokenError("Unsupported token version")
    for field in ("issuer", "subject", "audience", "token_id"):
        if not isinstance(claims[field], str) or not claims[field] or len(claims[field]) > 256:
            raise TokenError(f"Token claim '{field}' is invalid")
    if claims["issuer"] != expected_issuer:
        raise TokenError("Token issuer is not trusted")
    if claims["audience"] != expected_audience:
        raise WrongAudience("Token is not intended for this service")
    if (
        not isinstance(claims["capabilities"], list)
        or not claims["capabilities"]
        or not all(
            isinstance(value, str) and value and len(value) <= 256
            for value in claims["capabilities"]
        )
        or len(claims["capabilities"]) > 128
        or len(set(claims["capabilities"])) != len(claims["capabilities"])
    ):
        raise TokenError("Token capabilities are invalid")
    issued_at = claims["issued_at"]
    expires_at = claims["expires_at"]
    if (
        isinstance(issued_at, bool)
        or isinstance(expires_at, bool)
        or not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
        or issued_at < 0
        or expires_at <= issued_at
        or expires_at - issued_at > TOKEN_TTL_SECONDS
    ):
        raise TokenError("Token lifetime claims are invalid")
    current_time = int(time.time()) if now is None else int(now)
    if issued_at > current_time + 30:
        raise TokenError("Token is not yet valid")
    if expires_at <= current_time:
        raise TokenError("Token has expired")
    try:
        verification_key.verify(decode_signature(token["signature"]), canonical_bytes(claims))
    except InvalidSignature as error:
        raise TokenError("Token signature is invalid") from error
    return claims
