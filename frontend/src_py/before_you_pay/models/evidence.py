"""Phase 7: Evidence-First Explainability Models.

Provides the canonical evidence traceability structures for the
Before You Pay decision-support system.

Every finding, explanation, and question traces back to:
DOCUMENT → OCR EVIDENCE → EXTRACTED FIELD → FINANCIAL COMPONENT → SEMANTIC INTERPRETATION → DETERMINISTIC VALIDATION → FINDING → EXPLANATION → QUESTION → ACTION
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceType(StrEnum):
    """Canonical evidence type classification.

    Distinguishes between literal document text, AI interpretation,
    deterministic calculations, and curated knowledge.
    """

    DOCUMENT_TEXT = "DOCUMENT_TEXT"
    OCR_TEXT = "OCR_TEXT"
    EXTRACTED_VALUE = "EXTRACTED_VALUE"
    SEMANTIC_CLASSIFICATION = "SEMANTIC_CLASSIFICATION"
    DETERMINISTIC_CALCULATION = "DETERMINISTIC_CALCULATION"
    SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT"
    CROSS_DOCUMENT_COMPARISON = "CROSS_DOCUMENT_COMPARISON"
    AUTHORITATIVE_KNOWLEDGE = "AUTHORITATIVE_KNOWLEDGE"


class ConfidenceLevel(StrEnum):
    """Confidence level for evidence and interpretations."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    REQUIRES_VERIFICATION = "Requires verification"


class ExplanationSection(StrEnum):
    """Canonical explanation sections for evidence-first explainability."""

    WHAT_WE_KNOW = "WHAT WE KNOW"
    WHAT_WE_INFER = "WHAT WE INFER"
    WHAT_REMAINS_UNCERTAIN = "WHAT REMAINS UNCERTAIN"
    ACTION = "ACTION"
    EVIDENCE = "EVIDENCE"


class EvidenceItem(BaseModel):
    """A single evidence item with full provenance traceability.

    Every evidence item traces back to its source in the document
    and includes the interpretation chain.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    evidence_type: EvidenceType
    source_document_id: UUID
    source_document_role: str = "primary"  # "primary" or "supporting"
    page_number: int | None = None
    ocr_line_id: UUID | None = None
    field_id: UUID | None = None
    component_id: UUID | None = None
    validation_id: UUID | None = None
    finding_id: UUID | None = None

    # Content
    original_text: str | None = None
    interpreted_as: str | None = None
    extracted_value: float | None = None
    normalized_label: str | None = None
    semantic_category: str | None = None

    # Provenance
    bounding_box: dict[str, Any] | None = None
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    uncertainty_reason: str | None = None

    # Calculation (for DETERMINISTIC_CALCULATION type)
    calculation_inputs: dict[str, Any] | None = None
    calculation_expected: float | None = None
    calculation_document_result: float | None = None
    calculation_delta: float | None = None
    calculation_status: str | None = None  # "PASS", "FAIL", "INCONCLUSIVE"

    # Supporting document comparison
    supporting_document_id: UUID | None = None
    supporting_text: str | None = None
    supporting_amount: float | None = None
    comparison_result: str | None = None

    # Authoritative knowledge
    okf_rule_id: str | None = None
    okf_rule_version: str | None = None
    okf_source_reference: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> EvidenceItem:
        """Ensure non-committal language is used in system interpretations."""
        prohibited = re.compile(
            r"\b(scam|fraud|illegal|definitely buy|definitely not buy|good deal|bad deal"
            r"|guaranteed savings|definitely save|you will save|safe to buy|unsafe to buy"
            r"|buy this|should buy|should not buy|you should buy|you should not buy)\b",
            re.IGNORECASE,
        )
        text = f"{self.interpreted_as or ''} {self.normalized_label or ''} {self.semantic_category or ''}"
        match = prohibited.search(text)
        if match:
            raise ValueError(
                f"EvidenceItem contains prohibited language '{match.group(0)}'. "
                "Use neutral, non-committal language."
            )
        return self


class FindingExplanation(BaseModel):
    """Complete explanation for a finding with evidence-first traceability.

    Distinguishes between facts, interpretations, calculations, and uncertainty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation_id: UUID = Field(default_factory=uuid4)
    finding_id: UUID
    finding_type: str

    # Concise explanation (default view)
    concise_explanation: str = Field(..., min_length=1)

    # Detailed explanation sections
    what_we_know: list[str] = Field(default_factory=list)
    what_we_infer: list[str] = Field(default_factory=list)
    what_remains_uncertain: list[str] = Field(default_factory=list)
    action: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)

    # Calculation explanation (for arithmetic findings)
    calculation_explanation: CalculationExplanation | None = None

    # Supporting document explanation
    supporting_document_explanation: SupportingDocumentExplanation | None = None

    # Confidence and uncertainty
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    uncertainty_reason: str | None = None

    # Why was this flagged
    why_flagged: str = Field(..., min_length=1)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> FindingExplanation:
        """Ensure non-committal language is used."""
        prohibited = re.compile(
            r"\b(scam|fraud|illegal|definitely buy|definitely not buy|good deal|bad deal"
            r"|guaranteed savings|definitely save|you will save|safe to buy|unsafe to buy"
            r"|buy this|should buy|should not buy|you should buy|you should not buy)\b",
            re.IGNORECASE,
        )
        text = f"{self.concise_explanation} {self.why_flagged} {self.action or ''}"
        text += " " + " ".join(self.what_we_know) + " " + " ".join(self.what_we_infer)
        match = prohibited.search(text)
        if match:
            raise ValueError(
                f"FindingExplanation contains prohibited language '{match.group(0)}'. "
                "Use neutral, non-committal language."
            )
        return self


