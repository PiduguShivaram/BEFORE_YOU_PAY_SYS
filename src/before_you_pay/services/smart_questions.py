"""Smart Cost-Reduction Questions Service (Phase 5).

Generates practical questions the buyer can ask the seller/dealer based ONLY
on evidence found in the document.

RULES:
- Goal is NOT to negotiate on the user's behalf.
- Goal is to help the user discover whether charges can be removed, reduced,
  substituted, or clarified.
- Every question includes:
  1. question: str
  2. reason: str
  3. related_charge: str
  4. amount_involved: float | None
  5. potential_impact: str
  6. evidence_source: str
  7. confidence: float
- Do NOT generate generic questions (e.g. "Can you give me a discount?").
- Every question must be connected to an actual document finding.
- Do NOT claim the user can legally choose another insurer unless authoritative
  evidence supports that statement for the relevant jurisdiction/transaction.
  Frame questions as inquiries to the seller.
- Rank questions by:
  - amount involved
  - uncertainty
  - potential impact
  - duplication risk
  - optionality uncertainty
  using transparent ordering based on explicit measurable criteria.
- Display title: "Questions to ask before paying"
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from before_you_pay.models.analysis import (
    SmartCostReductionQuestion,
    ValidationCheck,
    ValidationStatus,
)
from before_you_pay.models.document import (
    ComponentCategory,
    FinancialComponent,
    OptionalityStatus,
    StructuredFinancialDocument,
)
from before_you_pay.services.extra_cost_analysis import (
    ExtraCostAnalysisResult,
    ExtraCostFlag,
    ExtraCostFlagType,
)


class SmartCostReductionQuestionsService:
    """Generates evidence-backed discovery questions for buyers."""

    DISPLAY_TITLE = "Questions to ask before paying"

    @classmethod
    def generate_questions(
        cls,
        cost_breakdown: list[FinancialComponent] | None = None,
        extra_cost_analysis: ExtraCostAnalysisResult | dict[str, Any] | None = None,
        validation_checks: list[ValidationCheck] | None = None,
        reasoning_claims: list[Any] | None = None,
        document: StructuredFinancialDocument | None = None,
    ) -> list[SmartCostReductionQuestion]:
        """Generate, rank, and deduplicate smart questions from document evidence."""
        questions: list[SmartCostReductionQuestion] = []
        seen_question_keys: set[str] = set()

        if isinstance(cost_breakdown, StructuredFinancialDocument):
            document = cost_breakdown
            components = list(document.cost_breakdown or [])
        else:
            components = cost_breakdown or []
        checks = validation_checks or []

        # ── 1. Questions from Arithmetic Discrepancies ──
        arithmetic_questions = cls._generate_arithmetic_discrepancy_questions(checks, document=document)
        for q in arithmetic_questions:
            key = f"arithmetic:{q.related_charge}:{q.amount_involved}"
            if key not in seen_question_keys:
                seen_question_keys.add(key)
                questions.append(q)

        # ── 2. Questions from Extra Cost Flags ──
        flagged_list: list[ExtraCostFlag | dict[str, Any]] = []
        if extra_cost_analysis is not None:
            if isinstance(extra_cost_analysis, ExtraCostAnalysisResult):
                flagged_list = extra_cost_analysis.flagged_costs
            elif isinstance(extra_cost_analysis, dict):
                flagged_list = extra_cost_analysis.get("flagged_costs", [])

        for flag in flagged_list:
            q = cls._generate_question_from_flag(flag)
            if q:
                key = f"flag:{q.related_charge}:{q.amount_involved}"
                if key not in seen_question_keys:
                    seen_question_keys.add(key)
                    questions.append(q)

        # ── 3. Questions from Unclear Offers / Discounts ──
        offer_questions = cls._generate_offer_questions(components)
        for q in offer_questions:
            key = f"offer:{q.related_charge}:{q.amount_involved}"
            if key not in seen_question_keys:
                seen_question_keys.add(key)
                questions.append(q)

        # ── 4. Questions from Duplicate Charges in Components ──
        dup_questions = cls._generate_duplicate_pair_questions(components)
        for q in dup_questions:
            key = f"duplicate:{q.related_charge}"
            if key not in seen_question_keys:
                seen_question_keys.add(key)
                questions.append(q)

        # ── 5. Rank questions by measurable criteria ──
        ranked_questions = cls._rank_questions(questions)
        return ranked_questions

    @classmethod
    def _generate_question_from_flag(
        cls,
        flag: ExtraCostFlag | dict[str, Any],
    ) -> SmartCostReductionQuestion | None:
        """Create a targeted, non-negotiating inquiry from an extra cost flag."""
        # Normalize dict or dataclass access
        if isinstance(flag, dict):
            what = flag.get("what", "")
            amt = float(flag.get("amount", 0.0) or 0.0)
            category = flag.get("category", "")
            flag_type = flag.get("flag_type", "")
            evidence = flag.get("evidence")
            why_flagged = flag.get("why_flagged", "")
            opt_status = flag.get("optionality_status")
            potential_saving = flag.get("potential_saving")
        else:
            what = flag.what
            amt = float(flag.amount or 0.0)
            category = flag.category
            flag_type = flag.flag_type.value if hasattr(flag.flag_type, "value") else str(flag.flag_type)
            evidence = flag.evidence
            why_flagged = flag.why_flagged
            opt_status = flag.optionality_status
            potential_saving = flag.potential_saving

        cat_upper = category.upper() if category else ""
        evidence_str = evidence or f"Quotation line: '{what} — ₹{amt:,.0f}'"

        # 1. Extended Warranty
        if cat_upper in ("EXTENDED_WARRANTY", "WARRANTY"):
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"Is the ₹{amt:,.0f} extended warranty optional?",
                reason="The quotation lists warranty as a separate charge.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Up to ₹{amt:,.0f} if the charge is optional and removed.",
                evidence_source=evidence_str,
                confidence=0.95,
                category=cat_upper,
            )

        # 2. Accessories / Accessory Package
        if cat_upper in ("ACCESSORY", "ACCESSORY_PACKAGE") or "accessory" in what.lower():
            if amt > 0:
                question = f"Which accessories are included in the ₹{amt:,.0f} package, and can I remove individual accessories I don't need?"
                potential_impact = f"Up to ₹{amt:,.0f} if the full package is declined, or savings on individual removed accessories."
            else:
                question = f"Which accessories are included in '{what}', and can individual items be removed?"
                potential_impact = "Potential savings if unwanted individual accessories are removed."
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=question,
                reason="The quotation lists an accessory package separately from the base vehicle price.",
                related_charge=what,
                amount_involved=amt if amt > 0 else None,
                potential_impact=potential_impact,
                evidence_source=evidence_str,
                confidence=0.92,
                category=cat_upper or "ACCESSORY",
            )

        # 3. Insurance (STRICT: Never claim legal right without authoritative jurisdiction evidence)
        if cat_upper == "INSURANCE" or "insurance" in what.lower():
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question="Is this insurance package mandatory from the dealer, or can I choose another insurer?",
                reason="The quotation includes dealer-arranged insurance as a separate line item.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=(
                    f"Potential savings if independent third-party insurance provides a lower premium for equivalent coverage."
                    if amt > 0
                    else "Potential savings if third-party insurance is permitted."
                ),
                evidence_source=evidence_str,
                confidence=0.90,
                category="INSURANCE",
            )

        # 4. Handling Fee / Logistics Fee / Processing Fee / Documentation Fee
        if cat_upper in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE") or any(
            t in what.lower() for t in ("handling", "logistics", "processing", "documentation fee")
        ):
            clean_name = what.strip()
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"What does the ₹{amt:,.0f} {clean_name.lower()} cover, and is it required for this purchase?",
                reason=f"The quotation includes a separate {clean_name.lower()} added by the dealer.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Up to ₹{amt:,.0f} if the fee is optional, negotiable, or waived.",
                evidence_source=evidence_str,
                confidence=0.95,
                category=cat_upper or "HANDLING_FEE",
            )

        # 5. Dealer Package / Service Package
        if cat_upper in ("DEALER_PACKAGE", "SERVICE_PACKAGE") or any(
            t in what.lower() for t in ("dealer package", "service package", "basic kit", "essential kit")
        ):
            clean_name = what.strip()
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"What services are included in the ₹{amt:,.0f} {clean_name.lower()}, and can I purchase the vehicle without this package?",
                reason=f"The quotation bundles services under '{what}' separately from the base vehicle price.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Up to ₹{amt:,.0f} if the package is optional and declined.",
                evidence_source=evidence_str,
                confidence=0.92,
                category=cat_upper or "DEALER_PACKAGE",
            )

        # 6. FASTag with Markup
        if cat_upper == "FASTAG" or "fastag" in what.lower():
            if amt > 500:
                markup = amt - 500
                return SmartCostReductionQuestion(
                    question_id=uuid4(),
                    question=f"What is the breakdown of the ₹{amt:,.0f} FASTag charge, including the security deposit, threshold amount, and issuance fee?",
                    reason="The quotation lists a FASTag fee higher than the standard issuance fee (typically ₹200–₹500 including deposit).",
                    related_charge=what,
                    amount_involved=amt,
                    potential_impact=f"Up to ₹{markup:,.0f} potential reduction if excess dealer markup is removed.",
                    evidence_source=evidence_str,
                    confidence=0.90,
                    category="FASTAG",
                )

        # 7. Possible Duplicate
        if flag_type == ExtraCostFlagType.POSSIBLE_DUPLICATE.value or "duplicate" in why_flagged.lower():
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"Can you explain why '{what}' is listed separately, and whether it covers items included in another charge?",
                reason=why_flagged or f"The quotation includes '{what}' which may duplicate another listed service or charge.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Potential reduction of up to ₹{amt:,.0f} if one charge is redundant.",
                evidence_source=evidence_str,
                confidence=0.88,
                category="POSSIBLE_DUPLICATE",
            )

        # 8. Unclear Charge / Other Fee
        if flag_type == ExtraCostFlagType.UNCLEAR_CHARGE.value or cat_upper in ("UNKNOWN", "OTHER_FEE"):
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"What specific service or administrative item does the ₹{amt:,.0f} '{what}' charge represent, and is it required?",
                reason=f"The quotation lists '{what}' without a detailed description of what it covers.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Up to ₹{amt:,.0f} if the charge is discretionary or can be removed.",
                evidence_source=evidence_str,
                confidence=0.82,
                category=cat_upper or "OTHER_FEE",
            )

        # 9. Potentially Optional Catch-all
        if potential_saving and potential_saving > 0:
            return SmartCostReductionQuestion(
                question_id=uuid4(),
                question=f"Is the ₹{amt:,.0f} '{what}' charge optional, and can it be removed from the quote?",
                reason=why_flagged or f"The quotation lists '{what}' separately from the base vehicle price.",
                related_charge=what,
                amount_involved=amt,
                potential_impact=f"Up to ₹{potential_saving:,.0f} if the charge is optional and declined.",
                evidence_source=evidence_str,
                confidence=0.85,
                category=cat_upper,
            )

        return None

    @classmethod
    def _generate_arithmetic_discrepancy_questions(
        cls,
        checks: list[ValidationCheck],
        document: StructuredFinancialDocument | None = None,
    ) -> list[SmartCostReductionQuestion]:
        """Generate questions for failed arithmetic or subtotal reconciliation checks."""
        questions: list[SmartCostReductionQuestion] = []
        for c in checks:
            if c.status == ValidationStatus.FAIL:
                if c.check_code == "LINE_ITEM_EXTENSION_MATCH":
                    matched_item = None
                    if document and document.line_items:
                        for item in document.line_items:
                            if item.item_id in c.input_field_ids or (item.description and item.description.normalized_value in c.message):
                                matched_item = item
                                break
                    if matched_item:
                        item_name = matched_item.description.normalized_value
                        amt_val = float(matched_item.total_price.normalized_value)
                        amt_str = f"₹{int(amt_val):,}" if amt_val == int(amt_val) else f"₹{amt_val:,.2f}"
                        mrp_val = float(matched_item.mrp.normalized_value) if matched_item.mrp else None
                        rate_val = float(matched_item.unit_price.normalized_value) if matched_item.unit_price else None
                        disc_val = float(matched_item.discount.normalized_value) if matched_item.discount else None

                        if mrp_val is not None and rate_val is not None and disc_val is not None:
                            mrp_str = f"₹{int(mrp_val):,}" if mrp_val == int(mrp_val) else f"₹{mrp_val:,.2f}"
                            rate_str = f"₹{int(rate_val):,}" if rate_val == int(rate_val) else f"₹{rate_val:,.2f}"
                            disc_str = f"₹{int(disc_val):,}" if disc_val == int(disc_val) else f"₹{disc_val:,.2f}"
                            q_text = f"Could you please clarify how the {amt_str} amount for {item_name} is calculated from the displayed {mrp_str} MRP, {rate_str} rate/item, and {disc_str} discount?"
                        else:
                            q_text = f"Could you please clarify how the {amt_str} amount for {item_name} is calculated from the displayed rate and discount?"

                        questions.append(
                            SmartCostReductionQuestion(
                                question_id=uuid4(),
                                question=q_text,
                                reason=f"The displayed line-item numbers for {item_name} do not mathematically explain {amt_str}.",
                                related_charge=item_name,
                                amount_involved=amt_val,
                                potential_impact=f"Verification of {item_name} pricing calculation ({amt_str}).",
                                evidence_source=f"Validation check: {c.check_code} ({c.message})",
                                confidence=0.98,
                                category="ARITHMETIC_DISCREPANCY",
                            )
                        )
                        continue

                delta = c.absolute_delta
                # Try to extract delta from message if not set
                if delta is None or delta <= 0:
                    delta_match = re.search(r"difference(?:\s+of)?\s+[₹$]?([\d,]+(?:\.\d+)?)", c.message, re.IGNORECASE)
                    if delta_match:
                        try:
                            delta = float(delta_match.group(1).replace(",", ""))
                        except ValueError:
                            delta = None

                if delta and delta > 0:
                    diff_str = f"{int(delta):,}" if delta == int(delta) else f"{delta:,.2f}"
                    is_subtotal = "subtotal" in c.check_code.lower() or "subtotal" in c.message.lower()
                    term = "subtotal" if is_subtotal else "total"

                    questions.append(
                        SmartCostReductionQuestion(
                            question_id=uuid4(),
                            question=f"Could you please explain the ₹{diff_str} difference between the listed charges and the stated {term}?",
                            reason=f"The mathematical calculation of listed charges differs from the stated {term} on the quotation.",
                            related_charge=f"Stated {term.capitalize()} vs Calculated Sum",
                            amount_involved=delta,
                            potential_impact=f"Correction of ₹{diff_str} arithmetic difference in the final payable amount.",
                            evidence_source=f"Validation check: {c.check_code} ({c.message})",
                            confidence=0.98,
                            category="ARITHMETIC_DISCREPANCY",
                        )
                    )
        return questions

    @classmethod
    def _generate_offer_questions(
        cls,
        components: list[FinancialComponent],
    ) -> list[SmartCostReductionQuestion]:
        """Generate clarification questions for offers and discounts whose inclusion is ambiguous."""
        questions: list[SmartCostReductionQuestion] = []
        for comp in components:
            cat = comp.category
            cat_upper = cat.value.upper() if hasattr(cat, "value") else str(cat).upper()
            if cat_upper in ("OFFER", "DISCOUNT"):
                amt = cls._get_amount(comp)
                if amt > 0:
                    evidence_str = comp.evidence or f"Quotation line: '{comp.name} — ₹{amt:,.0f}'"
                    questions.append(
                        SmartCostReductionQuestion(
                            question_id=uuid4(),
                            question=f"Is the ₹{amt:,.0f} offer already included in the final quoted price, or will it be applied separately?",
                            reason=f"The quotation lists '{comp.name}' without clearly indicating whether it has already been deducted from the final payable amount.",
                            related_charge=comp.name,
                            amount_involved=amt,
                            potential_impact=f"Clarity on net payable amount and confirmation of ₹{amt:,.0f} deduction.",
                            evidence_source=evidence_str,
                            confidence=0.85,
                            category=cat_upper,
                        )
                    )
        return questions

    @classmethod
    def _generate_duplicate_pair_questions(
        cls,
        components: list[FinancialComponent],
    ) -> list[SmartCostReductionQuestion]:
        """Generate inquiry questions when two distinct components appear to duplicate each other."""
        questions: list[SmartCostReductionQuestion] = []
        n = len(components)
        paired_indices: set[int] = set()

        for i in range(n):
            if i in paired_indices:
                continue
            c1 = components[i]
            c1_cat = c1.category.value if hasattr(c1.category, "value") else str(c1.category)
            if c1_cat in ("BASE_PRICE", "EX_SHOWROOM_PRICE", "TOTAL", "SUBTOTAL", "AMOUNT_PAID", "BALANCE_DUE"):
                continue

            for j in range(i + 1, n):
                if j in paired_indices:
                    continue
                c2 = components[j]
                c2_cat = c2.category.value if hasattr(c2.category, "value") else str(c2.category)

                # Check if same non-base category or matching core names
                same_cat = c1_cat == c2_cat and c1_cat not in ("OTHER_FEE", "UNKNOWN")
                names_similar = (
                    c1.normalized_name
                    and c2.normalized_name
                    and c1.normalized_name.lower() == c2.normalized_name.lower()
                    and c1.name.lower() != c2.name.lower()
                )

                if same_cat or names_similar:
                    paired_indices.add(j)
                    amt1 = cls._get_amount(c1)
                    amt2 = cls._get_amount(c2)
                    smaller_amt = min(amt1, amt2) if (amt1 > 0 and amt2 > 0) else max(amt1, amt2)
                    questions.append(
                        SmartCostReductionQuestion(
                            question_id=uuid4(),
                            question=f"Can you explain why both {c1.name} and {c2.name} are being charged separately?",
                            reason=f"The document lists two separate charges that appear to cover similar items ('{c1.name}' and '{c2.name}').",
                            related_charge=f"{c1.name} / {c2.name}",
                            amount_involved=smaller_amt if smaller_amt > 0 else None,
                            potential_impact=(
                                f"Potential reduction of up to ₹{smaller_amt:,.0f} if one charge is redundant or duplicated."
                                if smaller_amt > 0
                                else "Potential reduction if one charge is redundant."
                            ),
                            evidence_source=f"Quotation lines: '{c1.name}' (₹{amt1:,.0f}) and '{c2.name}' (₹{amt2:,.0f})",
                            confidence=0.88,
                            category="POSSIBLE_DUPLICATE",
                        )
                    )
                    break
        return questions

    @classmethod
    def _rank_questions(
        cls,
        questions: list[SmartCostReductionQuestion],
    ) -> list[SmartCostReductionQuestion]:
        """Rank questions using transparent, measurable criteria.

        Criteria:
        1. Amount involved (higher amount -> higher factor)
        2. Potential impact (removable saving / arithmetic error -> higher factor)
        3. Optionality uncertainty (potentially optional / unclear -> higher factor)
        4. Duplication risk (duplicate charges -> high factor)
        5. General uncertainty (unclear charges / unverified offers -> high factor)

        Formula:
          score = (amount * 0.35) + (impact * 0.25) + (opt_uncertainty * 0.15)
                + (duplication * 0.15) + (general_uncertainty * 0.10)
        """
        scored_questions: list[SmartCostReductionQuestion] = []

        for q in questions:
            amt = q.amount_involved or 0.0

            # 1. Amount factor: normalized up to ₹1,00,000 (1.0)
            amount_factor = round(min(1.0, amt / 100000.0), 4)

            # 2. Potential impact factor
            impact_text = q.potential_impact.lower()
            if "correction" in impact_text or "arithmetic" in impact_text:
                impact_factor = 0.95
            elif "up to ₹" in q.potential_impact:
                # Direct monetary removal saving
                impact_factor = round(min(1.0, max(0.5, amt / 50000.0)), 4)
            elif "potential reduction" in impact_text or "savings" in impact_text:
                impact_factor = 0.80
            else:
                impact_factor = 0.50

            # 3. Optionality uncertainty factor
            cat = (q.category or "").upper()
            if cat in ("EXTENDED_WARRANTY", "ACCESSORY", "ACCESSORY_PACKAGE", "DEALER_PACKAGE"):
                opt_factor = 0.90
            elif cat == "ARITHMETIC_DISCREPANCY":
                opt_factor = 1.00
            elif cat in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE"):
                opt_factor = 0.85
            elif cat == "INSURANCE":
                opt_factor = 0.75
            else:
                opt_factor = 0.50

            # 4. Duplication risk factor
            duplication_factor = 1.00 if cat == "POSSIBLE_DUPLICATE" else 0.00

            # 5. General uncertainty factor
            if cat in ("OTHER_FEE", "UNKNOWN", "OFFER", "DISCOUNT"):
                uncertainty_factor = 0.90
            elif cat == "FASTAG":
                uncertainty_factor = 0.80
            elif cat == "ARITHMETIC_DISCREPANCY":
                uncertainty_factor = 0.90
            else:
                uncertainty_factor = 0.40

            # Composite transparent score
            priority_score = round(
                (amount_factor * 0.35)
                + (impact_factor * 0.25)
                + (opt_factor * 0.15)
                + (duplication_factor * 0.15)
                + (uncertainty_factor * 0.10),
                4,
            )

            ranking_factors = {
                "amount_factor": amount_factor,
                "impact_factor": impact_factor,
                "optionality_uncertainty_factor": opt_factor,
                "duplication_risk_factor": duplication_factor,
                "general_uncertainty_factor": uncertainty_factor,
            }

            scored_q = SmartCostReductionQuestion(
                question_id=q.question_id,
                question=q.question,
                reason=q.reason,
                related_charge=q.related_charge,
                amount_involved=q.amount_involved,
                potential_impact=q.potential_impact,
                evidence_source=q.evidence_source,
                confidence=q.confidence,
                category=q.category,
                priority_score=priority_score,
                ranking_factors=ranking_factors,
            )
            scored_questions.append(scored_q)

        # Sort descending by priority_score, then by amount_involved
        scored_questions.sort(
            key=lambda x: (x.priority_score, x.amount_involved or 0.0),
            reverse=True,
        )
        return scored_questions

    @staticmethod
    def _get_amount(comp: FinancialComponent) -> float:
        """Safely extract float amount from a FinancialComponent."""
        try:
            if hasattr(comp.amount, "normalized_value"):
                return float(comp.amount.normalized_value)
            return float(comp.amount)
        except (TypeError, ValueError):
            return 0.0
