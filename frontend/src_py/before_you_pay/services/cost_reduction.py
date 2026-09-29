"""Potential Cost Reduction Summary Service (Phase 7).

Calculates potential cost reduction amounts without promising savings.

RULES:
- This must NOT promise savings.
- Calculate only amounts associated with charges that are:
  - explicitly optional (CONFIRMED_OPTIONAL)
  - potentially optional (POTENTIALLY_OPTIONAL)
  - unclear but removable subject to confirmation (UNCLEAR)
- Separate them into 3 distinct tiers:
  1. CONFIRMED OPTIONAL (Potential removable amount: ₹X)
  2. POTENTIALLY OPTIONAL (Potential amount: ₹Y)
  3. UNCLEAR / NEEDS CONFIRMATION (Amount requiring clarification: ₹Z)
- Calculate:
  "Potential amount worth reviewing: ₹X–₹Y"
  Only calculate a range when the underlying components are independent and mathematically valid.
- Never double-count:
  - discounts
  - offers
  - bundled charges
  - subtotal components
- Do not include mandatory charges in potential savings.
- Do not treat tax/statutory charges as negotiable unless authoritative evidence explicitly supports it.
- Use wording:
  "You may be able to reduce the quoted amount if the seller confirms these charges are optional or removable."
- NEVER use:
  "You can save ₹X."
"""

from __future__ import annotations

from uuid import uuid4

from before_you_pay.models.analysis import (
    PotentialCostReductionSummary,
    ReductionTierItem,
)
from before_you_pay.models.document import (
    ChargeNature,
    ComponentCategory,
    FinancialComponent,
    OptionalityStatus,
)

# Categories that are statutory or structural and NEVER included in potential reductions
_EXCLUDED_CATEGORIES: frozenset[ComponentCategory] = frozenset(
    {
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
    }
)

_STATUTORY_MANDATORY_CATEGORIES: frozenset[ComponentCategory] = frozenset(
    {
        ComponentCategory.REGISTRATION,
        ComponentCategory.RC,
        ComponentCategory.HSRP,
        ComponentCategory.INSURANCE,
    }
)


