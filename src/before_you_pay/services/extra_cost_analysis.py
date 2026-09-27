"""Extra Cost and Cost-Reduction Analysis Service (Phase 4).

Identifies financial components that deserve buyer scrutiny because they are:
- Potentially optional
- Additional to the base price
- Dealer-added
- Bundled services / packages
- Accessories or extended warranties
- Convenience / handling / processing fees
- Unclear or unexplained charges
- Possible duplicates

RULES:
- Never call a charge "unnecessary" without evidence.
- Use neutral labels only: "Potentially optional", "Additional charge",
  "Dealer-added charge", "Unclear charge", "Possible duplicate", "Requires verification".
- Only display "potential saving" when removal is mathematically meaningful.
- Language: "If this charge is optional and you choose not to purchase it,
  up to ₹X could be removed from the quoted amount."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from before_you_pay.models.document import (
    ChargeNature,
    ComponentCategory,
    FinancialComponent,
    OptionalityStatus,
)


class ExtraCostFlagType(StrEnum):
    """Neutral classification labels for flagged extra costs."""

    POTENTIALLY_OPTIONAL = "potentially_optional"
    ADDITIONAL_CHARGE = "additional_charge"
    DEALER_ADDED = "dealer_added"
    BUNDLED_PACKAGE = "bundled_package"
    UNCLEAR_CHARGE = "unclear_charge"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    REQUIRES_VERIFICATION = "requires_verification"


@dataclass(frozen=True)
class ExtraCostFlag:
    """A single flagged cost component with structured analysis fields.

    Matches the Phase 4 specification:
    - WHAT: The component name
    - AMOUNT: The monetary value
    - WHY FLAGGED: Reason this charge deserves scrutiny
    - WHAT TO VERIFY: Actionable verification guidance
    - POTENTIAL SAVING: Amount that could be removed (only when meaningful)
    - SAVING LANGUAGE: Carefully worded neutral phrasing
    """

    component_id: str
    flag_type: ExtraCostFlagType
    flag_label: str

    # WHAT
    what: str
    normalized_name: str
    category: str

    # AMOUNT
    amount: float

    # WHY FLAGGED
    why_flagged: str

    # WHAT TO VERIFY
    what_to_verify: str

    # POTENTIAL SAVING — only when mathematically meaningful
    potential_saving: float | None = None
    saving_language: str | None = None

    # Bundled package questions (when applicable)
    bundled_questions: list[str] = field(default_factory=list)

    # Source evidence
    evidence: str | None = None
    optionality_status: str | None = None


@dataclass(frozen=True)
class ExtraCostAnalysisResult:
    """Complete extra cost analysis for a document's cost breakdown.

    Contains all flagged costs, total potential reduction, and summary statistics.
    """

    flagged_costs: list[ExtraCostFlag]
    total_potential_reduction: float
    total_flagged_count: int
    total_charges_analyzed: int
    reduction_summary: str


# ── Categories that are NEVER flagged as extra costs ──
_NEVER_FLAG_CATEGORIES: frozenset[ComponentCategory] = frozenset({
    ComponentCategory.BASE_PRICE,
    ComponentCategory.EX_SHOWROOM_PRICE,
    ComponentCategory.TCS,
    ComponentCategory.GST,
    ComponentCategory.TAX,
    ComponentCategory.ROAD_TAX,
    ComponentCategory.SUBTOTAL,
    ComponentCategory.TOTAL,
    ComponentCategory.AMOUNT_PAID,
    ComponentCategory.BALANCE_DUE,
    ComponentCategory.DISCOUNT,
    ComponentCategory.OFFER,
})

# ── Categories that indicate a dealer-added/bundled charge ──
_DEALER_ADDED_CATEGORIES: frozenset[ComponentCategory] = frozenset({
    ComponentCategory.ACCESSORY,
    ComponentCategory.ACCESSORY_PACKAGE,
    ComponentCategory.DEALER_PACKAGE,
    ComponentCategory.SERVICE_PACKAGE,
})

_BUNDLED_CATEGORIES: frozenset[ComponentCategory] = frozenset({
    ComponentCategory.ACCESSORY_PACKAGE,
    ComponentCategory.DEALER_PACKAGE,
    ComponentCategory.SERVICE_PACKAGE,
})

_FEE_CATEGORIES: frozenset[ComponentCategory] = frozenset({
    ComponentCategory.HANDLING_FEE,
    ComponentCategory.LOGISTICS_FEE,
    ComponentCategory.PROCESSING_FEE,
    ComponentCategory.OTHER_FEE,
})


class ExtraCostAnalysisService:
    """Analyzes a document's cost breakdown to identify charges deserving buyer scrutiny."""

    @classmethod
    def analyze(
        cls,
        components: list[FinancialComponent],
    ) -> ExtraCostAnalysisResult:
        """Scan all financial components and flag those deserving scrutiny.

        Only charges (not deductions/discounts) are analyzed.
        Base price, statutory taxes, and totals are never flagged.
        """
        flagged: list[ExtraCostFlag] = []
        seen_categories: dict[ComponentCategory, list[FinancialComponent]] = {}

        # First pass: index by category for duplicate detection
        charges = [
            c for c in components
            if c.charge_nature == ChargeNature.CHARGE
        ]

        for comp in charges:
            cat = comp.category
            if cat not in seen_categories:
                seen_categories[cat] = []
            seen_categories[cat].append(comp)

        # Second pass: analyze each charge
        for comp in charges:
            cat = comp.category

            # Skip categories that should never be flagged
            if cat in _NEVER_FLAG_CATEGORIES:
                continue

            amt = cls._get_amount(comp)
            if amt <= 0:
                continue

            flag = cls._evaluate_component(comp, amt, seen_categories)
            if flag is not None:
                flagged.append(flag)

        # Calculate totals
        total_reduction = sum(f.potential_saving or 0.0 for f in flagged)
        reduction_summary = cls._build_reduction_summary(flagged, total_reduction)

        return ExtraCostAnalysisResult(
            flagged_costs=flagged,
            total_potential_reduction=total_reduction,
            total_flagged_count=len(flagged),
            total_charges_analyzed=len(charges),
            reduction_summary=reduction_summary,
        )

    @classmethod
    def _evaluate_component(
        cls,
        comp: FinancialComponent,
        amt: float,
        seen_categories: dict[ComponentCategory, list[FinancialComponent]],
    ) -> ExtraCostFlag | None:
        """Evaluate a single component and return a flag if it deserves scrutiny."""
        cat = comp.category
        comp_name = comp.normalized_name or comp.normalized_label or comp.name
        comp_id = str(comp.component_id)
        evidence = comp.evidence or ""
        opt_status = (
            comp.optionality_status.value
            if hasattr(comp.optionality_status, "value")
            else str(comp.optionality_status)
        )

        # ── 1. Check for duplicate charges in the same category ──
        same_cat = seen_categories.get(cat, [])
        if len(same_cat) > 1 and cat not in _NEVER_FLAG_CATEGORIES:
            # Only flag as duplicate if this is not the first occurrence
            first_in_cat = same_cat[0]
            if comp.component_id != first_in_cat.component_id:
                return ExtraCostFlag(
                    component_id=comp_id,
                    flag_type=ExtraCostFlagType.POSSIBLE_DUPLICATE,
                    flag_label="Possible duplicate",
                    what=comp_name,
                    normalized_name=comp_name,
                    category=cat.value if hasattr(cat, "value") else str(cat),
                    amount=amt,
                    why_flagged=(
                        f"Multiple charges in the '{comp_name}' category appear on this quotation. "
                        f"This may indicate a duplicate entry or overlapping charges."
                    ),
                    what_to_verify=(
                        "Verify with the seller whether both charges are correct and represent "
                        "distinct services, or if one is a duplicate that should be removed."
                    ),
                    potential_saving=amt,
                    saving_language=(
                        f"If this is a duplicate charge, up to ₹{amt:,.0f} could be "
                        f"removed from the quoted amount."
                    ),
                    evidence=evidence,
                    optionality_status=opt_status,
                )

        # ── 2. Extended Warranty ──
        if cat == ComponentCategory.EXTENDED_WARRANTY:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.POTENTIALLY_OPTIONAL,
                flag_label="Potentially optional",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "The quotation lists this separately from the base vehicle price. "
                    "Extended warranty is a supplemental coverage contract distinct from "
                    "the standard manufacturer warranty included with the vehicle."
                ),
                what_to_verify=(
                    "Ask whether this is optional and whether removing it changes the quoted price. "
                    "Verify the coverage period, terms, and whether it can be purchased later."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this charge is optional and you choose not to purchase it, "
                    f"up to ₹{amt:,.0f} could be removed from the quoted amount."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 3. Dealer-added / bundled packages ──
        if cat in _BUNDLED_CATEGORIES:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.BUNDLED_PACKAGE,
                flag_label="Bundled package — verify contents",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    f"The quotation includes a bundled package ('{comp_name}') "
                    f"that groups multiple items or services into a single charge."
                ),
                what_to_verify=(
                    "Request an itemized breakdown of what is included in this package. "
                    "Determine whether all bundled components are needed."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this package is optional and you choose not to purchase it, "
                    f"up to ₹{amt:,.0f} could be removed from the quoted amount. "
                    f"Individual components may also be removable."
                ),
                bundled_questions=[
                    "What services are included in this package?",
                    "Are all components required?",
                    "Can individual components be removed or selected separately?",
                    "Is this package mandatory for vehicle delivery?",
                ],
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 4. Individual accessories ──
        if cat == ComponentCategory.ACCESSORY:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.DEALER_ADDED,
                flag_label="Dealer-added charge",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "This accessory is listed as a separate dealer-added charge. "
                    "Consumer protection regulations prohibit dealers from forcing "
                    "mandatory accessory purchases on buyers."
                ),
                what_to_verify=(
                    "Confirm whether this accessory is optional. Ask whether it can be "
                    "removed from the quotation without affecting vehicle delivery."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this accessory is optional and you choose not to purchase it, "
                    f"up to ₹{amt:,.0f} could be removed from the quoted amount."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 5. Handling / logistics / processing / documentation fees ──
        if cat in _FEE_CATEGORIES:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.ADDITIONAL_CHARGE,
                flag_label="Additional charge — verify legitimacy",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "This fee is listed as a separate charge beyond the base price. "
                    "Multiple High Courts and State Transport Departments have ruled "
                    "certain dealer handling, logistics, and documentation charges "
                    "unlawful under Rule 115 of the Central Motor Vehicles Rules."
                ),
                what_to_verify=(
                    "Contest with dealer and request removal. Ask for documentary proof "
                    "of the statutory or contractual basis for this fee."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this fee can be removed or contested, "
                    f"up to ₹{amt:,.0f} could be removed from the quoted amount."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 6. Insurance (purchasable externally) ──
        if cat == ComponentCategory.INSURANCE:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.REQUIRES_VERIFICATION,
                flag_label="Requires verification — external purchase possible",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "Third-party liability insurance is statutory, but purchasing it through "
                    "the dealer is optional. IRDAI guidelines grant buyers the right to "
                    "purchase motor insurance from any licensed insurer."
                ),
                what_to_verify=(
                    "Compare the dealer-quoted premium against independent insurance quotes. "
                    "Verify whether the dealer will accept an externally purchased policy."
                ),
                # No potential_saving — insurance is mandatory, just the source is negotiable
                potential_saving=None,
                saving_language=None,
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 7. FASTag (possible markup) ──
        if cat == ComponentCategory.FASTAG:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.ADDITIONAL_CHARGE,
                flag_label="Additional charge — verify pricing",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "FASTag is mandatory for highway tolling, but official bank issuance "
                    "is typically capped at ~₹500 (including security deposit). "
                    "Dealer quotes sometimes charge inflated figures."
                ),
                what_to_verify=(
                    "Verify if the dealer charge matches official bank/NHAI issuance rates, "
                    "or obtain FASTag directly from a bank or NHAI authorized point of sale."
                ),
                potential_saving=max(0.0, amt - 500.0) if amt > 500.0 else None,
                saving_language=(
                    f"If the FASTag is procured directly at official rates (~₹500), "
                    f"up to ₹{max(0.0, amt - 500.0):,.0f} could be saved."
                ) if amt > 500.0 else None,
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 8. Registration / RC / HSRP (possible dealer markup) ──
        if cat in (ComponentCategory.REGISTRATION, ComponentCategory.RC, ComponentCategory.HSRP):
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.REQUIRES_VERIFICATION,
                flag_label="Requires verification",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "Official RTO registration is legally required, but dealer quotation figures "
                    "for registration-related charges routinely include unauthorized documentation "
                    "fees, agent commissions, and markups beyond the statutory government fee."
                ),
                what_to_verify=(
                    "Request an itemized RTO government receipt to verify the actual statutory fee "
                    "versus any dealer markup included in this amount."
                ),
                # No potential_saving — registration is mandatory, markup amount unknown
                potential_saving=None,
                saving_language=None,
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 9. Standard warranty (should be free) ──
        if cat == ComponentCategory.WARRANTY:
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.REQUIRES_VERIFICATION,
                flag_label="Requires verification",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value,
                amount=amt,
                why_flagged=(
                    "Standard manufacturer warranty is typically included in the vehicle "
                    "purchase price at no additional cost. A separate charge for standard "
                    "warranty may indicate a billing error or hidden fee."
                ),
                what_to_verify=(
                    "Confirm whether this represents the standard manufacturer warranty "
                    "(which should be free) or an additional warranty product."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If the standard warranty is already included in the vehicle price, "
                    f"this ₹{amt:,.0f} charge may be removable."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 10. Unclear / unknown charges ──
        if cat in (ComponentCategory.UNCLEAR, ComponentCategory.UNKNOWN, ComponentCategory.OTHER):
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.UNCLEAR_CHARGE,
                flag_label="Unclear charge",
                what=comp_name,
                normalized_name=comp_name,
                category="unclear",
                amount=amt,
                why_flagged=(
                    "This charge could not be classified into a recognized financial category. "
                    "Its inclusion and purpose are not explained in the quotation."
                ),
                what_to_verify=(
                    "Ask the seller to clarify what this charge covers, whether it is "
                    "mandatory, and request documentary proof of its basis."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this charge is not justified, up to ₹{amt:,.0f} could be "
                    f"removed from the quoted amount."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        # ── 11. Catch-all for any remaining potentially-optional items ──
        if comp.optionality_status in (
            OptionalityStatus.CONFIRMED_OPTIONAL,
            OptionalityStatus.POTENTIALLY_OPTIONAL,
        ):
            return ExtraCostFlag(
                component_id=comp_id,
                flag_type=ExtraCostFlagType.POTENTIALLY_OPTIONAL,
                flag_label="Potentially optional",
                what=comp_name,
                normalized_name=comp_name,
                category=cat.value if hasattr(cat, "value") else str(cat),
                amount=amt,
                why_flagged=(
                    f"This charge ('{comp_name}') has been identified as potentially optional "
                    f"based on document analysis and category assessment."
                ),
                what_to_verify=(
                    "Verify with the seller whether this charge can be removed or is "
                    "required for the purchase."
                ),
                potential_saving=amt,
                saving_language=(
                    f"If this charge is optional and you choose not to purchase it, "
                    f"up to ₹{amt:,.0f} could be removed from the quoted amount."
                ),
                evidence=evidence,
                optionality_status=opt_status,
            )

        return None

    @staticmethod
    def _get_amount(comp: FinancialComponent) -> float:
        """Safely extract the numeric amount from a FinancialComponent."""
        try:
            if hasattr(comp.amount, "normalized_value"):
                return float(comp.amount.normalized_value)
            return float(comp.amount)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _build_reduction_summary(
        flagged: list[ExtraCostFlag],
        total_reduction: float,
    ) -> str:
        """Build a neutral, evidence-appropriate summary of potential reductions."""
        if not flagged:
            return "No charges were flagged for additional scrutiny."

        count = len(flagged)
        removable = [f for f in flagged if f.potential_saving and f.potential_saving > 0]

        if not removable:
            return (
                f"{count} charge{'s' if count > 1 else ''} flagged for verification. "
                f"No charges were identified as directly removable without further investigation."
            )

        return (
            f"{count} charge{'s' if count > 1 else ''} flagged for scrutiny. "
            f"If all potentially removable charges are confirmed optional and declined, "
            f"up to ₹{total_reduction:,.0f} could be removed from the quoted amount. "
            f"Verify each item individually before making decisions."
        )
