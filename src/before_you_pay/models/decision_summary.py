"""Phase 6: Before You Pay Final Decision Summary Models.

Provides the canonical presentation and aggregation structures for the final
decision-support experience:
1. Decision Hero (Quoted Total, Payment Status, Review Status, Readiness State)
2. Three-Tier Reconciliation (Component, Offers, Quoted Total kept strictly separate)
3. Canonical Financial Summary (Categories that actually exist, respecting amount states)
4. Attention Items (Grounded in actual findings, neutral and factual)
5. Ways to Review This Cost (6 canonical categories, no double-counting, no guaranteed savings)
6. Supporting Document Context (Evidence-based cross-document comparisons)
7. Questions to Ask Before Paying (Directly tied to findings)
8. Message to Seller (Dynamically generated, editable, copyable)
9. Before You Pay Checklist (Factual checklist reflecting analysis state)
10. Information Completeness (Distinguishes complete to calculate vs explain vs verify)

Strict Guardrails:
- No numerical risk or deal scores.
- No binary "SAFE TO PAY" or purchase recommendations ("Buy this" / "Don't buy this").
- No scam or fraud accusations.
- No guaranteed savings claims; strictly "Potential amount to review".
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_you_pay.models.document import AmountState, ChargeNature, ComponentCategory

_PROHIBITED_SUMMARY_PHRASES = re.compile(
    r"\b(good deal|bad deal|safe to pay|unsafe to pay|guaranteed savings|definitely save"
    r"|you will save|scam|fraud|cheat|scammer"
    r"|buy this|should buy|should not buy|you should buy|you should not buy"
    r"|safe to buy|unsafe to buy|this is a good|this is a bad)\b",
    re.IGNORECASE,
)


class PaymentReadinessState(StrEnum):
    """Factual, non-binary payment readiness status."""

    READY_FOR_FINAL_VERIFICATION = "READY_FOR_FINAL_VERIFICATION"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    INCOMPLETE_INFORMATION = "INCOMPLETE_INFORMATION"


class ChecklistItemStatus(StrEnum):
    """Deterministic verification state of a checklist item."""

    VERIFIED = "VERIFIED"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    PENDING_USER_ACTION = "PENDING_USER_ACTION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BeforeYouPayChecklistItem(BaseModel):
    """An individual item on the Before You Pay pre-payment verification checklist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    title: str
    status: ChecklistItemStatus
    detail: str
    evidence: str | None = None


class BeforeYouPayChecklist(BaseModel):
    """Complete pre-payment verification checklist evaluated from document analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[BeforeYouPayChecklistItem] = Field(default_factory=list)
    overall_status: ChecklistItemStatus = Field(default=ChecklistItemStatus.REQUIRES_VERIFICATION)
    completed_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)


class InformationCompleteness(BaseModel):
    """Evaluates whether document data is complete enough for calculation, explanation, and verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_complete_to_calculate: bool
    is_complete_to_explain: bool
    is_complete_to_verify: bool
    missing_or_uncertain_fields: list[str] = Field(default_factory=list)
    completeness_note: str


class CanonicalFinancialSummaryItem(BaseModel):
    """Major financial component in canonical category normalization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_category: ComponentCategory
    name: str
    amount: float | None = None
    amount_state: AmountState = Field(default=AmountState.PRESENT)
    charge_nature: ChargeNature = Field(default=ChargeNature.CHARGE)
    formatted_amount: str
    is_deduction: bool = False


class DecisionHero(BaseModel):
    """Primary decision-support headline area at the top of the Before You Pay summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quoted_total: float | None = None
    stated_total: float | None = None
    formatted_total: str
    currency: str = Field(default="INR")
    payment_status: str = Field(default="Unpaid")
    balance_due: float | None = None
    formatted_balance_due: str | None = None
    review_status: str = Field(default="Review before paying")
    readiness_state: PaymentReadinessState = Field(
        default=PaymentReadinessState.REQUIRES_VERIFICATION
    )
    readiness_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_guardrails(self) -> DecisionHero:
        text = f"{self.review_status} {' '.join(self.readiness_reasons)}"
        match = _PROHIBITED_SUMMARY_PHRASES.search(text)
        if match:
            raise ValueError(f"DecisionHero contains prohibited language '{match.group(0)}'.")
        return self


