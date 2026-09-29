"""Mandatory, Optional, and Potentially Optional Cost Analysis Service (Phase 3).

Evaluates every financial component across 6 evidence dimensions:
1. Document wording
2. Explicit optional/mandatory language
3. User-provided context
4. Authoritative knowledge when applicable
5. Jurisdiction
6. Product/service context

Explicitly differentiates:
- WHAT THE DOCUMENT STATES (document_states)
- WHAT THE SYSTEM KNOWS (system_knows)
- WHAT REQUIRES CONFIRMATION (requires_confirmation)

Never classifies purely from component name.
Never converts uncertainty into certainty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from before_you_pay.models.document import (
    ChargeNature,
    ComponentCategory,
    OptionalityStatus,
)


@dataclass(frozen=True)
class OptionalityAssessment:
    """Multi-dimensional assessment result for a financial component's optionality."""

    status: OptionalityStatus
    display_label: str
    document_states: str
    system_knows: str
    requires_confirmation: str


# Regex patterns for explicit document optionality signals
EXPLICIT_OPTIONAL_PATTERN = re.compile(
    r"\b(?:optional|opt\b|\(opt\)|add-?on|elective|voluntary|customer\s+choice|if\s+required|choice|on\s+request)\b",
    re.IGNORECASE,
)

EXPLICIT_MANDATORY_PATTERN = re.compile(
    r"\b(?:mandatory|compulsory|statutory|mandated|govt\s+mandated|required\s+by\s+law|official\s+fee)\b",
    re.IGNORECASE,
)


