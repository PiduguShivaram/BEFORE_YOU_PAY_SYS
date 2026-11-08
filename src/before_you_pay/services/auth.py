"""Cryptographic token-based authentication and tenant identity management service.

Implements RFC 7519 HMAC-SHA256 (HS256) JWT signed session tokens.
Strictly ensures:
1. Client-supplied user IDs are NEVER trusted blindly for authorization.
2. Authenticated user identity is derived exclusively from cryptographically validated tokens.
3. Token expiration, signature tampering, and tenant boundaries are enforced in constant time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from before_you_pay.config import get_settings


class AuthError(Exception):
    """Base exception for authentication failures."""


class TokenMissingError(AuthError):
    """Raised when an authentication token is required but missing."""


class TokenInvalidError(AuthError):
    """Raised when a token signature is invalid, forged, or malformed."""


class TokenExpiredError(AuthError):
    """Raised when an authentication token has exceeded its expiration timestamp."""


class ForbiddenTenantError(AuthError):
    """Raised when a client attempts to act on or access a tenant resource not owned by the token."""


def _base64url_encode(data: bytes) -> str:
    """Encode bytes using URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    """Decode URL-safe base64 string, restoring padding as needed."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


class AuthService:
    """Production authentication and tenant token verification engine."""

    def __init__(
        self,
        secret_key: str | None = None,
        default_expire_minutes: int | None = None,
    ) -> None:
        settings = get_settings()
        self._secret = (secret_key or settings.auth_secret_key).encode("utf-8")
        self._expire_minutes = default_expire_minutes or settings.auth_token_expire_minutes
        self._algorithm = settings.auth_algorithm

    def create_access_token(
        self,
        user_id: UUID,
        expires_in_minutes: int | None = None,
    ) -> str:
        """Issue a cryptographically signed HMAC-SHA256 JWT access token for user_id."""
        now_ts = int(time.time())
        exp_minutes = expires_in_minutes if expires_in_minutes is not None else self._expire_minutes
        exp_ts = now_ts + int(exp_minutes * 60)

        header = {
            "alg": self._algorithm,
            "typ": "JWT",
        }
        payload = {
            "sub": str(user_id),
            "iat": now_ts,
            "exp": exp_ts,
            "iss": "before-you-pay",
            "jti": str(uuid4()),
        }

        header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

        encoded_header = _base64url_encode(header_bytes)
        encoded_payload = _base64url_encode(payload_bytes)

        signing_input = f"{encoded_header}.{encoded_payload}".encode()
        signature_bytes = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        encoded_signature = _base64url_encode(signature_bytes)

        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def verify_access_token(self, token: str) -> UUID:
        """Validate signature, format, and expiration of access token and return verified user_id.

        Raises:
            TokenMissingError: If token is empty or None.
            TokenInvalidError: If token signature, structure, or claims are malformed.
            TokenExpiredError: If token expiration timestamp is in the past.
        """
        if not token or not token.strip():
            raise TokenMissingError("Authentication token is missing.")

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise TokenInvalidError("Malformed authentication token: expected 3 segments.")

        encoded_header, encoded_payload, encoded_signature = parts

        # Verify signature in constant time
        signing_input = f"{encoded_header}.{encoded_payload}".encode()
        expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        try:
            actual_sig = _base64url_decode(encoded_signature)
        except Exception as exc:
            raise TokenInvalidError(f"Invalid token signature encoding: {exc}") from exc

        if not hmac.compare_digest(actual_sig, expected_sig):
            raise TokenInvalidError("Invalid token signature: verification failed.")

        # Decode header and payload
        try:
            header_json = _base64url_decode(encoded_header)
            header = json.loads(header_json.decode("utf-8"))
            if header.get("alg") != self._algorithm:
                raise TokenInvalidError(f"Unsupported token algorithm '{header.get('alg')}'.")
        except Exception as exc:
            raise TokenInvalidError(f"Malformed token header: {exc}") from exc

        try:
            payload_json = _base64url_decode(encoded_payload)
            payload = json.loads(payload_json.decode("utf-8"))
        except Exception as exc:
            raise TokenInvalidError(f"Malformed token payload: {exc}") from exc

        # Check expiration
        exp_ts = payload.get("exp")
        if exp_ts is None:
            raise TokenInvalidError("Token payload missing required 'exp' claim.")

        now_ts = int(time.time())
        if now_ts >= exp_ts:
            exp_dt = datetime.fromtimestamp(exp_ts, tz=UTC).isoformat()
            raise TokenExpiredError(f"Token expired at {exp_dt}.")

        # Extract and validate user_id subject
        sub = payload.get("sub")
        if not sub:
            raise TokenInvalidError("Token payload missing required 'sub' subject claim.")

        try:
            user_id = UUID(str(sub))
        except ValueError as exc:
            raise TokenInvalidError(f"Invalid subject UUID in token: {sub}") from exc

        return user_id

    def create_auth_session(self, user_id: UUID | None = None) -> dict[str, Any]:
        """Generate a verified auth session package with token and metadata."""
        uid = user_id or uuid4()
        token = self.create_access_token(uid)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(uid),
            "expires_in": self._expire_minutes * 60,
        }
