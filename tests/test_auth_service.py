"""Unit tests for cryptographic AuthService and JWT token verification."""

import json
import time
from uuid import UUID, uuid4

import pytest

from before_you_pay.services.auth import (
    AuthService,
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingError,
    _base64url_encode,
)


class TestAuthServiceUnit:
    """Verifies RFC 7519 HS256 JWT encoding, signature verification, and expiration."""

    def test_create_and_verify_valid_token(self):
        auth = AuthService()
        uid = uuid4()
        token = auth.create_access_token(uid, expires_in_minutes=60)

        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        verified_uid = auth.verify_access_token(token)
        assert verified_uid == uid
        assert isinstance(verified_uid, UUID)

    def test_missing_or_empty_token_raises_missing_error(self):
        auth = AuthService()
        with pytest.raises(TokenMissingError):
            auth.verify_access_token("")

        with pytest.raises(TokenMissingError):
            auth.verify_access_token("   ")

    def test_malformed_token_segments_raises_invalid_error(self):
        auth = AuthService()
        with pytest.raises(TokenInvalidError) as exc_info:
            auth.verify_access_token("header.payload")
        assert "expected 3 segments" in str(exc_info.value)

        with pytest.raises(TokenInvalidError):
            auth.verify_access_token("one.two.three.four")

    def test_tampered_signature_raises_invalid_error(self):
        auth = AuthService()
        uid = uuid4()
        token = auth.create_access_token(uid)
        h, p, sig = token.split(".")

        # Tamper with signature
        tampered_sig = sig[:-4] + ("AAAA" if sig[-4:] != "AAAA" else "BBBB")
        with pytest.raises(TokenInvalidError) as exc_info:
            auth.verify_access_token(f"{h}.{p}.{tampered_sig}")
        assert "verification failed" in str(exc_info.value)

    def test_tampered_payload_raises_invalid_error(self):
        auth = AuthService()
        user_a = uuid4()
        user_b = uuid4()
        token_a = auth.create_access_token(user_a)
        h, _, sig_a = token_a.split(".")

        # Craft forged payload with user_b
        forged_payload = {
            "sub": str(user_b),
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": "before-you-pay",
        }
        forged_p_b64 = _base64url_encode(json.dumps(forged_payload).encode("utf-8"))

        with pytest.raises(TokenInvalidError):
            auth.verify_access_token(f"{h}.{forged_p_b64}.{sig_a}")

    def test_expired_token_raises_expired_error(self):
        auth = AuthService()
        uid = uuid4()
        # Expired 5 minutes ago
        expired_token = auth.create_access_token(uid, expires_in_minutes=-5)

        with pytest.raises(TokenExpiredError) as exc_info:
            auth.verify_access_token(expired_token)
        assert "expired at" in str(exc_info.value).lower()

    def test_unsupported_algorithm_rejected(self):
        auth = AuthService()
        header = {"alg": "none", "typ": "JWT"}
        payload = {"sub": str(uuid4()), "exp": int(time.time()) + 1000}
        h_b64 = _base64url_encode(json.dumps(header).encode("utf-8"))
        p_b64 = _base64url_encode(json.dumps(payload).encode("utf-8"))
        # Empty signature or arbitrary
        fake_token = f"{h_b64}.{p_b64}."
        with pytest.raises(TokenInvalidError):
            auth.verify_access_token(fake_token)

    def test_create_auth_session(self):
        auth = AuthService()
        uid = uuid4()
        session = auth.create_auth_session(uid)

        assert session["token_type"] == "bearer"
        assert session["user_id"] == str(uid)
        assert session["expires_in"] > 0
        assert isinstance(session["access_token"], str)

        verified_uid = auth.verify_access_token(session["access_token"])
        assert verified_uid == uid