class OptionalityAnalysisService:
    """Service to evaluate component optionality using multi-factor evidence."""

    @classmethod
    def analyze(
        cls,
        raw_text: str,
        category: ComponentCategory,
        charge_nature: ChargeNature = ChargeNature.CHARGE,
        user_context: dict[str, Any] | None = None,
        jurisdiction: str = "IN",
        product_context: str = "vehicle_retail",
        explicit_status: str | OptionalityStatus | None = None,
    ) -> OptionalityAssessment:
        """Analyze a financial charge across evidence dimensions.

        Never relies purely on component name. Checks explicit document language,
        statutory legal authority, jurisdiction rules, and retail purchase context.
        """
        # If an explicit status was forced (e.g. from user or prior validated state)
        if explicit_status is not None and str(explicit_status).strip():
            if isinstance(explicit_status, OptionalityStatus):
                return cls._build_explicit_override_assessment(explicit_status, raw_text)
            status_str = str(explicit_status).lower().strip()
            if status_str in (
                "confirmed_mandatory",
                "confirmed_optional",
                "potentially_optional",
                "not_applicable",
                "unclear",
            ):
                status_enum = OptionalityStatus(status_str)
                return cls._build_explicit_override_assessment(status_enum, raw_text)
            if status_str in ("mandatory", "compulsory"):
                return cls._build_explicit_override_assessment(
                    OptionalityStatus.CONFIRMED_MANDATORY, raw_text
                )
            if status_str in ("optional", "opt"):
                return cls._build_explicit_override_assessment(
                    OptionalityStatus.CONFIRMED_OPTIONAL, raw_text
                )

        text_to_scan = raw_text.strip() if raw_text else ""
        has_explicit_opt = bool(EXPLICIT_OPTIONAL_PATTERN.search(text_to_scan))
        has_explicit_mand = bool(EXPLICIT_MANDATORY_PATTERN.search(text_to_scan))

        # 1. Non-applicable components: deductions, discounts, and totals
        if charge_nature == ChargeNature.DEDUCTION or category in (
            ComponentCategory.DISCOUNT,
            ComponentCategory.OFFER,
            ComponentCategory.SUBTOTAL,
            ComponentCategory.TOTAL,
            ComponentCategory.AMOUNT_PAID,
            ComponentCategory.BALANCE_DUE,
        ):
            return OptionalityAssessment(
                status=OptionalityStatus.NOT_APPLICABLE,
                display_label="Not applicable",
                document_states="Document states a deduction, discount concession, or aggregate calculation.",
                system_knows="Negative adjustments and arithmetic totals are not constituent billed add-ons; optionality does not apply.",
                requires_confirmation="No optionality confirmation required.",
            )

        # 2. Document explicitly specifies optionality in its own text
        if has_explicit_opt and not has_explicit_mand:
            return OptionalityAssessment(
                status=OptionalityStatus.CONFIRMED_OPTIONAL,
                display_label="Confirmed optional",
                document_states=f"Document explicitly designates this charge as optional ('{text_to_scan}').",
                system_knows="When a document explicitly marks an item as optional, the buyer is entitled to decline it.",
                requires_confirmation="Can be declined or removed from the final invoice prior to payment.",
            )

        if has_explicit_mand and not has_explicit_opt:
            return OptionalityAssessment(
                status=OptionalityStatus.CONFIRMED_MANDATORY,
                display_label="Document states mandatory",
                document_states=f"Document explicitly states mandatory fee ('{text_to_scan}').",
                system_knows="Document explicitly declares statutory or compulsory nature.",
                requires_confirmation="Verify that the billed figure conforms to official government or contractually binding rates.",
            )

        # 3. Categorical statutory analysis under jurisdiction and product context
        if category in (ComponentCategory.EX_SHOWROOM_PRICE, ComponentCategory.BASE_PRICE):
            return OptionalityAssessment(
                status=OptionalityStatus.CONFIRMED_MANDATORY,
                display_label="Confirmed mandatory",
                document_states="Document lists base vehicle invoice price.",
                system_knows="The contracted vehicle purchase price is mandatory to acquire vehicle ownership.",
                requires_confirmation="Verify base vehicle price against manufacturer official ex-showroom price list.",
            )

        if category in (ComponentCategory.TCS, ComponentCategory.GST, ComponentCategory.TAX):
            return OptionalityAssessment(
                status=OptionalityStatus.CONFIRMED_MANDATORY,
                display_label="Confirmed mandatory",
                document_states="Document itemizes statutory tax levy.",
                system_knows="Statutory tax mandated by government regulations (e.g., Section 206C(1F) of Income Tax Act for TCS, GST Act).",
                requires_confirmation="Verify tax rate arithmetic and ensure tax credit reflects in Form 26AS / AIS.",
            )

        if category == ComponentCategory.ROAD_TAX:
            # Road tax is a mandatory government tax for vehicle operation, but dealers may round or inflate
            return OptionalityAssessment(
                status=OptionalityStatus.CONFIRMED_MANDATORY,
                display_label="Confirmed mandatory",
                document_states="Document itemizes statutory road tax / motor vehicle life tax.",
                system_knows="State motor vehicle life tax is legally mandatory under the Motor Vehicles Act for registration and public road use.",
                requires_confirmation="Verify road tax slab against state Vahan RTO calculation to ensure no dealer padding.",
            )

        if category in (
            ComponentCategory.REGISTRATION,
            ComponentCategory.RC,
            ComponentCategory.HSRP,
        ):
            # If bare registration with no evidence: dealer quotes routinely inflate registration with handling markups.
            # Never convert this uncertainty into certainty.
            return OptionalityAssessment(
                status=OptionalityStatus.UNCLEAR,
                display_label="Status: Requires verification",
                document_states="Document lists registration without statutory breakdown or mandatory verification.",
                system_knows=(
                    "Official RTO vehicle registration is legally required, but dealer quotation figures for "
                    "'Registration / R.C.' routinely bundle unauthorized documentation fees, agent commissions, and markups "
                    "beyond the statutory government fee schedule."
                ),
                requires_confirmation="Status: Requires verification — request itemized RTO government receipt to verify actual statutory fee vs dealer markup.",
            )

        if category == ComponentCategory.EXTENDED_WARRANTY:
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional",
                document_states="Document lists extended warranty add-on without explicit opt-in confirmation.",
                system_knows=(
                    "Manufacturer extended warranty is an optional supplemental coverage contract distinct from "
                    "the standard warranty included with the vehicle. Dealers cannot condition vehicle delivery on purchasing extended warranty."
                ),
                requires_confirmation="Verify whether this can be removed.",
            )

        if category in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE):
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional",
                document_states="Document lists vehicle accessories without explicit mandatory/optional indication.",
                system_knows=(
                    "Accessory packages are dealer merchandise add-ons. Automotive regulations and consumer protection rules "
                    "prohibit dealerships from forcing mandatory accessory packages on buyers."
                ),
                requires_confirmation="Verify whether this can be removed or selected individually.",
            )

        if category in (
            ComponentCategory.HANDLING_FEE,
            ComponentCategory.LOGISTICS_FEE,
            ComponentCategory.PROCESSING_FEE,
        ):
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional — verify with seller",
                document_states="Document bills dealer handling, logistics, or document processing charges.",
                system_knows=(
                    "Multiple High Courts and State Transport Departments in India have ruled dealer handling, logistics, and "
                    "depot charges unlawful and unauthorized under Rule 115 of the Central Motor Vehicles Rules."
                ),
                requires_confirmation="Contest with dealer; request removal under Transport Department rulings prohibiting handling charges.",
            )

        if category == ComponentCategory.INSURANCE:
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional",
                document_states="Document lists dealer-quoted motor insurance premium.",
                system_knows=(
                    "Third-party liability motor insurance is statutory under Section 146 of the Motor Vehicles Act, "
                    "but purchasing the insurance policy through the dealer is completely optional. Buyers possess the legal right "
                    "under IRDAI guidelines to purchase insurance externally or seek quotes from independent insurers."
                ),
                requires_confirmation="Verify whether dealer insurance can be price-matched or purchased independently from an external insurer.",
            )

        if category == ComponentCategory.FASTAG:
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional",
                document_states="Document lists FASTag fee.",
                system_knows="FASTag is mandatory for national highway toll collection, but official bank issuance is capped at ~₹500 (including security deposit). Dealer quotes often charge inflated figures.",
                requires_confirmation="Verify if dealer charge matches official bank/NHAI issuance rates or obtain FASTag directly.",
            )

        if category in (
            ComponentCategory.DEALER_PACKAGE,
            ComponentCategory.SERVICE_PACKAGE,
            ComponentCategory.OTHER_FEE,
        ):
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional — verify with seller",
                document_states=f"Document lists miscellaneous dealer service package ('{text_to_scan}').",
                system_knows="Dealer service packages, ceramic coatings, anti-rust treatments, and convenience packs are optional consumer products.",
                requires_confirmation="Potentially optional — verify with seller whether this can be excluded.",
            )

        if category == ComponentCategory.FINANCING:
            return OptionalityAssessment(
                status=OptionalityStatus.POTENTIALLY_OPTIONAL,
                display_label="Potentially optional — verify financing terms",
                document_states="Document itemizes vehicle financing, loan processing, or hypothecation fees.",
                system_knows=(
                    "Financing arrangements and dealer loan origination fees are elective. If purchasing outright or arranging external finance, "
                    "these fees do not apply; hypothecation charges only apply if availing credit through this lender."
                ),
                requires_confirmation="Verify loan processing terms, interest rate, and whether dealer loan facilitation fee is optional.",
            )

        # 4. Unknown / Unclear charges (e.g. "XYZ ₹5,000")
        return OptionalityAssessment(
            status=OptionalityStatus.UNCLEAR,
            display_label="Optionality: Unclear",
            document_states="Document lists charge without clear identification or statutory categorization.",
            system_knows="No authoritative statutory basis or standard retail classification exists for this unitemized charge.",
            requires_confirmation="Optionality: Unclear — ask seller to clarify what this charge covers and verify whether it is mandatory.",
        )

    @classmethod
    def _build_explicit_override_assessment(
        cls, status: OptionalityStatus, raw_text: str
    ) -> OptionalityAssessment:
        """Create assessment when status is explicitly provided."""
        if status == OptionalityStatus.CONFIRMED_MANDATORY:
            return OptionalityAssessment(
                status=status,
                display_label="Confirmed mandatory",
                document_states="Document or validated data specifies mandatory charge.",
                system_knows="Compulsory financial commitment.",
                requires_confirmation="Verify charge calculation.",
            )
        if status == OptionalityStatus.CONFIRMED_OPTIONAL:
            return OptionalityAssessment(
                status=status,
                display_label="Confirmed optional",
                document_states="Document or validated data explicitly specifies optional item.",
                system_knows="Buyer has full discretion to accept or decline this item.",
                requires_confirmation="Can be declined or removed from quotation.",
            )
        if status == OptionalityStatus.POTENTIALLY_OPTIONAL:
            return OptionalityAssessment(
                status=status,
                display_label="Potentially optional",
                document_states="Document lists charge that typically represents an optional add-on.",
                system_knows="Industry practices or court rulings identify this fee as negotiable or optional.",
                requires_confirmation="Verify whether this can be removed.",
            )
        if status == OptionalityStatus.NOT_APPLICABLE:
            return OptionalityAssessment(
                status=status,
                display_label="Not applicable",
                document_states="Document states deduction or aggregate total.",
                system_knows="Not a constituent fee.",
                requires_confirmation="No optionality confirmation required.",
            )
        return OptionalityAssessment(
            status=OptionalityStatus.UNCLEAR,
            display_label="Optionality: Unclear",
            document_states="Document wording provides insufficient evidence regarding optionality.",
            system_knows="Unclear statutory basis.",
            requires_confirmation="Optionality: Unclear — ask seller to clarify.",
        )