class ReconciliationThreeTier(BaseModel):
    """Strictly separates Component, Offers, and Quoted Total reconciliations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # 1. Component Reconciliation
    component_reconciliation_status: str = Field(
        default="NOT_APPLICABLE"
    )  # PASS | REQUIRES_VERIFICATION | FAIL | NOT_APPLICABLE
    component_reconciliation_delta: float | None = None
    component_reconciliation_explanation: str = Field(default="")

    # 2. Offers / Deductions Reconciliation
    offers_reconciliation_status: str = Field(default="NOT_APPLICABLE")
    offers_reconciliation_delta: float | None = None
    offers_reconciliation_explanation: str = Field(default="")

    # 3. Quoted Total Reconciliation
    quoted_total_reconciliation_status: str = Field(default="NOT_APPLICABLE")
    quoted_total_reconciliation_delta: float | None = None
    quoted_total_reconciliation_explanation: str = Field(default="")


class AttentionItem(BaseModel):
    """Factual attention item derived strictly from validation checks and findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: UUID = Field(default_factory=uuid4)
    title: str
    category: str
    amount: float | None = None
    formatted_amount: str = Field(default="")
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    action_or_question: str
    related_component_id: UUID | None = None
    page_number: int | None = None
    provenance_text: str | None = None

    @model_validator(mode="after")
    def validate_guardrails(self) -> AttentionItem:
        text = f"{self.title} {self.reason} {self.action_or_question}"
        match = _PROHIBITED_SUMMARY_PHRASES.search(text)
        if match:
            raise ValueError(f"AttentionItem contains prohibited language '{match.group(0)}'.")
        return self


class CostReviewOpportunity(BaseModel):
    """Cost-review opportunity across the 6 canonical categories.

    Uses 'Potential amount to review' instead of 'Guaranteed Savings'.
    Supports linking related opportunities to prevent double-counting.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    opportunity_id: UUID = Field(default_factory=uuid4)
    category: str  # "Potentially Optional", "Potentially Negotiable", etc.
    component: str
    amount: float | None = None
    formatted_amount: str = Field(default="")
    potential_amount_to_review: float | None = None
    formatted_potential_amount: str = Field(default="")
    evidence: str
    explanation: str
    suggested_action: str
    related_component_id: UUID | None = None
    linked_opportunity_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_guardrails(self) -> CostReviewOpportunity:
        text = f"{self.explanation} {self.suggested_action}"
        match = _PROHIBITED_SUMMARY_PHRASES.search(text)
        if match:
            raise ValueError(
                f"CostReviewOpportunity contains prohibited language '{match.group(0)}'."
            )
        return self


class WaysToReviewCostSummary(BaseModel):
    """Summary of cost-review opportunities with double-counting prevention."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_categories: list[str] = Field(default_factory=list)
    opportunities: list[CostReviewOpportunity] = Field(default_factory=list)
    disclaimer: str = Field(
        default="Potential amounts to review are discovery targets for negotiation or verification, not promised or assured savings."
    )


class SupportingDocComparison(BaseModel):
    """Evidence-grounded comparison between current document and supporting document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_type: str  # "Potential Overlap", "Price Variance", "Coverage Comparison", etc.
    title: str
    current_charge_name: str
    current_charge_amount: float | None = None
    supporting_document_text: str
    finding_description: str
    action_guidance: str


class BeforeYouPayFinalSummary(BaseModel):
    """The complete user-facing Before You Pay decision-support payload (Phase 6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    user_id: UUID
    hero: DecisionHero
    reconciliation: ReconciliationThreeTier
    financial_summary: list[CanonicalFinancialSummaryItem] = Field(default_factory=list)
    attention_items: list[AttentionItem] = Field(default_factory=list)
    ways_to_review_cost: WaysToReviewCostSummary
    supporting_document_context: list[SupportingDocComparison] | None = None
    questions_to_ask: list[str] = Field(default_factory=list)
    suggested_message: str = Field(default="")
    checklist: BeforeYouPayChecklist
    completeness: InformationCompleteness

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
