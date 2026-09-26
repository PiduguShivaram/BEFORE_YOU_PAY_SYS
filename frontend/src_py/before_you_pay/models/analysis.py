"""Analysis, validation, RAG evidence, OKF rules, and decision result models."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_you_pay.models.document import (
    BoundingBox,
    DocumentClassification,
    OcrLine,
    StructuredFinancialDocument,
)

STANDARD_DISCLAIMER = (
    "This analysis provides automated decision support based on scanned text and user records. "
    "It does not constitute legal, tax, or financial advice. The final payment decision rests with you."
)

DISALLOWED_PHRASES_PATTERN = re.compile(
    r"\b(scam|fraud|illegal|definitely buy|definitely not buy)\b",
    re.IGNORECASE,
)


class StandardError(BaseModel):
    """Standardized error envelope across all API endpoints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnalysisState(StrEnum):
    """Explicit lifecycle states separating extraction findings from OCR quality."""

    FINANCIAL_DATA_FOUND = "FINANCIAL_DATA_FOUND"
    NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR = "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR"
    OCR_UNRELIABLE = "OCR_UNRELIABLE"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    EXTRACTION_INCONCLUSIVE = "EXTRACTION_INCONCLUSIVE"


class OCRQualityStatus(StrEnum):
    """Deterministic OCR recognition quality status."""

    GOOD = "GOOD"
    MODERATE = "MODERATE"
    DEGRADED = "DEGRADED"
    UNRELIABLE = "UNRELIABLE"


class OCRQualityResult(BaseModel):
    """Deterministic assessment of OCR line plausibility, density, and garbage ratios."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: OCRQualityStatus
    score: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    line_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    alphanumeric_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    garbage_token_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class ValidationStatus(StrEnum):
    """Result status of a deterministic validation check."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class ValidationSeverity(StrEnum):
    """Severity classification of validation findings."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ClaimType(StrEnum):
    """Allowed semantic claim classifications (non-committal language)."""

    POTENTIAL_ISSUE = "potential_issue"
    POTENTIAL_OVERLAP = "potential_overlap"
    REQUIRES_VERIFICATION = "requires_verification"
    ADDITIONAL_CHARGE_DETECTED = "additional_charge_detected"
    TERM_REQUIRING_ATTENTION = "term_requiring_attention"


class DecisionStatus(StrEnum):
    """Overall status assessment for the user."""

    CLEAR = "CLEAR"
    REQUIRES_ATTENTION = "REQUIRES_ATTENTION"
    DISCREPANCY_DETECTED = "DISCREPANCY_DETECTED"
    CRITICAL_WARNING = "CRITICAL_WARNING"


class RagEvidenceChunk(BaseModel):
    """Retrieved evidence chunk from user's historical document store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    source_document_id: UUID
    source_document_type: DocumentClassification = Field(default=DocumentClassification.OTHER)
    page_number: int = Field(..., ge=1)
    source_text: str = Field(..., min_length=1)
    bounding_box: BoundingBox | None = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class RagQuery(BaseModel):
    """Query parameters for retrieving context from user historical documents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: UUID
    current_document_id: UUID
    query_text: str = Field(..., min_length=1)
    document_types: list[DocumentClassification] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0.50, ge=0.0, le=1.0)


class OkfCategory(StrEnum):
    """Categories of curated Open Knowledge Format entries."""

    DEFINITION = "definition"
    DOCUMENT_CONCEPT = "document_concept"
    VERIFICATION_RULE = "verification_rule"
    COMPARISON_RULE = "comparison_rule"
    TERMINOLOGY = "terminology"
    DOMAIN_GUIDANCE = "domain_guidance"


class OkfRuleEvidence(BaseModel):
    """Curated knowledge entry from Open Knowledge Format catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., min_length=3)
    rule_name: str = Field(..., min_length=1)
    category: OkfCategory
    summary: str = Field(..., min_length=1)
    source_reference: str = Field(..., min_length=1)
    version: str = Field(default="1.0.0")
    guidance: str = Field(..., min_length=1)


class OkfQuery(BaseModel):
    """Query parameters to filter the curated OKF catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_type: DocumentClassification = Field(default=DocumentClassification.OTHER)
    categories: list[OkfCategory] = Field(default_factory=list)
    concept_keywords: list[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    """Result of an independent, deterministic arithmetic or constraint check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    validation_id: UUID = Field(default_factory=uuid4)
    check_code: str = Field(..., min_length=3)
    status: ValidationStatus
    input_field_ids: list[UUID] = Field(..., min_length=1)
    expected_value: Any | None = None
    calculated_value: Any | None = None
    absolute_delta: float | None = Field(default=None, ge=0.0)
    severity: ValidationSeverity = Field(default=ValidationSeverity.WARNING)
    message: str = Field(..., min_length=1)


class ReasoningClaim(BaseModel):
    """Semantic finding grounded by referencing field, RAG, OKF, or validation IDs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: UUID = Field(default_factory=uuid4)
    type: ClaimType
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    field_references: list[UUID] = Field(default_factory=list)
    rag_evidence_references: list[UUID] = Field(default_factory=list)
    okf_rule_references: list[str] = Field(default_factory=list)
    validation_references: list[UUID] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: ValidationSeverity = Field(default=ValidationSeverity.WARNING)

    @model_validator(mode="after")
    def validate_grounding_and_tone(self) -> "ReasoningClaim":
        total_refs = (
            len(self.field_references)
            + len(self.rag_evidence_references)
            + len(self.okf_rule_references)
            + len(self.validation_references)
        )
        if total_refs == 0:
            raise ValueError(
                "ReasoningClaim cannot be an orphan; must cite at least one reference."
            )

        text_to_check = f"{self.title} {self.description}"
        match = DISALLOWED_PHRASES_PATTERN.search(text_to_check)
        if match:
            raise ValueError(
                f"ReasoningClaim contains prohibited language '{match.group(0)}'. "
                "The system must use neutral classifications ('potential_issue', 'requires_verification')."
            )
        return self


class DecisionFlag(BaseModel):
    """Actionable notification card presented on the mobile screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    flag_id: UUID = Field(default_factory=uuid4)
    claim_type: ClaimType
    label: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    severity: ValidationSeverity = Field(default=ValidationSeverity.WARNING)
    associated_claim_id: UUID | None = None
    associated_validation_id: UUID | None = None
    field_ids: list[UUID] = Field(default_factory=list)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)


class ResultSummary(BaseModel):
    """High-level summary of document analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str = Field(..., min_length=1)
    overall_status: DecisionStatus
    total_flags: int = Field(..., ge=0)
    requires_human_verification: bool = Field(default=True)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None


class FinalDecisionSupportResult(BaseModel):
    """Complete, evidence-backed decision support payload returned to the user."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    user_id: UUID
    summary: ResultSummary
    flags: list[DecisionFlag] = Field(default_factory=list)
    reasoning_claims: list[ReasoningClaim] = Field(default_factory=list)
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    document: StructuredFinancialDocument | None = None
    raw_ocr_lines: list[str] = Field(default_factory=list)
    ocr_lines: list[OcrLine] = Field(default_factory=list)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
