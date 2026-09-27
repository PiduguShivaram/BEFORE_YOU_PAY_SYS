"""Phase 3: Cost Review Classifications and Evidence-Grounded Questions.

Defines the 7 canonical charge review classifications:
- potentially optional
- potentially negotiable
- unexplained
- duplicated/overlapping
- alternative available
- inconsistent
- requires verification

And the CostReviewQuestion model strictly enforcing evidence grounding,
non-generic phrasing, and "Potential amount to review" framing.
"""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_you_pay.models.analysis import (
    DISALLOWED_PHRASES_PATTERN,
    SmartCostReductionQuestion,
)


class CostReviewClassification(StrEnum):
    """Phase 3 charge classifications for cost review questions."""

    POTENTIALLY_OPTIONAL = "potentially optional"
    POTENTIALLY_NEGOTIABLE = "potentially negotiable"
    UNEXPLAINED = "unexplained"
    DUPLICATED_OVERLAPPING = "duplicated/overlapping"
    ALTERNATIVE_AVAILABLE = "alternative available"
    INCONSISTENT = "inconsistent"
    REQUIRES_VERIFICATION = "requires verification"


PROHIBITED_GENERIC_PATTERNS = [
    r"can you give me a discount",
    r"give me a discount",
    r"can i get a discount",
    r"any discount",
    r"give a discount",
    r"lower the price for me",
]

PROHIBITED_SAVINGS_PATTERNS = [
    r"\byou will save\b",
    r"\byou can save\b",
    r"\bsavings of\b",
    r"\bguaranteed saving\b",
    r"\bguaranteed savings\b",
    r"\byou don't need this\b",
    r"\byou do not need this\b",
    r"\byou can definitely remove\b",
]


class CostReviewQuestion(BaseModel):
    """Cost review question grounded strictly in extracted document evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: UUID = Field(default_factory=uuid4)
    classification: CostReviewClassification
    question: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    related_charge: str = Field(..., min_length=1)
    amount_involved: float | None = None
    potential_amount_to_review: float | None = None
    potential_impact: str = Field(..., min_length=1)
    evidence_source: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_verification: bool = Field(default=True)
    category: str | None = None
    priority_score: float = Field(default=0.0, ge=0.0)
    ranking_factors: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_and_tone(self) -> CostReviewQuestion:
        full_text = f"{self.question} {self.reason} {self.potential_impact}"

        # 1. Base disallowed phrases from analysis model
        match = DISALLOWED_PHRASES_PATTERN.search(full_text)
        if match:
            raise ValueError(
                f"CostReviewQuestion contains disallowed phrase '{match.group(0)}'."
            )

        # 2. Savings promise prohibition: Must use 'Potential amount to review' instead of 'You can save'
        for pat in PROHIBITED_SAVINGS_PATTERNS:
            if re.search(pat, full_text, re.IGNORECASE):
                raise ValueError(
                    f"CostReviewQuestion violates savings promise rule with pattern '{pat}'. "
                    "Use 'Potential amount to review' instead of promising savings."
                )

        # 3. Generic question prohibition: No generic haggle questions
        q_lower = self.question.lower().strip()
        for pat in PROHIBITED_GENERIC_PATTERNS:
            if re.search(r"\b" + pat + r"\b", q_lower):
                raise ValueError(
                    f"Generic discount questions like '{pat}' are prohibited. "
                    "Questions must be grounded in extracted document evidence."
                )

        return self

    def to_smart_question(self) -> SmartCostReductionQuestion:
        """Convert to standard SmartCostReductionQuestion for downstream services."""
        return SmartCostReductionQuestion(
            question_id=self.question_id,
            question=self.question,
            reason=self.reason,
            related_charge=self.related_charge,
            amount_involved=self.amount_involved,
            potential_impact=self.potential_impact,
            evidence_source=self.evidence_source,
            confidence=self.confidence,
            category=self.category,
            priority_score=self.priority_score,
            ranking_factors=self.ranking_factors,
            classification=self.classification.value,
            potential_amount_to_review=self.potential_amount_to_review,
            requires_verification=self.requires_verification,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize question to dictionary representation."""
        return {
            "question_id": str(self.question_id),
            "classification": self.classification.value,
            "question": self.question,
            "reason": self.reason,
            "related_charge": self.related_charge,
            "amount_involved": self.amount_involved,
            "potential_amount_to_review": self.potential_amount_to_review,
            "potential_impact": self.potential_impact,
            "evidence_source": self.evidence_source,
            "confidence": self.confidence,
            "requires_verification": self.requires_verification,
            "category": self.category,
            "priority_score": self.priority_score,
            "ranking_factors": self.ranking_factors,
        }
