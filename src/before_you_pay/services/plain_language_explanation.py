"""Plain-Language Financial Explanation Service (Phase 8).

Generates a concise, evidence-derived plain-language explanation of quotation and financial documents:
- Quoted total sentence: "You're being quoted ₹12,28,399 for the vehicle."
- Base / ex-showroom price: "₹11,49,900 is the ex-showroom price."
- Charge breakdown:
  - "An additional ₹34,500 is listed for insurance."
  - "₹76,250 is listed for registration."
  - "₹24,000 is listed for warranty."
- Offers / deductions:
  - "₹70,000 in offers reduce the stated subtotal."
- Discrepancy (if any):
  - "One ₹6 discrepancy exists between the listed charges and the stated subtotal."
- Clarification items:
  "Before paying, clarify these items:"
  - [question]
  - [question]
  - [question]

RULES:
- Derived strictly from extracted evidence.
- Do not invent missing information.
- Use "not stated", "unclear", "requires verification" instead of guessing.
"""

from __future__ import annotations

import re
from typing import Any

from before_you_pay.models.analysis import (
    PlainLanguageExplanation,
    SmartCostReductionQuestion,
    ValidationCheck,
    ValidationStatus,
)
from before_you_pay.models.document import (
    ChargeNature,
    ComponentCategory,
    DocumentClassification,
    FinancialComponent,
    OptionalityStatus,
    StructuredFinancialDocument,
)


def _format_inr_number(val: float | int) -> str:
    """Format number using Indian numbering system (e.g. 12,28,399)."""
    is_neg = val < 0
    val = abs(val)
    int_part = int(val)
    frac_part = round(val - int_part, 2)
    s = str(int_part)
    if len(s) <= 3:
        res = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        res = ",".join(groups) + "," + last3
    if frac_part > 0:
        res += f".{int(round(frac_part * 100)):02d}"
    return f"-{res}" if is_neg else res


def _fmt_amt(amt: float, sym: str = "₹") -> str:
    """Format monetary amount cleanly with Indian notation if symbol is ₹."""
    if sym == "₹":
        num_str = _format_inr_number(amt)
        return f"{sym}{num_str}"
    if amt == int(amt):
        return f"{sym}{int(amt):,}"
    return f"{sym}{amt:,.2f}"


def _get_currency_symbol(curr: str | None) -> str:
    if not curr:
        return "₹"
    curr_upper = curr.upper().strip()
    if curr_upper in ("INR", "RS", "RS.", "RUPEES", "₹"):
        return "₹"
    if curr_upper in ("USD", "$"):
        return "$"
    if curr_upper in ("EUR", "€"):
        return "€"
    if curr_upper in ("GBP", "£"):
        return "£"
    return "₹"


