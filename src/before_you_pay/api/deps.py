"""FastAPI dependency injection providers."""

from functools import lru_cache

from before_you_pay.services.dealer_response_parser import DealerResponseParserService
from before_you_pay.services.multi_quote_comparison import MultiQuoteComparisonService
from before_you_pay.services.pipeline import PipelineService


@lru_cache
def get_pipeline_service() -> PipelineService:
    """Singleton provider for PipelineService and child engines."""
    return PipelineService()


@lru_cache
def get_multi_quote_comparison_service() -> MultiQuoteComparisonService:
    """Singleton provider for MultiQuoteComparisonService."""
    return MultiQuoteComparisonService()


@lru_cache
def get_dealer_response_parser_service() -> DealerResponseParserService:
    """Singleton provider for DealerResponseParserService."""
    return DealerResponseParserService()
