"""Temporal and recurring charge semantics engine (Phase 4 Step 8).

Extracts and validates temporal characteristics of financial components:
- One-time vs recurring charges
- Billing frequencies (monthly, yearly, quarterly, weekly, renewal)
- Effective periods, validity spans, and renewal indicators

Strict Guardrails:
- NEVER invent dates or periods.
- NEVER infer recurring charges merely because a document is classified as a subscription.
- Require actual textual evidence in the document line or context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Regex patterns for billing frequencies and recurring semantics
RECURRING_MONTHLY_PATTERN = re.compile(
    r"\b(?:monthly|per\s+month|\/\s*mo(?:nth)?|p\.m\.|\bmo\b(?!\w))\b",
    re.IGNORECASE,
)

RECURRING_YEARLY_PATTERN = re.compile(
    r"\b(?:annually|annual|yearly|per\s+(?:year|annum)|\/\s*yr|\/\s*year|p\.a\.)\b",
    re.IGNORECASE,
)

RECURRING_QUARTERLY_PATTERN = re.compile(
    r"\b(?:quarterly|per\s+quarter|\/\s*qtr)\b",
    re.IGNORECASE,
)

RECURRING_WEEKLY_PATTERN = re.compile(
    r"\b(?:weekly|per\s+week|\/\s*wk)\b",
    re.IGNORECASE,
)

RENEWAL_PATTERN = re.compile(
    r"\b(?:renewal\s*(?:fee|charge|premium)?|auto[\s\-_]*renew(?:al)?|on\s+renewal)\b",
    re.IGNORECASE,
)

ONE_TIME_PATTERN = re.compile(
    r"\b(?:one[\s\-_]*time|onetime|non[\s\-_]*recurring|single\s+payment|setup\s+fee|joining\s+fee|activation\s+fee|one[\s\-_]*off)\b",
    re.IGNORECASE,
)

# Date span pattern e.g. "valid from 01/01/2025 to 31/12/2025" or "period: 2025-01-01 - 2025-12-31"
DATE_SPAN_PATTERN = re.compile(
    r"\b(?:valid\s+(?:from|period)|period|effective\s+(?:from|period)|coverage\s+period)?\s*[:=]?\s*"
    r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})"
    r"\s*(?:to|–|—|-|until)\s*"
    r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})\b",
    re.IGNORECASE,
)

# Explicit duration e.g. "1 year", "3 years", "12 months", "36 months"
DURATION_PATTERN = re.compile(
    r"\b(\d+)\s*(?:yr|year|years|month|months|mo|mths)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemporalInfo:
    """Evidence-grounded temporal classification of a financial charge."""

    is_recurring: bool | None = None
    billing_frequency: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    effective_period: str | None = None
    duration: str | None = None
    has_explicit_evidence: bool = False
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_recurring": self.is_recurring,
            "billing_frequency": self.billing_frequency,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "effective_period": self.effective_period,
            "duration": self.duration,
            "has_explicit_evidence": self.has_explicit_evidence,
            "explanation": self.explanation,
        }


class TemporalSemanticsService:
    """Service to evaluate temporal and recurring properties of financial components."""

    @classmethod
    def extract_temporal_info(
        cls,
        text: str,
        document_text: str | None = None,
    ) -> TemporalInfo:
        """Extract temporal and recurring metadata based strictly on actual textual evidence.

        Guardrail:
        - If text contains no explicit temporal indicators, returns None for is_recurring and
          billing_frequency. Never guesses or assumes based on document type alone.
        """
        if not text:
            return TemporalInfo()

        text_to_scan = text.strip()

        # Check for explicit one-time indicators
        if ONE_TIME_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=False,
                billing_frequency="one-time",
                has_explicit_evidence=True,
                explanation="Explicitly designated as a one-time non-recurring charge.",
            )

        # Check for date spans and durations
        period_start = None
        period_end = None
        effective_period = None
        date_span_m = DATE_SPAN_PATTERN.search(text_to_scan)
        if date_span_m:
            period_start = date_span_m.group(1).strip()
            period_end = date_span_m.group(2).strip()
            effective_period = f"{period_start} to {period_end}"

        duration_m = DURATION_PATTERN.search(text_to_scan)
        duration = duration_m.group(0).strip() if duration_m else None

        # Check for explicit recurring frequencies in component line
        if RECURRING_MONTHLY_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=True,
                billing_frequency="monthly",
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation="Monthly recurring charge indicated by document evidence.",
            )

        if RECURRING_YEARLY_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=True,
                billing_frequency="yearly",
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation="Annual / yearly recurring charge indicated by document evidence.",
            )

        if RECURRING_QUARTERLY_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=True,
                billing_frequency="quarterly",
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation="Quarterly recurring charge indicated by document evidence.",
            )

        if RECURRING_WEEKLY_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=True,
                billing_frequency="weekly",
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation="Weekly recurring charge indicated by document evidence.",
            )

        if RENEWAL_PATTERN.search(text_to_scan):
            return TemporalInfo(
                is_recurring=True,
                billing_frequency="renewal",
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation="Recurring renewal charge indicated by document evidence.",
            )

        # If date span was found without explicit frequency keyword
        if effective_period:
            return TemporalInfo(
                is_recurring=True
                if duration and any(u in duration.lower() for u in ["yr", "year", "month"])
                else None,
                billing_frequency=None,
                period_start=period_start,
                period_end=period_end,
                effective_period=effective_period,
                duration=duration,
                has_explicit_evidence=True,
                explanation=f"Validity period specified: {effective_period}.",
            )

        if duration:
            return TemporalInfo(
                is_recurring=None,
                billing_frequency=None,
                period_start=None,
                period_end=None,
                effective_period=None,
                duration=duration,
                has_explicit_evidence=True,
                explanation=f"Coverage duration specified: {duration}.",
            )

        # No explicit temporal evidence -> strictly preserve uncertainty (None)
        return TemporalInfo(
            is_recurring=None,
            billing_frequency=None,
            period_start=None,
            period_end=None,
            effective_period=None,
            duration=None,
            has_explicit_evidence=False,
            explanation=None,
        )
