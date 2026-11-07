"""Models for Phase 1B: Dealer Response & Counter-Offer Parser.

Extracts structured negotiations, concessions, waivers, price adjustments,
and stated counter-offers from free-form dealer communications (email/chat)
and deterministically reconciles them against the original quotation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_you_pay.models.analysis import DISALLOWED_PHRASES_PATTERN, STANDARD_DISCLAIMER


class DealerActionType(StrEnum):
    """Categorization of vendor/dealer responses to negotiation."""

    CHARGE_WAIVED = "charge_waived"
    PRICE_REDUCED = "price_reduced"
    DISCOUNT_ADDED = "discount_added"
    REFUSED_NON_NEGOTIABLE = "refused_non_negotiable"
    COUNTER_TOTAL_STATED = "counter_total_stated"
    CLARIFICATION_PROVIDED = "clarification_provided"
    OTHER = "other"


class ExtractedDealerAction(BaseModel):
    """An individual concession, refusal, or amendment extracted from dealer text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: UUID = Field(default_factory=uuid4)
    action_type: DealerActionType
    target_component_name: str = Field(..., min_length=1)
    raw_text_snippet: str = Field(..., min_length=1)
    original_amount: float | None = None
    revised_amount: float | None = None
    reduction_amount: float | None = None
    is_confirmed: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_non_committal_language(self) -> ExtractedDealerAction:
        if self.notes:
            match = DISALLOWED_PHRASES_PATTERN.search(self.notes)
            if match:
                raise ValueError(f"Prohibited phrase '{match.group(0)}' found in action notes")
        return self


class DealerResponseAnalysisResult(BaseModel):
    """Structured analysis and deterministic reconciliation of a dealer's counter-offer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    response_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    original_document_id: UUID | None = None
    dealer_raw_text: str = Field(..., min_length=1)
    extracted_actions: list[ExtractedDealerAction] = Field(default_factory=list)
    currency: str = Field(default="INR")
    original_total: float | None = None
    calculated_new_total: float | None = None
    stated_counter_total: float | None = None
    total_reduction: float | None = None
    math_reconciliation_status: str = Field(
        default="RECONCILED"
    )  # RECONCILED, DISCREPANCY, INCOMPLETE_DATA
    reconciliation_difference: float | None = None
    follow_up_recommendations: list[str] = Field(default_factory=list)
    summary_text: str = Field(..., min_length=1)
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)

    @model_validator(mode="after")
    def validate_guardrails(self) -> DealerResponseAnalysisResult:
        match = DISALLOWED_PHRASES_PATTERN.search(self.summary_text)
        if match:
            raise ValueError(f"Prohibited phrase '{match.group(0)}' in summary_text")
        for rec in self.follow_up_recommendations:
            rec_match = DISALLOWED_PHRASES_PATTERN.search(rec)
            if rec_match:
                raise ValueError(
                    f"Prohibited phrase '{rec_match.group(0)}' in follow_up_recommendations"
                )
        return self