class CalculationExplanation(BaseModel):
    """Deterministic calculation explanation with full transparency.

    Shows inputs, expected result, document result, delta, and status.
    Never uses an LLM to calculate these values.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    calculation_id: UUID = Field(default_factory=uuid4)
    check_code: str
    title: str

    # Calculation breakdown
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_result: float | None = None
    document_result: float | None = None
    delta: float | None = None
    status: str  # "PASS", "FAIL", "INCONCLUSIVE"

    # Human-readable explanation
    explanation: str = Field(..., min_length=1)

    # Field references
    input_field_ids: list[UUID] = Field(default_factory=list)


class SupportingDocumentExplanation(BaseModel):
    """Explanation for cross-document comparisons.

    Shows both sources without automatically concluding action.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation_id: UUID = Field(default_factory=uuid4)
    finding_type: str  # "POTENTIAL_OVERLAP", "PRICE_VARIANCE", etc.

    # Current document
    current_document_label: str
    current_document_amount: float | None = None
    current_document_text: str | None = None

    # Supporting document
    supporting_document_label: str
    supporting_document_amount: float | None = None
    supporting_document_text: str | None = None

    # Comparison result
    finding: str
    uncertainty: str
    action: str

    # Evidence
    primary_evidence: list[EvidenceItem] = Field(default_factory=list)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)


class QuestionProvenance(BaseModel):
    """Provenance for a generated question.

    Every question traces to a finding.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: UUID = Field(default_factory=uuid4)
    question: str
    source_finding_type: str  # e.g., "COMPONENT_RECONCILIATION", "POTENTIALLY_OPTIONAL"
    source_finding_id: UUID | None = None
    source_evidence_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class SuggestedMessageItem(BaseModel):
    """An item in the suggested message with internal provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: UUID = Field(default_factory=uuid4)
    text: str
    source_finding_type: str
    source_finding_id: UUID | None = None
    source_question_id: UUID | None = None
    source_evidence_ids: list[UUID] = Field(default_factory=list)


class EvidenceFirstResult(BaseModel):
    """Phase 7: Evidence-first explainability payload.

    Added to the final result to provide complete traceability.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_result_id: UUID = Field(default_factory=uuid4)
    result_id: UUID

    # Evidence index
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    finding_explanations: list[FindingExplanation] = Field(default_factory=list)

    # Question provenance
    question_provenance: list[QuestionProvenance] = Field(default_factory=list)

    # Suggested message provenance
    suggested_message_items: list[SuggestedMessageItem] = Field(default_factory=list)

    # Metadata
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
