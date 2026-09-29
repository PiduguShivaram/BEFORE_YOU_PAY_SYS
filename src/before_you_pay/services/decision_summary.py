"""Phase 6: Before You Pay Final Decision Summary Aggregator Service.

Aggregates all pipeline stages (OCR, extraction, canonical taxonomy, deterministic
validation, contextual comparisons, smart questions, and temporal semantics)
into the unified final decision-support payload.

Strict Guardrails:
- Purely deterministic aggregation: No LLM arithmetic.
- No purchase recommendations ("Buy this" / "Don't buy this").
- Factual readiness states (READY_FOR_FINAL_VERIFICATION, REQUIRES_VERIFICATION, INCOMPLETE_INFORMATION).
- Three-tier separate reconciliation (Components, Offers, Quoted Total).
- No double counting of cost review opportunities.
- Preserves explicit amount states (PRESENT, MISSING, UNKNOWN, UNREADABLE, ZERO, NOT_APPLICABLE).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from before_you_pay.models.analysis import (
    ContextualFinding,
    DecisionFlag,
    SupportingDocumentAnalysis,
    ValidationCheck,
    ValidationStatus,
)
from before_you_pay.models.decision_summary import (
    AttentionItem,
    BeforeYouPayChecklist,
    BeforeYouPayChecklistItem,
    BeforeYouPayFinalSummary,
    CanonicalFinancialSummaryItem,
    ChecklistItemStatus,
    CostReviewOpportunity,
    DecisionHero,
    InformationCompleteness,
    PaymentReadinessState,
    ReconciliationThreeTier,
    SupportingDocComparison,
    WaysToReviewCostSummary,
)
from before_you_pay.models.document import (
    AmountState,
    ChargeNature,
    ComponentCategory,
    StructuredFinancialDocument,
)


def _fmt_curr(val: float | None, currency: str = "INR") -> str:
    """Format currency string cleanly."""
    if val is None:
        return "Unavailable"
    symbol = (
        "₹"
        if currency.upper() in ("INR", "RS", "RUPEES")
        else ("$" if currency.upper() == "USD" else f"{currency} ")
    )
    return f"{symbol}{val:,.2f}"


class BeforeYouPayDecisionSummaryService:
    """Deterministic aggregator compiling the canonical Before You Pay final decision summary."""

    @classmethod
    def build_summary(
        cls,
        document: StructuredFinancialDocument,
        validation_checks: list[ValidationCheck],
        flags: list[DecisionFlag] | None = None,
        smart_questions: list[Any] | None = None,
        contextual_findings: list[ContextualFinding] | None = None,
        suggested_message: str | None = None,
        supporting_document_analysis: SupportingDocumentAnalysis | None = None,
    ) -> BeforeYouPayFinalSummary:
        flags = flags or []
        smart_questions = smart_questions or []
        contextual_findings = contextual_findings or []
        currency = document.currency or "INR"

        # ── 1. Quoted Total & Decision Hero ──
        total_field = document.total_amount
        quoted_total = (
            float(total_field.normalized_value)
            if total_field and isinstance(total_field.normalized_value, (int, float))
            else None
        )
        amount_state = total_field.amount_state if total_field else AmountState.MISSING

        if amount_state == AmountState.ZERO:
            formatted_total = _fmt_curr(0.0, currency)
        elif quoted_total is not None and amount_state == AmountState.PRESENT:
            formatted_total = _fmt_curr(quoted_total, currency)
        elif amount_state == AmountState.UNREADABLE:
            formatted_total = "Total unreadable"
        elif amount_state == AmountState.UNKNOWN:
            formatted_total = "Total unknown"
        elif amount_state == AmountState.NOT_APPLICABLE:
            formatted_total = "Not applicable"
        else:
            formatted_total = "Total unavailable"

        # Balance Due & Payment Status
        balance_due = None
        if (
            hasattr(document, "balance_due")
            and document.balance_due
            and isinstance(document.balance_due.normalized_value, (int, float))
        ):
            balance_due = float(document.balance_due.normalized_value)

        payment_status = "Unpaid"
        if hasattr(document, "payment_status") and document.payment_status:
            payment_status = str(document.payment_status.normalized_value or "Unpaid").title()
        elif balance_due is not None and balance_due == 0.0:
            payment_status = "Paid"

        # Determine Readiness State & Reasons
        readiness_reasons: list[str] = []
        readiness_state = PaymentReadinessState.READY_FOR_FINAL_VERIFICATION

        if amount_state in (AmountState.MISSING, AmountState.UNKNOWN, AmountState.UNREADABLE):
            readiness_state = PaymentReadinessState.INCOMPLETE_INFORMATION
            readiness_reasons.append(
                "Quoted total could not be deterministically determined from the document."
            )

        failed_checks = [c for c in validation_checks if c.status == ValidationStatus.FAIL]
        for fc in failed_checks:
            delta_str = (
                f" ({_fmt_curr(fc.absolute_delta, currency)} difference)"
                if fc.absolute_delta
                else ""
            )
            readiness_reasons.append(f"{fc.message}{delta_str}")
            if readiness_state != PaymentReadinessState.INCOMPLETE_INFORMATION:
                readiness_state = PaymentReadinessState.REQUIRES_VERIFICATION

        for cf in contextual_findings:
            if "overlap" in cf.finding_type.lower() or "overlap" in cf.title.lower():
                readiness_reasons.append(
                    f"Potential coverage overlap identified in supporting document: {cf.title}"
                )
                if readiness_state != PaymentReadinessState.INCOMPLETE_INFORMATION:
                    readiness_state = PaymentReadinessState.REQUIRES_VERIFICATION

        # Check for unverified charges (questionable dealer charges or unexplained items)
        for comp in document.cost_breakdown:
            cat = comp.canonical_category or comp.category.to_canonical_category()
            is_questionable = cat in (
                ComponentCategory.DEALER_CHARGE,
                ComponentCategory.SERVICE,
                ComponentCategory.OTHER_FEE,
                ComponentCategory.OTHER,
                ComponentCategory.UNKNOWN,
            )
            if is_questionable and comp.requires_verification:
                comp_amt_str = (
                    f" ({_fmt_curr(float(comp.amount.normalized_value), currency)})"
                    if comp.amount and comp.amount.normalized_value is not None
                    else ""
                )
                readiness_reasons.append(
                    f"Quoted charge '{comp.name}'{comp_amt_str} requires seller verification."
                )
                if readiness_state != PaymentReadinessState.INCOMPLETE_INFORMATION:
                    readiness_state = PaymentReadinessState.REQUIRES_VERIFICATION

        if readiness_state == PaymentReadinessState.INCOMPLETE_INFORMATION:
            review_status = "Amount requires verification"
        elif readiness_state == PaymentReadinessState.REQUIRES_VERIFICATION:
            review_status = "Review before paying"
        else:
            review_status = "Ready for verification"

        hero = DecisionHero(
            quoted_total=quoted_total,
            stated_total=quoted_total,
            formatted_total=formatted_total,
            currency=currency,
            payment_status=payment_status,
            balance_due=balance_due,
            formatted_balance_due=_fmt_curr(balance_due, currency)
            if balance_due is not None
            else None,
            review_status=review_status,
            readiness_state=readiness_state,
            readiness_reasons=readiness_reasons,
        )

        # ── 2. Three-Tier Reconciliation ──
        # Tier 1: Component Reconciliation
        subtotal_check = next(
            (
                c
                for c in validation_checks
                if c.check_code in ("QUOTATION_SUBTOTAL_CONSISTENCY", "ARITHMETIC_LINE_ITEMS_SUM")
            ),
            None,
        )
        if subtotal_check:
            comp_status = (
                "PASS"
                if subtotal_check.status == ValidationStatus.PASS
                else "REQUIRES_VERIFICATION"
            )
            comp_delta = subtotal_check.absolute_delta
            comp_expl = subtotal_check.message
        else:
            comp_status = "NOT_APPLICABLE"
            comp_delta = None
            comp_expl = "No component subtotal breakdown present."

        # Tier 2: Offers / Deductions Reconciliation
        offers_check = next(
            (c for c in validation_checks if "OFFER" in c.check_code or "DISCOUNT" in c.check_code),
            None,
        )
        discount_amount = (
            float(document.discount_amount.normalized_value)
            if document.discount_amount and document.discount_amount.normalized_value is not None
            else 0.0
        )
        if offers_check:
            offers_status = (
                "PASS" if offers_check.status == ValidationStatus.PASS else "REQUIRES_VERIFICATION"
            )
            offers_delta = offers_check.absolute_delta
            offers_expl = offers_check.message
        elif discount_amount > 0:
            offers_status = "PASS"
            offers_delta = 0.0
            offers_expl = (
                f"Stated discounts of {_fmt_curr(discount_amount, currency)} accounted for."
            )
        else:
            offers_status = "NOT_APPLICABLE"
            offers_delta = None
            offers_expl = "No discounts or deductions claimed."

        # Tier 3: Quoted Total Reconciliation
        total_check = next(
            (
                c
                for c in validation_checks
                if c.check_code
                in ("QUOTATION_NET_TOTAL_CONSISTENCY", "ARITHMETIC_TOTAL_CONSISTENCY")
            ),
            None,
        )
        if total_check:
            tot_status = (
                "PASS" if total_check.status == ValidationStatus.PASS else "REQUIRES_VERIFICATION"
            )
            tot_delta = total_check.absolute_delta
            tot_expl = total_check.message
        else:
            tot_status = "NOT_APPLICABLE"
            tot_delta = None
            tot_expl = "Total reconciliation could not be evaluated."

        reconciliation = ReconciliationThreeTier(
            component_reconciliation_status=comp_status,
            component_reconciliation_delta=comp_delta,
            component_reconciliation_explanation=comp_expl,
            offers_reconciliation_status=offers_status,
            offers_reconciliation_delta=offers_delta,
            offers_reconciliation_explanation=offers_expl,
            quoted_total_reconciliation_status=tot_status,
            quoted_total_reconciliation_delta=tot_delta,
            quoted_total_reconciliation_explanation=tot_expl,
        )

        # ── 3. Canonical Financial Summary ──
        # Group and summarize by canonical category, only including existing components
        financial_summary: list[CanonicalFinancialSummaryItem] = []
        category_totals: dict[ComponentCategory, float] = {}
        category_states: dict[ComponentCategory, AmountState] = {}
        category_names: dict[ComponentCategory, str] = {}
        category_natures: dict[ComponentCategory, ChargeNature] = {}

        for comp in document.cost_breakdown:
            c_cat = comp.canonical_category or comp.category.to_canonical_category()
            val = (
                float(comp.amount.normalized_value)
                if comp.amount and comp.amount.normalized_value is not None
                else 0.0
            )
            st = comp.amount.amount_state if comp.amount else AmountState.UNKNOWN
            nature = comp.charge_nature or ChargeNature.CHARGE

            category_totals[c_cat] = category_totals.get(c_cat, 0.0) + (
                val if not nature.is_deduction else -val
            )
            category_states[c_cat] = st
            category_names[c_cat] = c_cat.value.replace("_", " ").title()
            category_natures[c_cat] = nature

        # Also incorporate standard document fields if not already captured
        if (
            document.subtotal
            and ComponentCategory.BASE_PRICE not in category_totals
            and isinstance(document.subtotal.normalized_value, (int, float))
        ):
            category_totals[ComponentCategory.BASE_PRICE] = float(
                document.subtotal.normalized_value
            )
            category_states[ComponentCategory.BASE_PRICE] = document.subtotal.amount_state
            category_names[ComponentCategory.BASE_PRICE] = "Subtotal / Base Price"
            category_natures[ComponentCategory.BASE_PRICE] = ChargeNature.CHARGE

        if (
            document.tax_amount
            and ComponentCategory.TAX_OR_STATUTORY not in category_totals
            and isinstance(document.tax_amount.normalized_value, (int, float))
        ):
            category_totals[ComponentCategory.TAX_OR_STATUTORY] = float(
                document.tax_amount.normalized_value
            )
            category_states[ComponentCategory.TAX_OR_STATUTORY] = document.tax_amount.amount_state
            category_names[ComponentCategory.TAX_OR_STATUTORY] = "Taxes & Statutory"
            category_natures[ComponentCategory.TAX_OR_STATUTORY] = ChargeNature.TAX

        if (
            document.shipping_amount
            and ComponentCategory.DEALER_CHARGE not in category_totals
            and isinstance(document.shipping_amount.normalized_value, (int, float))
        ):
            category_totals[ComponentCategory.DEALER_CHARGE] = float(
                document.shipping_amount.normalized_value
            )
            category_states[ComponentCategory.DEALER_CHARGE] = document.shipping_amount.amount_state
            category_names[ComponentCategory.DEALER_CHARGE] = "Shipping & Logistics"
            category_natures[ComponentCategory.DEALER_CHARGE] = ChargeNature.CHARGE

        if (
            document.discount_amount
            and ComponentCategory.DISCOUNT not in category_totals
            and isinstance(document.discount_amount.normalized_value, (int, float))
        ):
            category_totals[ComponentCategory.DISCOUNT] = -abs(
                float(document.discount_amount.normalized_value)
            )
            category_states[ComponentCategory.DISCOUNT] = document.discount_amount.amount_state
            category_names[ComponentCategory.DISCOUNT] = "Discounts & Offers"
            category_natures[ComponentCategory.DISCOUNT] = ChargeNature.DISCOUNT

        for cat, amt in category_totals.items():
            st = category_states.get(cat, AmountState.PRESENT)
            name = category_names.get(cat, cat.value.title())
            nature = category_natures.get(cat, ChargeNature.CHARGE)
            is_ded = nature.is_deduction or amt < 0

            if st == AmountState.ZERO or amt == 0.0:
                fmt = f"{_fmt_curr(0.0, currency)} (Included)"
            elif st == AmountState.PRESENT:
                fmt = f"-{_fmt_curr(abs(amt), currency)}" if is_ded else _fmt_curr(amt, currency)
            else:
                fmt = st.value.replace("_", " ").title()

            financial_summary.append(
                CanonicalFinancialSummaryItem(
                    canonical_category=cat,
                    name=name,
                    amount=amt,
                    amount_state=st,
                    charge_nature=nature,
                    formatted_amount=fmt,
                    is_deduction=is_ded,
                )
            )

        # ── 4. Attention Items ──
        attention_items: list[AttentionItem] = []

        # From arithmetic check failures:
        for fc in failed_checks:
            delta_val = fc.absolute_delta
            attention_items.append(
                AttentionItem(
                    title="Amount discrepancy",
                    category="Arithmetic Verification",
                    amount=delta_val,
                    formatted_amount=_fmt_curr(delta_val, currency)
                    if delta_val is not None
                    else "",
                    reason=fc.message,
                    confidence=1.0,
                    evidence=f"Deterministic arithmetic verification: {fc.check_code}",
                    action_or_question=f"Ask seller to explain the {_fmt_curr(delta_val, currency)} difference before paying.",
                )
            )

        # From contextual findings (supporting doc overlaps):
        for cf in contextual_findings:
            title = (
                "Potential overlap"
                if "overlap" in cf.finding_type.lower() or "overlap" in cf.title.lower()
                else cf.title
            )
            amt = cf.primary_amount or cf.supporting_amount
            ev_text = cf.primary_evidence[0].raw_text if cf.primary_evidence else cf.description
            q_text = (
                cf.questions_to_ask[0]
                if cf.questions_to_ask
                else "Verify whether existing policy satisfies coverage requirement."
            )

            attention_items.append(
                AttentionItem(
                    title=title,
                    category="Coverage & Duplication",
                    amount=amt,
                    formatted_amount=_fmt_curr(amt, currency) if amt is not None else "",
                    reason=cf.description,
                    confidence=cf.confidence,
                    evidence=ev_text,
                    action_or_question=q_text,
                )
            )

        # From questionable/dealer ancillary charges:
        for comp in document.cost_breakdown:
            cat = comp.canonical_category or comp.category.to_canonical_category()
            c_amt = (
                float(comp.amount.normalized_value)
                if comp.amount and comp.amount.normalized_value is not None
                else None
            )
            ev_str = (
                comp.amount.provenance.raw_text
                if comp.amount and comp.amount.provenance
                else comp.raw_label or comp.name
            )
            page_no = (
                comp.amount.provenance.page_number
                if comp.amount
                and comp.amount.provenance
                and hasattr(comp.amount.provenance, "page_number")
                else 1
            )

            if (
                cat in (ComponentCategory.DEALER_CHARGE, ComponentCategory.SERVICE)
                and comp.requires_verification
            ):
                attention_items.append(
                    AttentionItem(
                        title="Potentially negotiable",
                        category="Dealer Charges",
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        reason=f"Ancillary fee '{comp.name}' is non-statutory and frequently negotiable.",
                        confidence=0.9,
                        evidence=ev_str,
                        action_or_question=f"Ask whether the {_fmt_curr(c_amt, currency)} {comp.name} can be waived or reduced.",
                        related_component_id=comp.component_id,
                        page_number=page_no,
                        provenance_text=ev_str,
                    )
                )
            elif (
                cat in (ComponentCategory.OTHER, ComponentCategory.UNKNOWN)
                and comp.requires_verification
            ):
                attention_items.append(
                    AttentionItem(
                        title="Unexplained charge",
                        category="Unclear Line Item",
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        reason=f"Charge '{comp.name}' has no standard statutory or product definition.",
                        confidence=0.85,
                        evidence=ev_str,
                        action_or_question=f"Ask the provider to explain what the {_fmt_curr(c_amt, currency)} charge covers.",
                        related_component_id=comp.component_id,
                        page_number=page_no,
                        provenance_text=ev_str,
                    )
                )
            elif cat == ComponentCategory.WARRANTY and comp.requires_verification:
                attention_items.append(
                    AttentionItem(
                        title="Potentially optional",
                        category="Warranty",
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        reason=f"Extended warranty '{comp.name}' is an elective protection product.",
                        confidence=0.9,
                        evidence=ev_str,
                        action_or_question=f"Confirm if the {_fmt_curr(c_amt, currency)} warranty is optional before paying.",
                        related_component_id=comp.component_id,
                        page_number=page_no,
                        provenance_text=ev_str,
                    )
                )

        if not attention_items:
            attention_items.append(
                AttentionItem(
                    title="No critical attention items",
                    category="Verification",
                    amount=None,
                    formatted_amount="",
                    reason="Nothing requiring additional verification was identified from the available document evidence.",
                    confidence=1.0,
                    evidence="Document review complete",
                    action_or_question="Confirm final payment terms with provider.",
                )
            )

        # ── 5. Ways to Review This Cost (Phase 5 integration) ──
        # The 6 canonical categories:
        # 1. Potentially Optional
        # 2. Potentially Negotiable
        # 3. Alternatives to Compare
        # 4. Potential Overlap
        # 5. Amount Discrepancy
        # 6. Unexplained Charge
        opportunities: list[CostReviewOpportunity] = []
        active_cats: set[str] = set()
        component_to_opp_ids: dict[str, list[UUID]] = {}

        # 1. Discrepancies
        for fc in failed_checks:
            opp_id = uuid4()
            d_amt = fc.absolute_delta
            active_cats.add("Amount Discrepancy")
            opportunities.append(
                CostReviewOpportunity(
                    opportunity_id=opp_id,
                    category="Amount Discrepancy",
                    component="Arithmetic Subtotal / Total",
                    amount=d_amt,
                    formatted_amount=_fmt_curr(d_amt, currency) if d_amt is not None else "",
                    potential_amount_to_review=d_amt,
                    formatted_potential_amount=_fmt_curr(d_amt, currency)
                    if d_amt is not None
                    else "",
                    evidence=f"Validation Check: {fc.check_code}",
                    explanation=fc.message,
                    suggested_action=f"Request provider to reconcile the {_fmt_curr(d_amt, currency)} math difference.",
                )
            )

        # 2. Overlaps
        for cf in contextual_findings:
            if "overlap" in cf.finding_type.lower() or "overlap" in cf.title.lower():
                opp_id = uuid4()
                o_amt = cf.primary_amount or cf.supporting_amount
                active_cats.add("Potential Overlap")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Potential Overlap",
                        component=cf.title,
                        amount=o_amt,
                        formatted_amount=_fmt_curr(o_amt, currency) if o_amt is not None else "",
                        potential_amount_to_review=o_amt,
                        formatted_potential_amount=_fmt_curr(o_amt, currency)
                        if o_amt is not None
                        else "",
                        evidence=cf.description,
                        explanation=f"Supporting document references existing coverage for {cf.title}.",
                        suggested_action="Verify if existing coverage satisfies this requirement.",
                    )
                )

        # 3. Components (Optional, Negotiable, Alternative, Unexplained)
        for comp in document.cost_breakdown:
            cat = comp.canonical_category or comp.category.to_canonical_category()
            c_amt = (
                float(comp.amount.normalized_value)
                if comp.amount and comp.amount.normalized_value is not None
                else None
            )
            ev_str = (
                comp.amount.provenance.raw_text
                if comp.amount and comp.amount.provenance
                else comp.name
            )

            if cat == ComponentCategory.WARRANTY:
                opp_id = uuid4()
                active_cats.add("Potentially Optional")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Potentially Optional",
                        component=comp.name,
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        potential_amount_to_review=c_amt,
                        formatted_potential_amount=_fmt_curr(c_amt, currency)
                        if c_amt is not None
                        else "",
                        evidence=ev_str,
                        explanation="Extended warranty is optional and can be declined or deferred.",
                        suggested_action="Ask whether extended warranty can be opted out of.",
                        related_component_id=comp.component_id,
                    )
                )
                component_to_opp_ids.setdefault(comp.name, []).append(opp_id)

            elif cat in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE):
                opp_id = uuid4()
                active_cats.add("Potentially Optional")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Potentially Optional",
                        component=comp.name,
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        potential_amount_to_review=c_amt,
                        formatted_potential_amount=_fmt_curr(c_amt, currency)
                        if c_amt is not None
                        else "",
                        evidence=ev_str,
                        explanation="Accessories are elective additions not required for sale completion.",
                        suggested_action="Request itemized accessory list and select only preferred items.",
                        related_component_id=comp.component_id,
                    )
                )
                component_to_opp_ids.setdefault(comp.name, []).append(opp_id)

            elif cat in (ComponentCategory.DEALER_CHARGE, ComponentCategory.SERVICE):
                opp_id = uuid4()
                active_cats.add("Potentially Negotiable")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Potentially Negotiable",
                        component=comp.name,
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        potential_amount_to_review=c_amt,
                        formatted_potential_amount=_fmt_curr(c_amt, currency)
                        if c_amt is not None
                        else "",
                        evidence=ev_str,
                        explanation=f"{comp.name} is a dealer surcharge and subject to commercial negotiation.",
                        suggested_action="Ask dealer to waive or discount this charge.",
                        related_component_id=comp.component_id,
                    )
                )
                component_to_opp_ids.setdefault(comp.name, []).append(opp_id)

            elif cat == ComponentCategory.INSURANCE:
                opp_id = uuid4()
                active_cats.add("Alternatives to Compare")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Alternatives to Compare",
                        component=comp.name,
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        potential_amount_to_review=c_amt,
                        formatted_potential_amount=_fmt_curr(c_amt, currency)
                        if c_amt is not None
                        else "",
                        evidence=ev_str,
                        explanation="Buyers have the right to compare external market insurance quotes with equivalent terms.",
                        suggested_action="Request policy schedule and obtain 1–2 independent comparison quotes.",
                        related_component_id=comp.component_id,
                    )
                )
                component_to_opp_ids.setdefault(comp.name, []).append(opp_id)

            elif (
                cat in (ComponentCategory.OTHER, ComponentCategory.UNKNOWN)
                and comp.requires_verification
            ):
                opp_id = uuid4()
                active_cats.add("Unexplained Charge")
                opportunities.append(
                    CostReviewOpportunity(
                        opportunity_id=opp_id,
                        category="Unexplained Charge",
                        component=comp.name,
                        amount=c_amt,
                        formatted_amount=_fmt_curr(c_amt, currency) if c_amt is not None else "",
                        potential_amount_to_review=c_amt,
                        formatted_potential_amount=_fmt_curr(c_amt, currency)
                        if c_amt is not None
                        else "",
                        evidence=ev_str,
                        explanation="Line item has unclear description and purpose.",
                        suggested_action="Ask what service or item this charge provides.",
                        related_component_id=comp.component_id,
                    )
                )
                component_to_opp_ids.setdefault(comp.name, []).append(opp_id)

        # Link opportunities referring to the same component to prevent double counting
        for _comp_name, opp_ids in component_to_opp_ids.items():
            if len(opp_ids) > 1:
                for opp in opportunities:
                    if opp.opportunity_id in opp_ids:
                        other_ids = [oid for oid in opp_ids if oid != opp.opportunity_id]
                        # Create updated copy with linked ids
                        idx = opportunities.index(opp)
                        opportunities[idx] = opp.model_copy(
                            update={"linked_opportunity_ids": other_ids}
                        )

        ways_to_review = WaysToReviewCostSummary(
            active_categories=sorted(list(active_cats)),
            opportunities=opportunities,
        )

        # ── 6. Supporting Document Context ──
        supp_comparisons: list[SupportingDocComparison] | None = None
        if contextual_findings:
            supp_comparisons = []
            for cf in contextual_findings:
                supp_text = (
                    cf.supporting_evidence[0].raw_text
                    if cf.supporting_evidence
                    else "Supporting document record"
                )
                supp_comparisons.append(
                    SupportingDocComparison(
                        comparison_type="Potential Overlap"
                        if "overlap" in cf.finding_type.lower() or "overlap" in cf.title.lower()
                        else cf.finding_type.value,
                        title=cf.title,
                        current_charge_name=cf.primary_evidence[0].label
                        if cf.primary_evidence and cf.primary_evidence[0].label
                        else cf.title,
                        current_charge_amount=cf.primary_amount,
                        supporting_document_text=supp_text,
                        finding_description=cf.description,
                        action_guidance=cf.what_to_verify[0]
                        if cf.what_to_verify
                        else "Verify whether quoted charge overlaps with supporting document terms.",
                    )
                )

        # ── 7. Questions to Ask ──
        questions_to_ask: list[str] = []
        if smart_questions:
            for sq in smart_questions:
                q_text = getattr(sq, "question", str(sq))
                if q_text and q_text not in questions_to_ask:
                    questions_to_ask.append(q_text)
        if not questions_to_ask:
            for item in attention_items:
                if item.action_or_question and item.action_or_question not in questions_to_ask:
                    questions_to_ask.append(item.action_or_question)

        # ── 8. Message to Seller ──
        if not suggested_message:
            msg_items = [f"{i + 1}. {q}" for i, q in enumerate(questions_to_ask[:4])]
            suggested_message = (
                "Hi, I reviewed the quotation and wanted to clarify a few items before proceeding:\n\n"
                + "\n".join(msg_items)
                + "\n\nPlease confirm these items and provide a revised quotation if applicable. Thank you."
            )

        # ── 9. Before You Pay Checklist ──
        checklist_items = [
            BeforeYouPayChecklistItem(
                key="quoted_total_verified",
                title="Quoted total verified",
                status=ChecklistItemStatus.VERIFIED
                if tot_status == "PASS"
                else ChecklistItemStatus.REQUIRES_VERIFICATION,
                detail="Final quoted total matches expected mathematical reconciliation."
                if tot_status == "PASS"
                else "Quoted total requires verification against constituent charges.",
                evidence=tot_expl,
            ),
            BeforeYouPayChecklistItem(
                key="component_calculations_checked",
                title="Component calculations checked",
                status=ChecklistItemStatus.VERIFIED
                if comp_status == "PASS"
                else ChecklistItemStatus.REQUIRES_VERIFICATION,
                detail="All itemized breakdown figures sum up to stated subtotal."
                if comp_status == "PASS"
                else f"Component calculation difference: {_fmt_curr(comp_delta, currency)}.",
                evidence=comp_expl,
            ),
            BeforeYouPayChecklistItem(
                key="discounts_offers_verified",
                title="Discounts/offers verified",
                status=ChecklistItemStatus.VERIFIED
                if offers_status == "PASS"
                else (
                    ChecklistItemStatus.NOT_APPLICABLE
                    if offers_status == "NOT_APPLICABLE"
                    else ChecklistItemStatus.REQUIRES_VERIFICATION
                ),
                detail=offers_expl,
                evidence=offers_expl,
            ),
            BeforeYouPayChecklistItem(
                key="optional_charges_reviewed",
                title="Optional charges reviewed",
                status=ChecklistItemStatus.REQUIRES_VERIFICATION
                if any(o.category == "Potentially Optional" for o in opportunities)
                else ChecklistItemStatus.VERIFIED,
                detail="Elective protection or accessories identified that can be opted out of."
                if any(o.category == "Potentially Optional" for o in opportunities)
                else "No unverified optional add-ons identified.",
            ),
            BeforeYouPayChecklistItem(
                key="negotiable_charges_questioned",
                title="Negotiable charges questioned",
                status=ChecklistItemStatus.REQUIRES_VERIFICATION
                if any(o.category == "Potentially Negotiable" for o in opportunities)
                else ChecklistItemStatus.VERIFIED,
                detail="Non-statutory dealer surcharges present for commercial negotiation."
                if any(o.category == "Potentially Negotiable" for o in opportunities)
                else "No commercial surcharges requiring reduction.",
            ),
            BeforeYouPayChecklistItem(
                key="supporting_documents_compared",
                title="Supporting documents compared",
                status=ChecklistItemStatus.REQUIRES_VERIFICATION
                if supp_comparisons
                else ChecklistItemStatus.NOT_APPLICABLE,
                detail=f"{len(supp_comparisons)} contextual comparison(s) found with prior records."
                if supp_comparisons
                else "No supporting historical documents attached for cross-reference.",
            ),
            BeforeYouPayChecklistItem(
                key="discrepancies_clarified",
                title="Discrepancies clarified",
                status=ChecklistItemStatus.REQUIRES_VERIFICATION
                if failed_checks
                else ChecklistItemStatus.VERIFIED,
                detail=f"{len(failed_checks)} arithmetic discrepancy(ies) require clarification."
                if failed_checks
                else "No arithmetic discrepancies detected.",
            ),
            BeforeYouPayChecklistItem(
                key="unexplained_charges_clarified",
                title="Unexplained charges clarified",
                status=ChecklistItemStatus.REQUIRES_VERIFICATION
                if any(o.category == "Unexplained Charge" for o in opportunities)
                else ChecklistItemStatus.VERIFIED,
                detail="Unclear line items identified requiring provider explanation."
                if any(o.category == "Unexplained Charge" for o in opportunities)
                else "All line items clearly identified.",
            ),
            BeforeYouPayChecklistItem(
                key="final_revised_amount_confirmed",
                title="Final revised amount confirmed",
                status=ChecklistItemStatus.PENDING_USER_ACTION,
                detail="Pending final seller response and revised invoice confirmation.",
            ),
        ]

        completed_count = sum(
            1 for item in checklist_items if item.status == ChecklistItemStatus.VERIFIED
        )
        overall_checklist_status = (
            ChecklistItemStatus.VERIFIED
            if completed_count
            >= len([i for i in checklist_items if i.status != ChecklistItemStatus.NOT_APPLICABLE])
            - 1
            else ChecklistItemStatus.REQUIRES_VERIFICATION
        )

        checklist = BeforeYouPayChecklist(
            items=checklist_items,
            overall_status=overall_checklist_status,
            completed_count=completed_count,
            total_count=len(checklist_items),
        )

        # ── 10. Information Completeness ──
        missing_fields: list[str] = []
        if amount_state in (AmountState.MISSING, AmountState.UNKNOWN, AmountState.UNREADABLE):
            missing_fields.append("Total Amount")
        if not document.subtotal and not document.line_items and not document.cost_breakdown:
            missing_fields.append("Itemized Breakdown")
        if not document.issued_date:
            missing_fields.append("Issued Date")

        is_calc = quoted_total is not None and (
            document.subtotal is not None
            or bool(document.cost_breakdown)
            or bool(document.line_items)
        )
        is_explain = (
            bool(document.cost_breakdown) or bool(document.line_items) or bool(document.subtotal)
        )
        is_verify = is_calc and amount_state not in (AmountState.UNREADABLE, AmountState.UNKNOWN)

        if missing_fields:
            note = f"Some information could not be determined from the document: {', '.join(missing_fields)}."
        else:
            note = "Document contains complete financial figures for calculation, explanation, and verification."

        completeness = InformationCompleteness(
            is_complete_to_calculate=is_calc,
            is_complete_to_explain=is_explain,
            is_complete_to_verify=is_verify,
            missing_or_uncertain_fields=missing_fields,
            completeness_note=note,
        )

        return BeforeYouPayFinalSummary(
            summary_id=uuid4(),
            document_id=document.document_id,
            user_id=document.user_id,
            hero=hero,
            reconciliation=reconciliation,
            financial_summary=financial_summary,
            attention_items=attention_items,
            ways_to_review_cost=ways_to_review,
            supporting_document_context=supp_comparisons,
            questions_to_ask=questions_to_ask,
            suggested_message=suggested_message,
            checklist=checklist,
            completeness=completeness,
        )
