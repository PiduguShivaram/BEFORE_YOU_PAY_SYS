"""API request and response schemas for Before You Pay."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response model for system health check endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="ok", description="Service health state")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Software version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Server timestamp in UTC",
    )
    gemini_configured: bool = Field(
        default=False, description="Whether Gemini provider keys are loaded"
    )
    groq_configured: bool = Field(
        default=False, description="Whether Groq provider keys are loaded"
    )
    llm_provider: str = Field(default="gemini", description="Configured primary LLM provider")
    rag_retrieval_mode: str = Field(
        default="deterministic_sqlite_token_overlap",
        description="RAG retrieval mechanism",
    )