class PotentialCostReductionService:
    """Service to compute non-committal, evidence-grounded cost reduction summaries."""

    STANDARD_REVIEW_MESSAGE = "You may be able to reduce the quoted amount if the seller confirms these charges are optional or removable."

    @classmethod
    def calculate_summary(
        cls,
        components: list[FinancialComponent],
    ) -> PotentialCostReductionSummary:
        """Scan components and generate a 3-tier potential cost reduction summary without double counting."""
        charges = [c for c in components if c.charge_nature == ChargeNature.CHARGE]

        confirmed_items: list[ReductionTierItem] = []
        potentially_items: list[ReductionTierItem] = []
        unclear_items: list[ReductionTierItem] = []

        seen_item_keys: set[str] = set()

        for comp in charges:
            cat = comp.category
            if cat in _EXCLUDED_CATEGORIES:
                continue

            # Skip confirmed mandatory statutory items
            if comp.optionality_status == OptionalityStatus.CONFIRMED_MANDATORY:
                continue

            # Do not treat statutory charges (Registration, RC, HSRP, Insurance) as negotiable
            # unless authoritative evidence or explicit optionality supports it
            if cat in _STATUTORY_MANDATORY_CATEGORIES:
                if comp.optionality_status != OptionalityStatus.CONFIRMED_OPTIONAL:
                    # Unless authoritative evidence explicitly supports negotiability
                    ev_lower = (comp.evidence or "").lower()
                    if not any(
                        kw in ev_lower
                        for kw in ("negotiable", "waived", "optional", "dealer concession")
                    ):
                        continue

            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat_val in ("ROAD_TAX", "TCS", "GST", "TAX"):
                continue

            amt = cls._get_amount(comp)
            if amt <= 0:
                continue

            # Deduplication key to prevent double counting
            norm_name = (
                (comp.normalized_name or comp.normalized_label or comp.name or "").lower().strip()
            )

            # Prevent double-counting bundled charges
            full_text = f"{comp.name} {comp.raw_label or ''} {comp.normalized_name or ''} {comp.evidence or ''}".lower()
            if (
                "bundled" in full_text
                or "included in package" in full_text
                or "part of package" in full_text
            ):
                continue

            item_key = f"{cat_val}:{norm_name}:{amt}"
            if item_key in seen_item_keys:
                continue
            seen_item_keys.add(item_key)

            evidence_str = comp.evidence or f"Quotation line: '{comp.name} — ₹{amt:,.0f}'"
            comp_id = (
                comp.component_id if isinstance(comp.component_id, uuid4().__class__) else uuid4()
            )

            # ── Tier 1: Confirmed Optional ──
            if comp.optionality_status == OptionalityStatus.CONFIRMED_OPTIONAL:
                confirmed_items.append(
                    ReductionTierItem(
                        component_id=comp_id,
                        name=comp.name,
                        amount=amt,
                        category=cat_val,
                        status_label="Confirmed Optional",
                        evidence=evidence_str,
                    )
                )
                continue

            # ── Tier 3: Unclear / Needs Confirmation ──
            if comp.optionality_status == OptionalityStatus.UNCLEAR or cat in (
                ComponentCategory.OTHER_FEE,
                ComponentCategory.UNKNOWN,
            ):
                unclear_items.append(
                    ReductionTierItem(
                        component_id=comp_id,
                        name=comp.name,
                        amount=amt,
                        category=cat_val,
                        status_label="Requires Clarification",
                        evidence=evidence_str,
                    )
                )
                continue

            # ── Tier 2: Potentially Optional ──
            # Extended warranty, accessories, dealer packages, handling fees, or FASTag markup
            if cat == ComponentCategory.FASTAG:
                if amt > 500:
                    markup = amt - 500
                    potentially_items.append(
                        ReductionTierItem(
                            component_id=comp_id,
                            name=f"{comp.name} (Dealer Markup)",
                            amount=markup,
                            category=cat_val,
                            status_label="Potentially Optional Markup",
                            evidence=evidence_str,
                        )
                    )
                continue

            potentially_items.append(
                ReductionTierItem(
                    component_id=comp_id,
                    name=comp.name,
                    amount=amt,
                    category=cat_val,
                    status_label="Potentially Optional",
                    evidence=evidence_str,
                )
            )

        # Compute tier totals
        confirmed_amt = round(sum(item.amount for item in confirmed_items), 2)
        potentially_amt = round(sum(item.amount for item in potentially_items), 2)
        unclear_amt = round(sum(item.amount for item in unclear_items), 2)

        min_reduction = confirmed_amt
        max_reduction = round(confirmed_amt + potentially_amt + unclear_amt, 2)

        # Range formatting: only calculate a range when underlying components are independent and mathematically valid
        is_range_valid = max_reduction > min_reduction
        if is_range_valid:
            range_display = f"₹{min_reduction:,.0f}–₹{max_reduction:,.0f}"
        elif max_reduction > 0:
            range_display = f"₹{max_reduction:,.0f}"
        else:
            range_display = "₹0"

        return PotentialCostReductionSummary(
            confirmed_optional_amount=confirmed_amt,
            confirmed_optional_items=confirmed_items,
            potentially_optional_amount=potentially_amt,
            potentially_optional_items=potentially_items,
            unclear_confirmation_amount=unclear_amt,
            unclear_confirmation_items=unclear_items,
            min_potential_reduction=min_reduction,
            max_potential_reduction=max_reduction,
            potential_range_display=range_display,
            review_message=cls.STANDARD_REVIEW_MESSAGE,
            is_range_valid=is_range_valid,
            total_charges_reviewed=len(charges),
        )

    @staticmethod
    def _get_amount(comp: FinancialComponent) -> float:
        """Safely extract float amount from a FinancialComponent."""
        try:
            if hasattr(comp.amount, "normalized_value"):
                return float(comp.amount.normalized_value)
            return float(comp.amount)
        except (TypeError, ValueError):
            return 0.0
