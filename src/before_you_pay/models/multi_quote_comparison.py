"""Models for Phase 1A: N-Way Multi-Document Quotation Comparison.

Enables simultaneous side-by-side alignment, variance calculation, inclusion/exclusion
detection, and objective dealer question generation for 2 to 5 quotations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_you_pay.models.analysis import DISALLOWED_PHRASES_PATTERN, STANDARD_DISCLAIMER
from before_you_pay.models.document import BoundingBox


class QuoteSummary(BaseModel):
    """Metadata and high-level summary of an individual quotation in the comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    vendor_name: str = Field(default="Unknown Vendor")
    document_date: str | None = None
    currency: str = Field(default="INR")
    total_amount: float | None = None
    item_count: int = Field(default=0, ge=0)
    filename: str | None = None


class AlignedComponentCell(BaseModel):
    """The occurrence and extraction details of a component within a specific quote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    is_present: bool = True
    raw_label: str | None = None
    amount: float | None = None
    amount_state: str = Field(default="PRESENT")  # PRESENT, MISSING, UNKNOWN, ZERO, NOT_APPLICABLE
    is_included_in_total: bool = True
    ocr_line_id: UUID | None = None
    page_number: int | None = None
    bounding_box: BoundingBox | None = None


class AlignedFinancialComponent(BaseModel):
    """A financial component aligned across 2–5 quotations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alignment_id: UUID = Field(default_factory=uuid4)
    canonical_category: str = Field(
        ..., min_length=1
    )  # e.g., "ex_showroom", "insurance", "handling"
    display_name: str = Field(..., min_length=1)  # e.g., "Handling / PDI Charges"
    cells: dict[str, AlignedComponentCell] = Field(default_factory=dict)  # key: document_id str
    min_amount: float | None = None
    max_amount: float | None = None
    delta_amount: float | None = None  # max_amount - min_amount
    presence_variance: bool = False  # True if present in some quotes and absent in others


class InclusionExclusionFinding(BaseModel):
    """Detected difference in what items/services are included vs excluded across quotes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: UUID = Field(default_factory=uuid4)
    component_category: str
    component_name: str
    description: str = Field(..., min_length=1)
    present_in_document_ids: list[UUID] = Field(default_factory=list)
    absent_in_document_ids: list[UUID] = Field(default_factory=list)
    potential_cost_difference: float | None = None

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> InclusionExclusionFinding:
        match = DISALLOWED_PHRASES_PATTERN.search(self.description)
        if match:
            raise ValueError(
                f"Prohibited non-committal phrase '{match.group(0)}' found in description"
            )
        return self


class MultiQuoteComparisonResult(BaseModel):
    """Comprehensive N-way comparison matrix and variance report across 2–5 quotations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quotes: list[QuoteSummary] = Field(..., min_length=2, max_length=5)
    primary_currency: str = Field(default="INR")
    currency_mismatch: bool = False
    aligned_components: list[AlignedFinancialComponent] = Field(default_factory=list)
    totals_by_document_id: dict[str, float | None] = Field(default_factory=dict)
    min_total: float | None = None
    max_total: float | None = None
    total_delta: float | None = None
    inclusions_and_exclusions: list[InclusionExclusionFinding] = Field(default_factory=list)
    suggested_negotiation_questions: list[str] = Field(default_factory=list)
    summary_text: str = Field(..., min_length=1)
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)

    @model_validator(mode="after")
    def validate_non_committal_summary(self) -> MultiQuoteComparisonResult:
        match = DISALLOWED_PHRASES_PATTERN.search(self.summary_text)
        if match:
            raise ValueError(f"Prohibited phrase '{match.group(0)}' found in summary_text")
        for q in self.suggested_negotiation_questions:
            q_match = DISALLOWED_PHRASES_PATTERN.search(q)
            if q_match:
                raise ValueError(
                    f"Prohibited phrase '{q_match.group(0)}' found in suggested question '{q}'"
                )
        return self
