"""Regression test suite for CORS_ORIGINS configuration parsing."""

import os
from unittest import mock

from before_you_pay.config import Settings


def test_cors_origins_default():
    """Verify default CORS origins is ['*'] when unset."""
    with mock.patch.dict(os.environ, {}, clear=False):
        if "CORS_ORIGINS" in os.environ:
            del os.environ["CORS_ORIGINS"]
        settings = Settings(_env_file=None)
        assert settings.cors_origins == ["*"]
        assert isinstance(settings.cors_origins, list)


def test_cors_origins_json_array():
    """Verify JSON array formatted CORS_ORIGINS parses correctly."""
    with mock.patch.dict(
        os.environ,
        {"CORS_ORIGINS": '["https://before-you-pay-sys.vercel.app", "http://localhost:3000"]'},
    ):
        settings = Settings()
        assert settings.cors_origins == [
            "https://before-you-pay-sys.vercel.app",
            "http://localhost:3000",
        ]
        assert isinstance(settings.cors_origins, list)


def test_cors_origins_single_url():
    """Verify single URL string without JSON brackets parses cleanly without error."""
    with mock.patch.dict(os.environ, {"CORS_ORIGINS": "https://before-you-pay-sys.vercel.app"}):
        settings = Settings()
        assert settings.cors_origins == ["https://before-you-pay-sys.vercel.app"]
        assert isinstance(settings.cors_origins, list)


def test_cors_origins_comma_separated():
    """Verify comma-separated URLs parse cleanly into list."""
    with mock.patch.dict(
        os.environ, {"CORS_ORIGINS": "http://localhost:3000, https://before-you-pay-sys.vercel.app"}
    ):
        settings = Settings()
        assert settings.cors_origins == [
            "http://localhost:3000",
            "https://before-you-pay-sys.vercel.app",
        ]
        assert isinstance(settings.cors_origins, list)


def test_cors_origins_wildcard_string():
    """Verify wildcard string '*' parses cleanly into ['*']."""
    with mock.patch.dict(os.environ, {"CORS_ORIGINS": "*"}):
        settings = Settings()
        assert settings.cors_origins == ["*"]
        assert isinstance(settings.cors_origins, list)


def test_cors_origins_empty_string():
    """Verify empty or whitespace string falls back to ['*']."""
    with mock.patch.dict(os.environ, {"CORS_ORIGINS": "   "}):
        settings = Settings()
        assert settings.cors_origins == ["*"]
        assert isinstance(settings.cors_origins, list)


def test_empty_environment_variables_fallback_to_defaults():
    """Verify empty string env vars (e.g. from blank Vercel env fields) use declared defaults."""
    env_overrides = {
        "APP_ENV": "",
        "APP_PORT": "",
        "DEBUG": "",
        "MAX_UPLOAD_SIZE_MB": "",
        "RAG_DEFAULT_TOP_K": "",
        "RAG_SIMILARITY_THRESHOLD": "",
    }
    with mock.patch.dict(os.environ, env_overrides):
        settings = Settings(_env_file=None)
        assert settings.app_env == "development"
        assert settings.app_port == 8000
        assert settings.debug is False
        assert settings.max_upload_size_mb == 25
        assert settings.rag_default_top_k == 5
        assert settings.rag_similarity_threshold == 0.30
