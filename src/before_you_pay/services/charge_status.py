"""Phase 2 - Charge Status Classification Engine.

Classifies extracted financial components into exact evidence-backed statuses:
- MANDATORY_STATUTORY: Mandatory by law (statutory taxes, jurisdiction-dependent registration)
- CONTRACTUAL_REQUIREMENT: Required by seller/contract (base vehicle price / ex-showroom)
- OPTIONAL: Explicitly marked as optional in document
- POTENTIALLY_OPTIONAL: Provider-dependent or elective (insurance, extended warranty, accessories)
- NEGOTIABLE: Dealer-added charges requiring verification (handling, logistics, incidental fees)
- INCLUDED_ELSEWHERE: Bundled into base price or zero-rated
- UNKNOWN: Insufficient evidence to classify

Guarantees:
- Never makes universal legal claims.
- Never promises definite savings or states 'You don't need this' or 'You will save ₹X'.
- Uses neutral phrasing: 'Potentially optional — verify whether it is required.'
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from before_you_pay.models.document import (
    ChargeNature,
    ChargeStatus,
    ComponentCategory,
    CHARGE_STATUS_DISPLAY_LABELS,
)


@dataclass(frozen=True)
class ChargeStatusAssessment:
    """Detailed evidence-backed classification result for an extracted charge."""

    status: ChargeStatus
    confidence: float
    reason: str
    evidence: str
    requires_verification: bool
    display_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "confidence": float(self.confidence),
            "reason": self.reason,
            "evidence": self.evidence,
            "requires_verification": bool(self.requires_verification),
            "display_label": self.display_label,
        }


# Explicit document signals
EXPLICIT_OPTIONAL_PATTERN = re.compile(
    r"\b(?:optional|opt\b|\(opt\)|add-?on|elective|voluntary|customer\s+choice|if\s+required|choice|on\s+request)\b",
    re.IGNORECASE,
)

EXPLICIT_MANDATORY_PATTERN = re.compile(
    r"\b(?:mandatory|compulsory|statutory|mandated\s+by\s+law|required\s+by\s+law|govt\s+mandated|official\s+fee)\b",
    re.IGNORECASE,
)

INCLUDED_ELSEWHERE_PATTERN = re.compile(
    r"\b(?:included|incl\.?|foc|free\s+of\s+cost|n/?c|no\s+charge|bundled\s+in|zero|part\s+of\s+base)\b",
    re.IGNORECASE,
)

DEALER_HANDLING_PATTERN = re.compile(
    r"\b(?:handling|incidental|depot|pdi|p\.d\.i\.|logistics?|freight|delivery\s+charges?|facilitation)\b",
    re.IGNORECASE,
)


class ChargeStatusClassifier:
    """Classifies extracted financial components into standardized Phase 2 statuses."""

    @classmethod
    def classify(
        cls,
        raw_text: str,
        category: ComponentCategory,
        amount: float | None = None,
        charge_nature: ChargeNature = ChargeNature.CHARGE,
        evidence: str | None = None,
        confidence: float | None = None,
        explicit_status: str | ChargeStatus | None = None,
    ) -> ChargeStatusAssessment:
        """Determine charge status based on evidence without universal legal claims."""
        ev_text = str(evidence or raw_text or "").strip()
        text_lower = f"{raw_text} {ev_text}".lower().strip()

        # Handle explicit override if provided
        if explicit_status is not None:
            norm_exp = str(explicit_status).strip().upper().replace(" ", "_").replace("-", "_")
            if norm_exp in ChargeStatus.__members__:
                status_enum = ChargeStatus(norm_exp)
                disp = CHARGE_STATUS_DISPLAY_LABELS.get(status_enum, "Unknown")
                return ChargeStatusAssessment(
                    status=status_enum,
                    confidence=confidence or 0.95,
                    reason=f"Explicit status override: {disp}",
                    evidence=ev_text,
                    requires_verification=status_enum in (ChargeStatus.POTENTIALLY_OPTIONAL, ChargeStatus.NEGOTIABLE, ChargeStatus.UNKNOWN),
                    display_label=disp,
                )

        # 1. Included elsewhere check (e.g. ₹0 or marked 'included')
        if amount == 0.0 or INCLUDED_ELSEWHERE_PATTERN.search(text_lower):
            return ChargeStatusAssessment(
                status=ChargeStatus.INCLUDED_ELSEWHERE,
                confidence=0.92,
                reason="Indicated as included elsewhere or bundled into base price — verify coverage.",
                evidence=ev_text,
                requires_verification=True,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.INCLUDED_ELSEWHERE],
            )

        # 2. Explicit optional language in document
        if EXPLICIT_OPTIONAL_PATTERN.search(text_lower):
            return ChargeStatusAssessment(
                status=ChargeStatus.OPTIONAL,
                confidence=0.95,
                reason="Document explicitly designates this charge as optional.",
                evidence=ev_text,
                requires_verification=False,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.OPTIONAL],
            )

        # 3. Base vehicle price / Ex-showroom (Contractual requirement)
        if category in (ComponentCategory.BASE_PRICE, ComponentCategory.EX_SHOWROOM_PRICE) or any(
            k in text_lower for k in ["ex-showroom", "ex showroom", "base price", "basic price", "vehicle price"]
        ):
            return ChargeStatusAssessment(
                status=ChargeStatus.CONTRACTUAL_REQUIREMENT,
                confidence=confidence or 0.95,
                reason="Base vehicle price stipulated under seller quotation and contract terms.",
                evidence=ev_text,
                requires_verification=False,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.CONTRACTUAL_REQUIREMENT],
            )

        # 4. Dealer handling / logistics charges (Potentially negotiable)
        # "Dealer handling charge → requires verification/potentially negotiable"
        if category in (
            ComponentCategory.HANDLING_FEE,
            ComponentCategory.LOGISTICS_FEE,
            ComponentCategory.PROCESSING_FEE,
            ComponentCategory.DEALER_PACKAGE,
        ) or DEALER_HANDLING_PATTERN.search(text_lower):
            return ChargeStatusAssessment(
                status=ChargeStatus.NEGOTIABLE,
                confidence=0.88,
                reason="Dealer-added charge — requires verification/potentially negotiable. Verify whether this fee is permissible or removable.",
                evidence=ev_text,
                requires_verification=True,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.NEGOTIABLE],
            )

        # 5. Registration (jurisdiction-dependent statutory requirement)
        # "Registration → jurisdiction-dependent"
        if category in (ComponentCategory.REGISTRATION, ComponentCategory.RC, ComponentCategory.HSRP) or any(
            k in text_lower for k in ["r.c.", "regn", "registration", "hsrp", "rto charges"]
        ):
            return ChargeStatusAssessment(
                status=ChargeStatus.MANDATORY_STATUTORY,
                confidence=0.90,
                reason="Statutory registration fee payable to government authorities (jurisdiction-dependent fee schedule).",
                evidence=ev_text,
                requires_verification=True,  # jurisdiction-dependent
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.MANDATORY_STATUTORY],
            )

        # 6. Mandatory statutory taxes (TCS, GST, Road Tax, FASTag)
        if category in (
            ComponentCategory.TAX_OR_STATUTORY,
            ComponentCategory.TCS,
            ComponentCategory.GST,
            ComponentCategory.ROAD_TAX,
            ComponentCategory.TAX,
            ComponentCategory.FASTAG,
        ) or any(k in text_lower for k in ["tcs", "t.c.s.", "gst", "road tax", "motor vehicle tax", "statutory tax"]):
            return ChargeStatusAssessment(
                status=ChargeStatus.MANDATORY_STATUTORY,
                confidence=confidence or 0.95,
                reason="Statutory tax or governmental levy mandated by applicable regulations.",
                evidence=ev_text,
                requires_verification=False,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.MANDATORY_STATUTORY],
            )

        # 7. Insurance (Potentially optional / provider-dependent)
        # "Insurance → potentially optional/provider-dependent"
        if category == ComponentCategory.INSURANCE or any(k in text_lower for k in ["insurance", "insur", "policy"]):
            return ChargeStatusAssessment(
                status=ChargeStatus.POTENTIALLY_OPTIONAL,
                confidence=0.90,
                reason="Potentially optional — verify whether purchasing this policy from the seller is required or if independent coverage is permitted.",
                evidence=ev_text,
                requires_verification=True,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.POTENTIALLY_OPTIONAL],
            )

        # 8. Extended Warranty (Potentially optional)
        # "Extended Warranty → potentially optional"
        if category in (ComponentCategory.EXTENDED_WARRANTY, ComponentCategory.WARRANTY) or any(
            k in text_lower for k in ["extended warranty", "ext warranty", "extd warranty", "ew charges"]
        ):
            return ChargeStatusAssessment(
                status=ChargeStatus.POTENTIALLY_OPTIONAL,
                confidence=0.92,
                reason="Potentially optional — verify whether extended warranty coverage is required or elective beyond standard factory warranty.",
                evidence=ev_text,
                requires_verification=True,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.POTENTIALLY_OPTIONAL],
            )

        # 9. Accessories & Service packages (Potentially optional)
        # "Accessories → potentially optional"
        if category in (
            ComponentCategory.ACCESSORY,
            ComponentCategory.ACCESSORY_PACKAGE,
            ComponentCategory.SERVICE,
            ComponentCategory.SERVICE_PACKAGE,
        ) or any(k in text_lower for k in ["accessor", "essential kit", "basic kit", "amc", "service package", "maintenance"]):
            return ChargeStatusAssessment(
                status=ChargeStatus.POTENTIALLY_OPTIONAL,
                confidence=0.90,
                reason="Potentially optional — verify whether this package is required or individual items can be removed.",
                evidence=ev_text,
                requires_verification=True,
                display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.POTENTIALLY_OPTIONAL],
            )

        # 10. Unknown / uncertain components
        # "If uncertain, use UNKNOWN and require verification."
        return ChargeStatusAssessment(
            status=ChargeStatus.UNKNOWN,
            confidence=0.60,
            reason="Charge status unknown due to insufficient evidence in the document — requires verification.",
            evidence=ev_text,
            requires_verification=True,
            display_label=CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.UNKNOWN],
        )
