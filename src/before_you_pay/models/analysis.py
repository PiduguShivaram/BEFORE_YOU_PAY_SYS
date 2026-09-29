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
    r"\b(scam|fraud|cheat|scammer|illegal"
    r"|good deal|bad deal|safe to pay|unsafe to pay|safe to buy|unsafe to buy"
    r"|guaranteed savings|definitely save|you will save"
    r"|buy this|don't buy this|do not buy this|definitely buy|definitely not buy"
    r"|should buy|should not buy|you should buy|you should not buy)\b",
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

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> "DecisionFlag":
        text_to_check = f"{self.label} {self.message}"
        match = DISALLOWED_PHRASES_PATTERN.search(text_to_check)
        if match:
            raise ValueError(
                f"DecisionFlag contains prohibited language '{match.group(0)}'. "
                "Use neutral, non-committal language."
            )
        return self


class ResultSummary(BaseModel):
    """High-level summary of document analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str = Field(..., min_length=1)
    overall_status: DecisionStatus
    total_flags: int = Field(..., ge=0)
    requires_human_verification: bool = Field(default=True)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> "ResultSummary":
        match = DISALLOWED_PHRASES_PATTERN.search(self.headline)
        if match:
            raise ValueError(
                f"ResultSummary contains prohibited language '{match.group(0)}'. "
                "Use neutral, non-committal language."
            )
        return self


class SmartCostReductionQuestion(BaseModel):
    """Practical, evidence-grounded question for the buyer to ask the seller.

    Phase 5 Specification:
    1. Question
    2. Reason
    3. Related charge
    4. Amount involved
    5. Potential impact if removed/reduced
    6. Evidence source
    7. Confidence
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: UUID = Field(default_factory=uuid4)
    question: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    related_charge: str = Field(..., min_length=1)
    amount_involved: float | None = None
    potential_impact: str = Field(..., min_length=1)
    evidence_source: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    category: str | None = None
    priority_score: float = Field(default=0.0, ge=0.0)
    ranking_factors: dict[str, float] = Field(default_factory=dict)
    classification: str | None = None
    potential_amount_to_review: float | None = None
    requires_verification: bool = Field(default=True)
    suggested_action: str | None = None
    document_id: UUID | None = None
    page_number: int | None = None
    ocr_line: str | None = None
    bounding_box: BoundingBox | None = None

    @model_validator(mode="after")
    def validate_tone_and_guardrails(self) -> "SmartCostReductionQuestion":
        text_to_check = f"{self.question} {self.reason} {self.potential_impact}"
        match = DISALLOWED_PHRASES_PATTERN.search(text_to_check)
        if match:
            raise ValueError(
                f"SmartCostReductionQuestion contains prohibited language '{match.group(0)}'. "
                "Questions must maintain a neutral, factual discovery tone."
            )
        generic_patterns = [
            r"can you give me a discount",
            r"give me a discount",
            r"can i get a discount",
            r"any discount",
        ]
        q_lower = self.question.lower().strip()
        for p in generic_patterns:
            if re.search(r"\b" + p + r"\b", q_lower):
                raise ValueError(
                    f"Generic questions like '{p}' are prohibited. "
                    "Questions must be connected to an actual document finding."
                )
        return self


PROHIBITED_SAVINGS_PATTERN = re.compile(
    r"\b(you can save|will save|guaranteed savings?|savings? promise)\b",
    re.IGNORECASE,
)


class ReductionTierItem(BaseModel):
    """An individual charge item evaluated for potential cost reduction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0.0)
    category: str = Field(..., min_length=1)
    status_label: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)


class PotentialCostReductionSummary(BaseModel):
    """Phase 7: Potential Cost Reduction Summary without promising savings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    confirmed_optional_amount: float = Field(default=0.0, ge=0.0)
    confirmed_optional_items: list[ReductionTierItem] = Field(default_factory=list)

    potentially_optional_amount: float = Field(default=0.0, ge=0.0)
    potentially_optional_items: list[ReductionTierItem] = Field(default_factory=list)

    unclear_confirmation_amount: float = Field(default=0.0, ge=0.0)
    unclear_confirmation_items: list[ReductionTierItem] = Field(default_factory=list)

    min_potential_reduction: float = Field(default=0.0, ge=0.0)
    max_potential_reduction: float = Field(default=0.0, ge=0.0)
    potential_range_display: str = Field(default="₹0")

    review_message: str = Field(
        default="You may be able to reduce the quoted amount if the seller confirms these charges are optional or removable."
    )
    is_range_valid: bool = Field(default=True)
    total_charges_reviewed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_wording_guardrails(self) -> "PotentialCostReductionSummary":
        text_to_check = f"{self.review_message} {self.potential_range_display}"
        for item in (
            self.confirmed_optional_items
            + self.potentially_optional_items
            + self.unclear_confirmation_items
        ):
            text_to_check += f" {item.name} {item.status_label} {item.evidence}"

        match = PROHIBITED_SAVINGS_PATTERN.search(text_to_check)
        if match:
            raise ValueError(
                f"PotentialCostReductionSummary contains prohibited savings promise '{match.group(0)}'. "
                "The system must NEVER state 'You can save ₹X' or promise savings."
            )
        return self


