"""LLM API Key Pool Manager with Automatic Failover Rotation (Gemini & Groq).

Implements resilient key-rotation strictly for external API calls:
If Primary key hits HTTP 429 / RateLimitError / 503 Unavailable / Quota Exhaustion,
it instantly rotates to Fallback Key 1, then Fallback Key 2.
"""

import logging
from collections.abc import Callable
from typing import Any

import httpx

from before_you_pay.config import get_settings

logger = logging.getLogger(__name__)


class AllApiKeysExhaustedError(Exception):
    """Raised when all configured API keys have exhausted their quotas."""

    pass


class RateLimitError(Exception):
    """Raised when a specific API key encounters rate limits or service unavailability."""

    pass


class GeminiClient:
    """Lightweight HTTP client for Google Gemini API generateContent endpoint."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_content(
        self,
        model: str,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Call Gemini generateContent endpoint with JSON mode and structured error handling."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        with httpx.Client(timeout=35.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    return candidates[0]["content"]["parts"][0]["text"]
                return "{}"
            if resp.status_code in (429, 503):
                raise RateLimitError(f"HTTP {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return "{}"


class LlmKeyManager:
    """Manages a pool of LLM API keys (Gemini / Groq) with cascading failover on quota exhaustion."""

    def __init__(
        self,
        api_keys: list[str] | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = (provider or settings.llm_provider).lower()
        if api_keys is not None:
            self._keys = [k for k in api_keys if k and k.strip()]
        else:
            self._keys = settings.active_llm_api_keys

        if model is not None:
            self.model = model
        else:
            self.model = settings.gemini_model if "gemini" in self.provider else settings.groq_model

        self._current_index = 0
        self._exhausted_keys: set[int] = set()

        if not self._keys:
            logger.warning(
                "No %s API keys configured. LLM services will operate in offline/fallback mode.",
                self.provider.upper(),
            )

    @property
    def key_count(self) -> int:
        """Total number of configured API keys."""
        return len(self._keys)

    @property
    def active_key_index(self) -> int:
        """Current zero-based index of active key."""
        return self._current_index

    @property
    def active_key_label(self) -> str:
        """Human-readable label of current active key."""
        if not self._keys:
            return "NONE"
        if self._current_index == 0:
            return "PRIMARY"
        return f"FALLBACK_{self._current_index}"

    def get_masked_key(self, index: int) -> str:
        """Return masked key string for safe logging/UI."""
        if 0 <= index < len(self._keys):
            key = self._keys[index]
            if len(key) > 12:
                return f"{key[:6]}...{key[-4:]}"
            return "***"
        return "N/A"

    def get_client(self) -> GeminiClient:
        """Get API client initialized with the current active key."""
        if not self._keys:
            raise AllApiKeysExhaustedError(
                f"No {self.provider.upper()} API keys configured in pool."
            )
        current_key = self._keys[self._current_index]
        return GeminiClient(api_key=current_key)

    def rotate_to_next_key(self, reason: str = "Quota exhausted") -> int:
        """Rotate to next available key in the cascade."""
        if self.key_count <= 1:
            self._exhausted_keys.add(0)
            raise AllApiKeysExhaustedError(
                f"Primary {self.provider.upper()} API key exhausted ({reason}) and no fallback keys configured."
            )

        self._exhausted_keys.add(self._current_index)
        next_index = (self._current_index + 1) % self.key_count

        if len(self._exhausted_keys) >= self.key_count:
            logger.error(
                "All %d %s API keys in the pool have been exhausted.",
                self.key_count,
                self.provider.upper(),
            )
            raise AllApiKeysExhaustedError(
                f"All {self.key_count} {self.provider.upper()} API keys in the failover pool are exhausted."
            )

        old_label = self.active_key_label
        self._current_index = next_index
        new_label = self.active_key_label

        logger.warning(
            "API KEY FAILOVER: %s (%s) %s -> Switched to %s (%s)",
            old_label,
            self.get_masked_key((next_index - 1) % self.key_count),
            reason,
            new_label,
            self.get_masked_key(next_index),
        )
        return self._current_index

    def execute_with_failover(self, call_fn: Callable[[Any, str], Any]) -> tuple[Any, str]:
        """Execute an API call with automatic key rotation on quota / rate limit errors.

        Returns:
            tuple: (result, active_key_label_used)
        """
        if not self._keys:
            raise AllApiKeysExhaustedError(f"No {self.provider.upper()} API keys configured.")

        attempts = 0
        max_attempts = self.key_count

        while attempts < max_attempts:
            client = self.get_client()
            current_label = self.active_key_label
            try:
                result = call_fn(client, self.model)
                return result, current_label
            except Exception as exc:
                err_msg = str(exc).lower()
                is_rate_limit = (
                    isinstance(exc, RateLimitError)
                    or "rate limit" in err_msg
                    or "quota" in err_msg
                    or "resource_exhausted" in err_msg
                    or "429" in err_msg
                    or "503" in err_msg
                    or "unavailable" in err_msg
                )

                if is_rate_limit:
                    attempts += 1
                    logger.warning("Quota / Rate Limit error on %s: %s", current_label, str(exc))
                    try:
                        self.rotate_to_next_key(reason=f"Quota / RateLimit: {exc}")
                    except AllApiKeysExhaustedError:
                        raise
                else:
                    raise

        raise AllApiKeysExhaustedError(
            f"Exhausted all {self.key_count} keys without successful completion."
        )


# Aliases for compatibility
GroqKeyManager = LlmKeyManager
GeminiKeyManager = LlmKeyManager

_global_pool: LlmKeyManager | None = None


def get_llm_key_manager() -> LlmKeyManager:
    """Singleton getter for the LlmKeyManager."""
    global _global_pool
    if _global_pool is None:
        _global_pool = LlmKeyManager()
    return _global_pool


def get_groq_key_manager() -> LlmKeyManager:
    """Compatibility alias."""
    return get_llm_key_manager()


def get_gemini_key_manager() -> LlmKeyManager:
    """Singleton getter for the GeminiKeyManager."""
    return get_llm_key_manager()
