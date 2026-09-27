"""Services module for Before You Pay."""

from before_you_pay.services.cost_reduction import PotentialCostReductionService
from before_you_pay.services.cost_review_questions import CostReviewQuestionsService
from before_you_pay.services.extraction import FinancialExtractionEngine
from before_you_pay.services.extra_cost_analysis import ExtraCostAnalysisService
from before_you_pay.services.ocr import SpatialOcrEngine
from before_you_pay.services.okf import OkfCatalogService
from before_you_pay.services.pipeline import PipelineService
from before_you_pay.services.plain_language_explanation import PlainLanguageExplanationService
from before_you_pay.services.precondition import PreconditionChecker, PreconditionResult
from before_you_pay.services.rag import SqliteRagService
from before_you_pay.services.reasoning import SemanticReasoningEngine
from before_you_pay.services.result import ResultAggregatorService
from before_you_pay.services.smart_questions import SmartCostReductionQuestionsService
from before_you_pay.services.validation import DeterministicValidationEngine

__all__ = [
    "PreconditionChecker",
    "PreconditionResult",
    "SpatialOcrEngine",
    "FinancialExtractionEngine",
    "ExtraCostAnalysisService",
    "CostReviewQuestionsService",
    "SmartCostReductionQuestionsService",
    "PotentialCostReductionService",
    "PlainLanguageExplanationService",
    "SqliteRagService",
    "OkfCatalogService",
    "DeterministicValidationEngine",
    "SemanticReasoningEngine",
    "ResultAggregatorService",
    "PipelineService",
]