class PlainLanguageExplanation(BaseModel):
    """Phase 8: Plain-Language Financial Explanation derived purely from extracted evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quoted_amount_sentence: str = Field(..., min_length=1)
    base_price_sentence: str = Field(..., min_length=1)
    charge_breakdown_sentences: list[str] = Field(default_factory=list)
    offers_sentence: str | None = None
    discrepancy_sentence: str | None = None
    clarification_heading: str = Field(default="Before paying, clarify these items:")
    clarification_items: list[str] = Field(default_factory=list)
    suggested_negotiation_message: str | None = None
    full_explanation: str = Field(..., min_length=1)


class ContextualFindingType(StrEnum):
    """Type of cross-document contextual finding."""

    POTENTIAL_OVERLAP = "POTENTIAL_OVERLAP"
    PRICE_VARIANCE = "PRICE_VARIANCE"
    COVERAGE_COMPARISON = "COVERAGE_COMPARISON"
    TERM_DIFFERENCE = "TERM_DIFFERENCE"
    NO_RELEVANT_CONTEXT = "NO_RELEVANT_CONTEXT"


class ContextualEvidence(BaseModel):
    """Evidence item from a specific document contributing to a contextual finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_role: str = Field(..., description="'primary' or 'supporting'")
    document_id: UUID
    source_document_type: str
    raw_text: str = Field(..., min_length=1)
    page_number: int = Field(default=1, ge=1)
    bounding_box: BoundingBox | None = None
    amount: float | None = None
    label: str | None = None


class ContextualFinding(BaseModel):
    """Phase 2: Cross-document contextual finding with full evidence provenance.

    Language is uncertainty-aware and non-committal. The system may identify
    potential overlaps or differences but must never declare outcomes without
    user verification.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: UUID = Field(default_factory=uuid4)
    finding_type: ContextualFindingType
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    primary_evidence: list[ContextualEvidence] = Field(default_factory=list)
    supporting_evidence: list[ContextualEvidence] = Field(default_factory=list)
    what_to_verify: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: ValidationSeverity = Field(default=ValidationSeverity.INFO)
    primary_amount: float | None = None
    supporting_amount: float | None = None
    delta_amount: float | None = None

    @model_validator(mode="after")
    def validate_language_guardrails(self) -> "ContextualFinding":
        prohibited = re.compile(
            r"\b(duplicate|unnecessary|fraudulent|scam|illegal|definitely removable|do not need)\b",
            re.IGNORECASE,
        )
        text = f"{self.title} {self.description} {' '.join(self.what_to_verify)} {' '.join(self.questions_to_ask)}"
        m = prohibited.search(text)
        if m:
            raise ValueError(
                f"ContextualFinding contains prohibited language '{m.group(0)}'. "
                "Use uncertainty-aware language: 'potential overlap', 'appears related', 'requires verification'."
            )
        return self


class SupportingDocumentAnalysis(BaseModel):
    """Metadata and contextual findings from supporting document analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supporting_document_id: UUID
    supporting_document_type: str
    supporting_line_count: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    supporting_preview: str | None = None
    findings: list[ContextualFinding] = Field(default_factory=list)
    retrieved_chunks_count: int = Field(default=0, ge=0)


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
    extra_cost_analysis: dict[str, Any] | None = Field(default=None)
    smart_questions: list[SmartCostReductionQuestion] = Field(default_factory=list)
    cost_reduction_summary: PotentialCostReductionSummary | None = None
    plain_language_explanation: PlainLanguageExplanation | None = None
    suggested_negotiation_message: str | None = Field(default=None)
    supporting_document_context: dict[str, Any] | None = Field(default=None)
    contextual_findings: list[ContextualFinding] = Field(default_factory=list)
    supporting_document_analysis: SupportingDocumentAnalysis | None = Field(default=None)
    raw_ocr_lines: list[str] = Field(default_factory=list)
    ocr_lines: list[OcrLine] = Field(default_factory=list)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None
    semantic_financial_structure: dict[str, Any] | None = Field(default=None)
    before_you_pay_summary: dict[str, Any] | None = Field(default=None)
    evidence_first_result: dict[str, Any] | None = Field(default=None)
    pipeline_metrics: dict[str, Any] | None = Field(default=None)
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
