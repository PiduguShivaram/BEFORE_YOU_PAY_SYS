"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Before You Pay backend service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Basics
    app_name: str = "Before You Pay"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Document Ingestion Limits
    max_upload_size_mb: int = 25

    # OCR Engine Config
    ocr_engine: str = "spatial_layout_ocr"

    # User Document RAG Store Config
    rag_default_top_k: int = 5
    rag_similarity_threshold: float = 0.30

    # OKF Catalog Configuration
    okf_catalog_path: str = "./data/okf"
    okf_schema_version: str = "1.0.0"

    # LLM & Inference Engine with Failover API Key Pool (Gemini / Groq)
    llm_provider: str = "gemini"
    gemini_api_key_primary: str | None = None
    gemini_api_key_fallback_1: str | None = None
    gemini_api_key_fallback_2: str | None = None
    gemini_model: str = "gemini-flash-lite-latest"

    groq_api_key_primary: str | None = None
    groq_api_key_fallback_1: str | None = None
    groq_api_key_fallback_2: str | None = None
    groq_model: str = "qwen/qwen3.8-27b"

    @property
    def gemini_api_keys(self) -> list[str]:
        """Return non-empty Gemini keys in cascading priority order."""
        keys = [
            self.gemini_api_key_primary,
            self.gemini_api_key_fallback_1,
            self.gemini_api_key_fallback_2,
        ]
        return [k for k in keys if k and k.strip()]

    @property
    def groq_api_keys(self) -> list[str]:
        """Return non-empty Groq keys in cascading priority order."""
        keys = [
            self.groq_api_key_primary,
            self.groq_api_key_fallback_1,
            self.groq_api_key_fallback_2,
        ]
        return [k for k in keys if k and k.strip()]

    @property
    def active_llm_api_keys(self) -> list[str]:
        """Return active LLM provider keys in cascading priority order."""
        if self.gemini_api_keys:
            return self.gemini_api_keys
        return self.groq_api_keys


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
