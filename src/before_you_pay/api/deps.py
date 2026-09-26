"""FastAPI dependency injection providers."""

from functools import lru_cache

from before_you_pay.services.pipeline import PipelineService


@lru_cache
def get_pipeline_service() -> PipelineService:
    """Singleton provider for PipelineService and child engines."""
    return PipelineService()
