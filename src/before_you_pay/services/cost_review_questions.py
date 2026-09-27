"""Phase 3: Cost Review Questions Service.

Generates evidence-grounded questions to help the buyer review or potentially
reduce quoted costs.

RULES:
- Work ONLY on generating evidence-based questions.
- For each relevant charge identify whether it is:
  * potentially optional
  * potentially negotiable
  * unexplained
  * duplicated/overlapping
  * alternative available
  * inconsistent
  * requires verification
- Generate 1–3 specific questions using actual document evidence.
- Questions must reference actual extracted values when available.
- Do NOT generate generic questions (e.g. "Can you give me a discount?").
- Do NOT promise savings.
- Use "Potential amount to review" instead of "You can save ₹X".
- Never say:
  "You don't need this"
  "You can definitely remove this"
  "You will save ₹X"
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
from before_you_pay.models.cost_review import (
    CostReviewClassification,
    CostReviewQuestion,
)
from before_you_pay.models.document import (
    FinancialComponent,
    StructuredFinancialDocument,
)
from before_you_pay.services.extra_cost_analysis import (
    ExtraCostAnalysisResult,
    ExtraCostFlag,
    ExtraCostFlagType,
)


class CostReviewQuestionsService:
    """Generates evidence-backed cost review questions for buyers."""

    DISPLAY_TITLE = "Cost Review Questions"

    @classmethod
    def generate_questions(
        cls,
        cost_breakdown: list[FinancialComponent] | None = None,
        extra_cost_analysis: ExtraCostAnalysisResult | dict[str, Any] | None = None,
        validation_checks: list[ValidationCheck] | None = None,
        document: StructuredFinancialDocument | None = None,
    ) -> list[CostReviewQuestion]:
        """Generate 1-3 specific evidence-based questions per relevant charge."""
        questions: list[CostReviewQuestion] = []
        seen_question_keys: set[str] = set()

        if isinstance(cost_breakdown, StructuredFinancialDocument):
            document = cost_breakdown
            components = list(document.cost_breakdown or [])
        else:
            components = list(cost_breakdown or [])
        checks = list(validation_checks or [])

        # ── 1. Inconsistent Charges (Arithmetic Discrepancies) ──
        discrepancy_questions = cls._generate_discrepancy_questions(checks, components, document=document)
        for q in discrepancy_questions:
            key = f"inconsistent:{q.question}"
            if key not in seen_question_keys:
                seen_question_keys.add(key)
                questions.append(q)

        # ── 2. Duplicated / Overlapping Charges ──
        duplicate_questions = cls._generate_duplicate_pair_questions(components)
        for q in duplicate_questions:
            key = f"duplicated:{q.question}"
            if key not in seen_question_keys:
                seen_question_keys.add(key)
                questions.append(q)

        # ── 3. Questions from Components ──
        for comp in components:
            comp_questions = cls._generate_questions_for_component(comp)
            for q in comp_questions:
                key = f"comp:{q.classification.value}:{q.question}"
                if key not in seen_question_keys:
                    seen_question_keys.add(key)
                    questions.append(q)

        # ── 4. Questions from Extra Cost Flags ──
        flagged_list: list[ExtraCostFlag | dict[str, Any]] = []
        if extra_cost_analysis is not None:
            if isinstance(extra_cost_analysis, ExtraCostAnalysisResult):
                flagged_list = extra_cost_analysis.flagged_costs
            elif isinstance(extra_cost_analysis, dict):
                flagged_list = extra_cost_analysis.get("flagged_costs", [])

        for flag in flagged_list:
            flag_questions = cls._generate_questions_from_flag(flag)
            for q in flag_questions:
                key = f"flag:{q.classification.value}:{q.question}"
                if key not in seen_question_keys:
                    seen_question_keys.add(key)
                    questions.append(q)

        # ── 5. Rank questions transparently by amount and priority ──
        ranked_questions = cls._rank_questions(questions)
        return ranked_questions

    @classmethod
    def generate_smart_questions(
        cls,
        cost_breakdown: list[FinancialComponent] | None = None,
        extra_cost_analysis: ExtraCostAnalysisResult | dict[str, Any] | None = None,
        validation_checks: list[ValidationCheck] | None = None,
        document: StructuredFinancialDocument | None = None,
    ) -> list[SmartCostReductionQuestion]:
        """Generate questions and convert them to standard SmartCostReductionQuestion."""
        questions = cls.generate_questions(
            cost_breakdown=cost_breakdown,
            extra_cost_analysis=extra_cost_analysis,
            validation_checks=validation_checks,
            document=document,
        )
        return [q.to_smart_question() for q in questions]

    @classmethod
    def _generate_discrepancy_questions(
        cls,
        checks: list[ValidationCheck],
        components: list[FinancialComponent],
        document: StructuredFinancialDocument | None = None,
    ) -> list[CostReviewQuestion]:
        """Generate 1-3 questions for arithmetic discrepancies between listed charges and stated totals."""
        questions: list[CostReviewQuestion] = []

        # Find components sum and stated subtotal if available
        subtotal_comp = next(
            (c for c in components if (c.category.value if hasattr(c.category, "value") else str(c.category)).upper() in ("SUBTOTAL", "BASE_SUBTOTAL")),
            None,
        )
        listed_charges_sum = sum(
            cls._get_amount(c)
            for c in components
            if (c.category.value if hasattr(c.category, "value") else str(c.category)).upper()
            not in ("TOTAL", "SUBTOTAL", "BALANCE_DUE", "AMOUNT_PAID", "DISCOUNT", "OFFER")
        )

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
                            CostReviewQuestion(
                                question_id=uuid4(),
                                classification=CostReviewClassification.INCONSISTENT,
                                question=q_text,
                                reason=f"The displayed line-item numbers for {item_name} do not mathematically explain {amt_str}.",
                                related_charge=item_name,
                                amount_involved=amt_val,
                                potential_amount_to_review=amt_val,
                                potential_impact=f"Potential amount to review: {amt_str} verification required.",
                                evidence_source=f"Validation check: {c.check_code} ({c.message})",
                                confidence=0.98,
                                requires_verification=True,
                                category="INCONSISTENT",
                            )
                        )
                        continue
                delta = c.absolute_delta
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

                    # 1. Primary question (exact prompt example if listed components and subtotal are available)
                    if subtotal_comp and cls._get_amount(subtotal_comp) > 0 and listed_charges_sum > 0:
                        stated_amt = cls._get_amount(subtotal_comp)
                        listed_str = f"{int(listed_charges_sum):,}" if listed_charges_sum == int(listed_charges_sum) else f"{listed_charges_sum:,.2f}"
                        stated_str = f"{int(stated_amt):,}" if stated_amt == int(stated_amt) else f"{stated_amt:,.2f}"
                        q1 = f"The listed components total ₹{listed_str}, but the stated {term} is ₹{stated_str}. Which amount is correct?"
                    else:
                        q1 = f"Could you please explain the ₹{diff_str} difference between the listed charges and the stated {term}?"

                    questions.append(
                        CostReviewQuestion(
                            question_id=uuid4(),
                            classification=CostReviewClassification.INCONSISTENT,
                            question=q1,
                            reason=f"The mathematical calculation of listed charges differs from the stated {term} on the quotation.",
                            related_charge=f"Stated {term.capitalize()} vs Calculated Sum",
                            amount_involved=delta,
                            potential_amount_to_review=delta,
                            potential_impact=f"Potential amount to review: ₹{diff_str} arithmetic discrepancy in the stated {term}.",
                            evidence_source=f"Validation check: {c.check_code} ({c.message})",
                            confidence=0.98,
                            requires_verification=True,
                            category="INCONSISTENT",
                        )
                    )

                    # 2. Secondary follow-up question
                    q2 = f"Does the stated {term} include or omit any line items that explain the ₹{diff_str} difference?"
                    questions.append(
                        CostReviewQuestion(
                            question_id=uuid4(),
                            classification=CostReviewClassification.INCONSISTENT,
                            question=q2,
                            reason=f"Clarification needed on whether hidden fees or unlisted deductions account for the ₹{diff_str} variance.",
                            related_charge=f"Stated {term.capitalize()} vs Calculated Sum",
                            amount_involved=delta,
                            potential_amount_to_review=delta,
                            potential_impact=f"Potential amount to review: ₹{diff_str} variance requiring reconciliation.",
                            evidence_source=f"Validation check: {c.check_code}",
                            confidence=0.95,
                            requires_verification=True,
                            category="INCONSISTENT",
                        )
                    )
        return questions

    @classmethod
    def _generate_duplicate_pair_questions(
        cls,
        components: list[FinancialComponent],
    ) -> list[CostReviewQuestion]:
        """Generate 1-3 questions when charges appear duplicated or overlapping."""
        questions: list[CostReviewQuestion] = []
        n = len(components)
        paired_indices: set[int] = set()

        for i in range(n):
            if i in paired_indices:
                continue
            c1 = components[i]
            c1_cat = (c1.category.value if hasattr(c1.category, "value") else str(c1.category)).upper()
            if c1_cat in ("BASE_PRICE", "EX_SHOWROOM_PRICE", "TOTAL", "SUBTOTAL", "AMOUNT_PAID", "BALANCE_DUE"):
                continue

            for j in range(i + 1, n):
                if j in paired_indices:
                    continue
                c2 = components[j]
                c2_cat = (c2.category.value if hasattr(c2.category, "value") else str(c2.category)).upper()

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
                    amt_str = f"₹{smaller_amt:,.0f}" if smaller_amt > 0 else "the charge"

                    # 1. Primary question
                    q1 = f"Can you explain why both {c1.name} and {c2.name} are being charged separately?"
                    questions.append(
                        CostReviewQuestion(
                            question_id=uuid4(),
                            classification=CostReviewClassification.DUPLICATED_OVERLAPPING,
                            question=q1,
                            reason=f"The document lists two separate charges that appear to cover similar items ('{c1.name}' and '{c2.name}').",
                            related_charge=f"{c1.name} / {c2.name}",
                            amount_involved=smaller_amt if smaller_amt > 0 else None,
                            potential_amount_to_review=smaller_amt if smaller_amt > 0 else None,
                            potential_impact=(
                                f"Potential amount to review: up to {amt_str} if one charge duplicates another."
                            ),
                            evidence_source=f"Quotation lines: '{c1.name}' (₹{amt1:,.0f}) and '{c2.name}' (₹{amt2:,.0f})",
                            confidence=0.88,
                            requires_verification=True,
                            category="DUPLICATED_OVERLAPPING",
                        )
                    )

                    # 2. Secondary question
                    q2 = f"Does '{c1.name}' cover services or items already included in '{c2.name}'?"
                    questions.append(
                        CostReviewQuestion(
                            question_id=uuid4(),
                            classification=CostReviewClassification.DUPLICATED_OVERLAPPING,
                            question=q2,
                            reason=f"Verification needed to determine whether '{c1.name}' and '{c2.name}' provide distinct deliverables.",
                            related_charge=f"{c1.name} / {c2.name}",
                            amount_involved=smaller_amt if smaller_amt > 0 else None,
                            potential_amount_to_review=smaller_amt if smaller_amt > 0 else None,
                            potential_impact=(
                                f"Potential amount to review: up to {amt_str} upon confirming overlap."
                            ),
                            evidence_source=f"Quotation lines: '{c1.name}' and '{c2.name}'",
                            confidence=0.85,
                            requires_verification=True,
                            category="DUPLICATED_OVERLAPPING",
                        )
                    )
                    break
        return questions

    @classmethod
    def _generate_questions_for_component(
        cls,
        comp: FinancialComponent,
    ) -> list[CostReviewQuestion]:
        """Generate 1-3 targeted questions for an individual financial component."""
        questions: list[CostReviewQuestion] = []
        cat_str = (comp.category.value if hasattr(comp.category, "value") else str(comp.category)).upper()
        amt = cls._get_amount(comp)
        name = comp.name.strip()
        name_lower = name.lower()
        amt_str = f"₹{amt:,.0f}" if amt > 0 else ""
        evidence_str = comp.evidence or f"Quotation line: '{name} — ₹{amt:,.0f}'"

        # ── 1. Insurance (Alternative Available) ──
        if cat_str == "INSURANCE" or "insurance" in name_lower:
            # Question 1: Exact prompt example
            q1 = "Can I choose my own insurer or insurance policy?"
            # Question 2: Specific amount inquiry
            q2 = (
                f"Is this {amt_str} insurance package mandatory from the dealer, or can I obtain coverage independently?"
                if amt > 0
                else "Is this insurance package mandatory from the dealer, or can I choose another insurer?"
            )
            # Question 3: Add-on customization inquiry
            q3 = "Does this quote include optional add-ons (such as zero depreciation or engine protect) that can be adjusted?"

            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q1,
                    reason="The quotation includes dealer-arranged insurance as a separate line item.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: {amt_str} if independent third-party insurance provides equivalent coverage at lower premium."
                        if amt > 0
                        else "Potential amount to review if independent coverage is permitted."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.92,
                    requires_verification=True,
                    category="INSURANCE",
                )
            )
            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q2,
                    reason="Dealer-provided insurance quotes may bundle premium rates higher than direct insurer market rates.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: {amt_str} upon comparing competitive market quotes."
                        if amt > 0
                        else "Potential amount to review upon market comparison."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.90,
                    requires_verification=True,
                    category="INSURANCE",
                )
            )
            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q3,
                    reason="Insurance line items often combine mandatory third-party liability with discretionary add-on riders.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact="Potential amount to review if discretionary insurance riders are customized or omitted.",
                    evidence_source=evidence_str,
                    confidence=0.88,
                    requires_verification=True,
                    category="INSURANCE",
                )
            )
            return questions

        # ── 2. Extended Warranty (Potentially Optional) ──
        if cat_str in ("EXTENDED_WARRANTY", "WARRANTY") or "warranty" in name_lower:
            # Question 1: Exact prompt example referencing actual extracted value
            q1 = (
                f"Is the {amt_str} extended warranty package optional?"
                if amt > 0
                else "Is the extended warranty package optional?"
            )
            # Question 2: Vehicle purchase independence
            q2 = (
                f"Can this vehicle be purchased without the {amt_str} extended warranty?"
                if amt > 0
                else "Can this vehicle be purchased without the extended warranty?"
            )
            # Question 3: Coverage comparison with factory warranty
            q3 = "What specific coverage does the manufacturer standard warranty already provide compared to this extended warranty?"

            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason="The quotation lists warranty as a separate charge from the base vehicle price.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the extended warranty package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if the warranty is optional."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.95,
                    requires_verification=True,
                    category="EXTENDED_WARRANTY",
                )
            )
            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q2,
                    reason="Extended warranties are elective commercial agreements beyond statutory factory guarantees.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if opting for standard factory warranty only."
                        if amt > 0
                        else "Potential amount to review if opting for factory warranty only."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.92,
                    requires_verification=True,
                    category="EXTENDED_WARRANTY",
                )
            )
            return questions

        # ── 3. Accessories / Accessory Package (Potentially Optional) ──
        if cat_str in ("ACCESSORY", "ACCESSORY_PACKAGE") or "accessor" in name_lower:
            # Question 1: Exact prompt example
            q1 = "Are these accessories required for delivery?"
            # Question 2: Breakdown and individual item removal referencing actual extracted value
            q2 = (
                f"Which accessories are included in the {amt_str} package, and can I remove individual accessories I don't need?"
                if amt > 0
                else f"Which accessories are included in '{name}', and can individual items be removed?"
            )
            # Question 3: Selective individual purchase
            q3 = "Can I purchase only specific individual accessories rather than the full bundled kit?"

            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason="The quotation lists accessories separately from the base vehicle price.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if accessory package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if accessories are optional."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.93,
                    requires_verification=True,
                    category="ACCESSORY",
                )
            )
            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q2,
                    reason="Dealers frequently bundle multiple cosmetic or utility accessories into a single package line item.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} for unwanted individual items within the package."
                        if amt > 0
                        else "Potential amount to review for individual items within the package."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.91,
                    requires_verification=True,
                    category="ACCESSORY",
                )
            )
            return questions

        # ── 4. Dealer Handling Charge / Logistics Fee (Potentially Negotiable) ──
        if cat_str in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE") or any(
            t in name_lower for t in ("handling", "logistics", "depot", "incidental", "documentation fee", "facilitation")
        ):
            # Question 1: Exact prompt example referencing actual extracted value
            q1 = (
                f"What service does this {amt_str} charge cover, and is it mandatory?"
                if amt > 0
                else f"What service does the '{name}' charge cover, and is it mandatory?"
            )
            # Question 2: Negotiability under consumer guidelines
            q2 = (
                f"Is the {amt_str} {name.lower()} negotiable or waivable under consumer transport guidelines?"
                if amt > 0
                else f"Is the {name.lower()} negotiable or waivable under consumer transport guidelines?"
            )
            # Question 3: Ex-showroom pricing overlap
            q3 = f"Is the cost covered by '{name}' already included in the ex-showroom vehicle price?"

            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_NEGOTIABLE,
                    question=q1,
                    reason=f"The quotation includes a separate {name.lower()} added by the dealer.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the fee is optional, negotiable, or waived."
                        if amt > 0
                        else "Potential amount to review if the fee is negotiable."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.95,
                    requires_verification=True,
                    category="HANDLING_FEE",
                )
            )
            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_NEGOTIABLE,
                    question=q2,
                    reason="Statutory rulings in multiple jurisdictions prohibit separate dealer logistics or depot charges on vehicle sales.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the charge is waived."
                        if amt > 0
                        else "Potential amount to review if waived."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.92,
                    requires_verification=True,
                    category="HANDLING_FEE",
                )
            )
            return questions

        # ── 5. Unexplained / Other Fee / Miscellaneous (Unexplained) ──
        if cat_str in ("UNKNOWN", "OTHER_FEE") or "other" in name_lower or "misc" in name_lower:
            if amt > 0:
                # Question 1: Exact prompt example referencing actual extracted value
                q1 = f"What service does this {amt_str} charge cover, and is it mandatory?"
                # Question 2: Itemized breakdown
                q2 = f"Can you provide an itemized breakdown of what is included in the '{name}' charge?"

                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=CostReviewClassification.UNEXPLAINED,
                        question=q1,
                        reason=f"The quotation lists '{name}' without an itemized explanation of what is covered.",
                        related_charge=name,
                        amount_involved=amt,
                        potential_amount_to_review=amt,
                        potential_impact=f"Potential amount to review: up to {amt_str} upon clarification of charge scope.",
                        evidence_source=evidence_str,
                        confidence=0.85,
                        requires_verification=True,
                        category="UNEXPLAINED",
                    )
                )
                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=CostReviewClassification.UNEXPLAINED,
                        question=q2,
                        reason=f"Without clear line item descriptions, '{name}' cannot be verified against contractual or statutory obligations.",
                        related_charge=name,
                        amount_involved=amt,
                        potential_amount_to_review=amt,
                        potential_impact=f"Potential amount to review: up to {amt_str} upon review.",
                        evidence_source=evidence_str,
                        confidence=0.82,
                        requires_verification=True,
                        category="UNEXPLAINED",
                    )
                )
            return questions

        # ── 6. Registration / R.C. / Road Tax (Requires Verification) ──
        if cat_str in ("REGISTRATION", "ROAD_TAX") or "registration" in name_lower or "r.c." in name_lower:
            if amt > 0:
                q1 = f"What is the breakdown of the {amt_str} registration charge between statutory RTO road tax and dealer processing fees?"
                q2 = "Does the quoted registration amount reflect the exact RTO fee schedule for this vehicle variant and state?"

                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=CostReviewClassification.REQUIRES_VERIFICATION,
                        question=q1,
                        reason="Registration and road tax fees are jurisdiction-dependent and require confirmation against official RTO slabs.",
                        related_charge=name,
                        amount_involved=amt,
                        potential_amount_to_review=amt,
                        potential_impact=f"Potential amount to review: verification of jurisdiction-dependent statutory fee schedule for {amt_str}.",
                        evidence_source=evidence_str,
                        confidence=0.88,
                        requires_verification=True,
                        category="REGISTRATION",
                    )
                )
            return questions

        # ── 7. Offer / Discount (Requires Verification) ──
        if cat_str in ("OFFER", "DISCOUNT") or "offer" in name_lower or "discount" in name_lower:
            if amt > 0:
                q1 = f"Is the {amt_str} offer already deducted from the stated subtotal, or does it apply to the final payable price?"
                q2 = f"Are there any eligibility conditions or financing requirements tied to the {amt_str} offer?"

                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=CostReviewClassification.REQUIRES_VERIFICATION,
                        question=q1,
                        reason=f"The quotation lists '{name}' without clearly indicating whether it has already been deducted from the subtotal.",
                        related_charge=name,
                        amount_involved=amt,
                        potential_amount_to_review=amt,
                        potential_impact=f"Potential amount to review: confirmation of {amt_str} deduction on net payable amount.",
                        evidence_source=evidence_str,
                        confidence=0.86,
                        requires_verification=True,
                        category="OFFER",
                    )
                )
            return questions

        # ── 8. Dealer Package / Service Package (Potentially Optional) ──
        if cat_str in ("DEALER_PACKAGE", "SERVICE_PACKAGE") or any(
            t in name_lower for t in ("dealer package", "service package", "basic kit", "essential kit")
        ):
            q1 = (
                f"What services are included in the {amt_str} {name.lower()}, and can I purchase the vehicle without this package?"
                if amt > 0
                else f"What services are included in '{name}', and is this package optional?"
            )
            q2 = f"Can individual services within '{name}' be unbundled?"

            questions.append(
                CostReviewQuestion(
                    question_id=uuid4(),
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason=f"The quotation bundles services under '{name}' separately from the base vehicle price.",
                    related_charge=name,
                    amount_involved=amt if amt > 0 else None,
                    potential_amount_to_review=amt if amt > 0 else None,
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if the package is optional."
                    ),
                    evidence_source=evidence_str,
                    confidence=0.92,
                    requires_verification=True,
                    category="DEALER_PACKAGE",
                )
            )
            return questions

        # ── 9. FASTag with Markup (Alternative Available) ──
        if cat_str == "FASTAG" or "fastag" in name_lower:
            if amt > 500:
                markup = amt - 500
                q1 = f"What is the breakdown of the {amt_str} FASTag charge, including the security deposit and issuance fee?"
                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                        question=q1,
                        reason="Standard FASTag issuance fees are typically ₹200–₹500 including security deposit, with alternative providers available.",
                        related_charge=name,
                        amount_involved=amt,
                        potential_amount_to_review=markup,
                        potential_impact=f"Potential amount to review: up to ₹{markup:,.0f} if purchasing FASTag directly from issuing banks.",
                        evidence_source=evidence_str,
                        confidence=0.90,
                        requires_verification=True,
                        category="FASTAG",
                    )
                )
            return questions

        return questions

    @classmethod
    def _generate_questions_from_flag(
        cls,
        flag: ExtraCostFlag | dict[str, Any],
    ) -> list[CostReviewQuestion]:
        """Generate targeted questions from an extra cost analysis flag."""
        if isinstance(flag, dict):
            what = flag.get("what", "")
            amt = float(flag.get("amount", 0.0) or 0.0)
            category = flag.get("category", "")
            flag_type = flag.get("flag_type", "")
            evidence = flag.get("evidence")
            why_flagged = flag.get("why_flagged", "")
        else:
            what = flag.what
            amt = float(flag.amount or 0.0)
            category = flag.category
            flag_type = flag.flag_type.value if hasattr(flag.flag_type, "value") else str(flag.flag_type)
            evidence = flag.evidence
            why_flagged = flag.why_flagged

        cat_upper = category.upper() if category else ""
        what_lower = what.lower()
        amt_str = f"₹{amt:,.0f}" if amt > 0 else ""
        evidence_str = evidence or f"Quotation line: '{what} — ₹{amt:,.0f}'"

        # Determine classification from flag
        if flag_type == ExtraCostFlagType.POSSIBLE_DUPLICATE.value or "duplicate" in why_flagged.lower():
            classification = CostReviewClassification.DUPLICATED_OVERLAPPING
            q = f"Can you explain why '{what}' is listed separately, and whether it covers items included in another charge?"
        elif cat_upper in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE") or "handling" in what_lower:
            classification = CostReviewClassification.POTENTIALLY_NEGOTIABLE
            q = f"What service does this {amt_str} charge cover, and is it mandatory?" if amt > 0 else f"What service does '{what}' cover, and is it mandatory?"
        elif cat_upper in ("EXTENDED_WARRANTY", "WARRANTY"):
            classification = CostReviewClassification.POTENTIALLY_OPTIONAL
            q = f"Is the {amt_str} extended warranty package optional?" if amt > 0 else "Is the extended warranty package optional?"
        elif cat_upper in ("ACCESSORY", "ACCESSORY_PACKAGE") or "accessor" in what_lower:
            classification = CostReviewClassification.POTENTIALLY_OPTIONAL
            q = "Are these accessories required for delivery?"
        elif cat_upper == "INSURANCE" or "insurance" in what_lower:
            classification = CostReviewClassification.ALTERNATIVE_AVAILABLE
            q = "Can I choose my own insurer or insurance policy?"
        elif flag_type == ExtraCostFlagType.UNCLEAR_CHARGE.value or cat_upper in ("UNKNOWN", "OTHER_FEE"):
            classification = CostReviewClassification.UNEXPLAINED
            q = f"What service does this {amt_str} charge cover, and is it mandatory?" if amt > 0 else f"What service does '{what}' cover, and is it mandatory?"
        else:
            classification = CostReviewClassification.REQUIRES_VERIFICATION
            q = f"Is the {amt_str} '{what}' charge optional, and can it be removed from the quote?" if amt > 0 else f"Is '{what}' optional, and can it be removed?"

        return [
            CostReviewQuestion(
                question_id=uuid4(),
                classification=classification,
                question=q,
                reason=why_flagged or f"The quotation lists '{what}' separately from the base vehicle price.",
                related_charge=what,
                amount_involved=amt if amt > 0 else None,
                potential_amount_to_review=amt if amt > 0 else None,
                potential_impact=(
                    f"Potential amount to review: up to {amt_str} upon review."
                    if amt > 0
                    else "Potential amount to review upon clarification."
                ),
                evidence_source=evidence_str,
                confidence=0.88,
                requires_verification=True,
                category=cat_upper or "EXTRA_COST",
            )
        ]

    @classmethod
    def _rank_questions(
        cls,
        questions: list[CostReviewQuestion],
    ) -> list[CostReviewQuestion]:
        """Rank questions transparently by amount involved, uncertainty, and classification."""
        scored_questions: list[CostReviewQuestion] = []

        for q in questions:
            amt = q.amount_involved or 0.0

            # 1. Amount factor normalized up to ₹1,00,000
            amount_factor = round(min(1.0, amt / 100000.0), 4)

            # 2. Classification impact factor
            if q.classification == CostReviewClassification.INCONSISTENT:
                class_factor = 1.00
            elif q.classification == CostReviewClassification.DUPLICATED_OVERLAPPING:
                class_factor = 0.95
            elif q.classification == CostReviewClassification.POTENTIALLY_OPTIONAL:
                class_factor = 0.90
            elif q.classification == CostReviewClassification.POTENTIALLY_NEGOTIABLE:
                class_factor = 0.85
            elif q.classification == CostReviewClassification.ALTERNATIVE_AVAILABLE:
                class_factor = 0.80
            elif q.classification == CostReviewClassification.UNEXPLAINED:
                class_factor = 0.75
            else:
                class_factor = 0.70

            # Composite transparent score
            priority_score = round(
                (amount_factor * 0.40) + (class_factor * 0.40) + (q.confidence * 0.20),
                4,
            )

            ranking_factors = {
                "amount_factor": amount_factor,
                "classification_factor": class_factor,
                "confidence_factor": q.confidence,
            }

            scored_q = CostReviewQuestion(
                question_id=q.question_id,
                classification=q.classification,
                question=q.question,
                reason=q.reason,
                related_charge=q.related_charge,
                amount_involved=q.amount_involved,
                potential_amount_to_review=q.potential_amount_to_review,
                potential_impact=q.potential_impact,
                evidence_source=q.evidence_source,
                confidence=q.confidence,
                requires_verification=q.requires_verification,
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
