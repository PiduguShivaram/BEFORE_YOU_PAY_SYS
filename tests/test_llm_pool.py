"""Unit tests for GroqKeyManager failover key rotation pool."""

import httpx
import pytest
from groq import RateLimitError

from before_you_pay.services.llm_pool import AllApiKeysExhaustedError, GroqKeyManager


def test_key_manager_initialization():
    """Verify key pool loads keys and labels properly."""
    pool = GroqKeyManager(
        api_keys=["key_primary_12345678", "key_fallback_1_12345", "key_fallback_2_12345"],
        model="qwen/qwen3.8-27b",
    )
    assert pool.key_count == 3
    assert pool.active_key_index == 0
    assert pool.active_key_label == "PRIMARY"
    assert "..." in pool.get_masked_key(0)


def test_key_manager_successful_call():
    """Verify standard call executes without failover."""
    pool = GroqKeyManager(api_keys=["key1", "key2"], model="test-model")

    def mock_call(client, model):
        return f"result_from_{client.api_key}"

    result, label = pool.execute_with_failover(mock_call)
    assert result == "result_from_key1"
    assert label == "PRIMARY"
    assert pool.active_key_index == 0


def test_key_manager_quota_failover_to_fallback():
    """Verify HTTP 429 RateLimit triggers instant switch to Fallback 1."""
    pool = GroqKeyManager(api_keys=["primary_key", "fallback_key_1"], model="test-model")
    attempts = []

    def mock_call_failing_first(client, model):
        attempts.append(client.api_key)
        if client.api_key == "primary_key":
            # Simulate 429 RateLimitError
            response = httpx.Response(
                status_code=429,
                request=httpx.Request("POST", "https://api.groq.com"),
                json={"error": {"message": "Rate limit reached / quota exhausted"}},
            )
            raise RateLimitError("Rate limit reached", response=response, body=None)
        return "success_from_fallback"

    result, label = pool.execute_with_failover(mock_call_failing_first)
    assert result == "success_from_fallback"
    assert label == "FALLBACK_1"
    assert pool.active_key_index == 1
    assert attempts == ["primary_key", "fallback_key_1"]


def test_key_manager_all_keys_exhausted():
    """Verify AllApiKeysExhaustedError when all keys in pool hit rate limits."""
    pool = GroqKeyManager(api_keys=["key_1", "key_2"], model="test-model")

    def mock_always_exhausted(client, model):
        response = httpx.Response(
            status_code=429,
            request=httpx.Request("POST", "https://api.groq.com"),
            json={"error": {"message": "TPM / RPM quota exhausted"}},
        )
        raise RateLimitError("Quota exhausted", response=response, body=None)

    with pytest.raises(AllApiKeysExhaustedError):
        pool.execute_with_failover(mock_always_exhausted)