class PlainLanguageExplanationService:
    """Service generating concise, evidence-grounded plain-language explanations."""

    CLARIFICATION_HEADING = "Before paying, clarify these items:"

    @classmethod
    def generate_explanation(
        cls,
        document: StructuredFinancialDocument,
        validation_checks: list[ValidationCheck] | None = None,
        smart_questions: list[SmartCostReductionQuestion] | None = None,
    ) -> PlainLanguageExplanation:
        """Construct PlainLanguageExplanation from extracted document components and validation results."""
        curr_sym = _get_currency_symbol(document.currency)
        validation_checks = validation_checks or []
        smart_questions = smart_questions or []

        # ── 1. Quoted Total Sentence ──
        total_val = None
        if document.total_amount and document.total_amount.normalized_value is not None:
            try:
                total_val = float(document.total_amount.normalized_value)
            except (ValueError, TypeError):
                total_val = None

        doc_meta = getattr(document, "document_metadata", None) or getattr(document, "metadata", None)
        has_vehicle_meta = doc_meta and getattr(doc_meta, "vehicle_model", None)

        is_vehicle = (
            getattr(document, "is_vehicle_document", False)
            or document.document_type in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN)
            or bool(has_vehicle_meta)
            or any(c.category in (ComponentCategory.EX_SHOWROOM_PRICE, ComponentCategory.ROAD_TAX) for c in (document.cost_breakdown or []))
        )

        if total_val is not None and total_val > 0:
            amt_str = _fmt_amt(total_val, curr_sym)
            if is_vehicle:
                quoted_amount_sentence = f"You're being quoted {amt_str} for the vehicle."
            else:
                quoted_amount_sentence = f"You're being quoted {amt_str}."
        else:
            quoted_amount_sentence = (
                "The final quoted amount for the vehicle is not stated."
                if is_vehicle
                else "The total quoted amount is not stated."
            )

        # ── 2. Base / Ex-Showroom Price Sentence ──
        base_comp = None
        for c in (document.cost_breakdown or []):
            if c.category in (ComponentCategory.EX_SHOWROOM_PRICE, ComponentCategory.BASE_PRICE):
                base_comp = c
                break
            if "ex-showroom" in (c.name or "").lower():
                base_comp = c
                break

        if base_comp and base_comp.amount and base_comp.amount.normalized_value is not None:
            try:
                b_amt = float(base_comp.amount.normalized_value)
                b_str = _fmt_amt(b_amt, curr_sym)
                label = (
                    "ex-showroom price"
                    if base_comp.category == ComponentCategory.EX_SHOWROOM_PRICE or "ex-showroom" in (base_comp.name or "").lower()
                    else "base price"
                )
                base_price_sentence = f"{b_str} is the {label}."
            except (ValueError, TypeError):
                base_price_sentence = "The ex-showroom / base price is unclear."
        elif document.subtotal and document.subtotal.normalized_value is not None and not document.cost_breakdown:
            try:
                sub_amt = float(document.subtotal.normalized_value)
                base_price_sentence = f"{_fmt_amt(sub_amt, curr_sym)} is the base subtotal."
            except (ValueError, TypeError):
                base_price_sentence = "The base price is unclear."
        else:
            base_price_sentence = (
                "The ex-showroom price is not stated."
                if is_vehicle
                else "The base price is not stated."
            )

        # ── 3. Component Breakdown Sentences ──
        charge_sentences: list[str] = []
        charges = [c for c in (document.cost_breakdown or []) if c.charge_nature == ChargeNature.CHARGE]

        # Insurance
        ins_comp = next((c for c in charges if c.category == ComponentCategory.INSURANCE or "insurance" in (c.name or "").lower()), None)
        if ins_comp and ins_comp.amount and ins_comp.amount.normalized_value is not None:
            try:
                ins_amt = float(ins_comp.amount.normalized_value)
                charge_sentences.append(f"An additional {_fmt_amt(ins_amt, curr_sym)} is listed for insurance.")
            except (ValueError, TypeError):
                charge_sentences.append("Insurance is listed but amount is unclear.")
        elif is_vehicle:
            charge_sentences.append("Insurance is not stated.")

        # Registration / RTO
        reg_comp = next((c for c in charges if c.category in (ComponentCategory.REGISTRATION, ComponentCategory.RC, ComponentCategory.ROAD_TAX) or "registration" in (c.name or "").lower() or "rto" in (c.name or "").lower()), None)
        if reg_comp and reg_comp.amount and reg_comp.amount.normalized_value is not None:
            try:
                reg_amt = float(reg_comp.amount.normalized_value)
                charge_sentences.append(f"{_fmt_amt(reg_amt, curr_sym)} is listed for registration.")
            except (ValueError, TypeError):
                charge_sentences.append("Registration is listed but amount is unclear.")
        elif is_vehicle:
            charge_sentences.append("Registration is not stated.")

        # Warranty / Extended Warranty
        war_comp = next((c for c in charges if c.category in (ComponentCategory.EXTENDED_WARRANTY, ComponentCategory.WARRANTY) or "warranty" in (c.name or "").lower()), None)
        if war_comp and war_comp.amount and war_comp.amount.normalized_value is not None:
            try:
                war_amt = float(war_comp.amount.normalized_value)
                w_label = "extended warranty" if war_comp.category == ComponentCategory.EXTENDED_WARRANTY or "extended" in (war_comp.name or "").lower() else "warranty"
                charge_sentences.append(f"{_fmt_amt(war_amt, curr_sym)} is listed for {w_label}.")
            except (ValueError, TypeError):
                charge_sentences.append("Warranty is listed but amount is unclear.")

        # Accessories
        accessories = [c for c in charges if c.category in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE) or "accessories" in (c.name or "").lower() or "accessory" in (c.name or "").lower()]
        if accessories:
            acc_tot = sum(cls._safe_float(c.amount.normalized_value) for c in accessories)
            if acc_tot > 0:
                charge_sentences.append(f"{_fmt_amt(acc_tot, curr_sym)} is listed for accessories.")

        # Dealer fees (handling, documentation, incidental)
        dealer_fees = [c for c in charges if c.category in (ComponentCategory.HANDLING_FEE, ComponentCategory.LOGISTICS_FEE, ComponentCategory.PROCESSING_FEE, ComponentCategory.DEALER_PACKAGE) or any(w in (c.name or "").lower() for w in ("handling", "logistics", "incidental", "depot"))]
        for fee in dealer_fees:
            f_amt = cls._safe_float(fee.amount.normalized_value) if fee.amount else 0.0
            if f_amt > 0:
                fee_name = fee.name.strip()
                charge_sentences.append(f"{_fmt_amt(f_amt, curr_sym)} is listed for {fee_name} (requires verification).")

        # ── 4. Offers & Deductions Sentence ──
        deductions = [c for c in (document.cost_breakdown or []) if c.charge_nature == ChargeNature.DEDUCTION or c.category in (ComponentCategory.OFFER, ComponentCategory.DISCOUNT)]
        offers_sentence = None
        if deductions:
            tot_ded = sum(cls._safe_float(c.amount.normalized_value) for c in deductions)
            if tot_ded > 0:
                has_offers = any(c.category == ComponentCategory.OFFER or "offer" in (c.name or "").lower() for c in deductions)
                term = "offers" if has_offers else "discounts"
                offers_sentence = f"{_fmt_amt(tot_ded, curr_sym)} in {term} reduce the stated subtotal."
        elif document.discount_amount and document.discount_amount.normalized_value is not None:
            disc_amt = cls._safe_float(document.discount_amount.normalized_value)
            if disc_amt > 0:
                offers_sentence = f"{_fmt_amt(disc_amt, curr_sym)} in discounts reduce the stated subtotal."

        # ── 5. Discrepancy Sentence ──
        discrepancy_sentence = None
        # Priority 1: Check QUOTATION_SUBTOTAL_CONSISTENCY
        sub_check = next((ck for ck in validation_checks if ck.check_code == "QUOTATION_SUBTOTAL_CONSISTENCY" and ck.status == ValidationStatus.FAIL), None)
        if sub_check and sub_check.absolute_delta is not None and sub_check.absolute_delta > 0.02:
            d_str = _fmt_amt(sub_check.absolute_delta, curr_sym)
            discrepancy_sentence = f"One {d_str} discrepancy exists between the listed charges and the stated subtotal."
        else:
            # Priority 2: Check QUOTATION_NET_TOTAL_CONSISTENCY
            net_check = next((ck for ck in validation_checks if ck.check_code == "QUOTATION_NET_TOTAL_CONSISTENCY" and ck.status == ValidationStatus.FAIL), None)
            if net_check and net_check.absolute_delta is not None and net_check.absolute_delta > 0.02:
                d_str = _fmt_amt(net_check.absolute_delta, curr_sym)
                discrepancy_sentence = f"A {d_str} discrepancy exists between the net total and the stated final price."
            else:
                # Priority 3: Check ARITHMETIC_LINE_ITEMS_SUM
                sum_check = next((ck for ck in validation_checks if ck.check_code in ("ARITHMETIC_LINE_ITEMS_SUM", "LINE_ITEMS_SUM_MATCH") and ck.status == ValidationStatus.FAIL), None)
                if sum_check and sum_check.absolute_delta is not None and sum_check.absolute_delta > 0.02:
                    d_str = _fmt_amt(sum_check.absolute_delta, curr_sym)
                    discrepancy_sentence = f"A {d_str} discrepancy exists between itemized line items and the stated total."

        # ── 6. Clarification Items ──
        clarification_items: list[str] = []

        # If discrepancy exists, prioritize it as first question
        if sub_check and sub_check.absolute_delta is not None and sub_check.absolute_delta > 0.02:
            d_str = _fmt_amt(sub_check.absolute_delta, curr_sym)
            clarification_items.append(f"Can the {d_str} discrepancy between the listed charges and the stated subtotal be corrected?")

        # Add top questions from smart_questions (deduplicating)
        for q in smart_questions:
            q_text = q.question.strip()
            if q_text not in clarification_items:
                clarification_items.append(q_text)
            if len(clarification_items) >= 4:
                break

        # Fallback clarification items if smart questions are empty
        if not clarification_items:
            if "Insurance is not stated." in charge_sentences:
                clarification_items.append("Confirm whether motor insurance is included in the quoted price or payable separately.")
            if "Registration is not stated." in charge_sentences:
                clarification_items.append("Confirm whether RTO registration fees and road tax are included in this quote.")
            if any("requires verification" in s for s in charge_sentences):
                clarification_items.append("Ask the dealer whether handling and incidental charges can be removed.")

        # ── 7. Build Full Text ──
        body_lines = [quoted_amount_sentence, base_price_sentence]
        body_lines.extend(charge_sentences)
        if offers_sentence:
            body_lines.append(offers_sentence)
        if discrepancy_sentence:
            body_lines.append(discrepancy_sentence)

        clarification_block = ""
        if clarification_items:
            clarification_block = f"\n\n{cls.CLARIFICATION_HEADING}\n" + "\n".join(f"- {item}" for item in clarification_items)

        full_text = "\n".join(body_lines) + clarification_block

        return PlainLanguageExplanation(
            quoted_amount_sentence=quoted_amount_sentence,
            base_price_sentence=base_price_sentence,
            charge_breakdown_sentences=charge_sentences,
            offers_sentence=offers_sentence,
            discrepancy_sentence=discrepancy_sentence,
            clarification_heading=cls.CLARIFICATION_HEADING,
            clarification_items=clarification_items,
            full_explanation=full_text,
        )

    @staticmethod
    def _safe_float(val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
