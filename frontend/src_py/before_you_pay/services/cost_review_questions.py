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
    ContextualFinding,
    ContextualFindingType,
    SmartCostReductionQuestion,
    ValidationCheck,
    ValidationStatus,
)
from before_you_pay.models.cost_review import (
    CostReviewClassification,
    CostReviewQuestion,
    get_canonical_action_for_classification,
)
from before_you_pay.models.document import (
    AmountState,
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
        contextual_findings: list[ContextualFinding] | None = None,
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
        discrepancy_questions = cls._generate_discrepancy_questions(
            checks, components, document=document
        )
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

        # ── 5. Questions from Phase 2 Contextual Findings (Cross-Document / RAG) ──
        if contextual_findings:
            context_questions = cls._generate_questions_from_contextual_findings(
                contextual_findings
            )
            for q in context_questions:
                key = f"context:{q.classification.value}:{q.question}"
                if key not in seen_question_keys:
                    seen_question_keys.add(key)
                    questions.append(q)

        # ── 6. Rank questions transparently by amount and priority ──
        ranked_questions = cls._rank_questions(questions)
        return ranked_questions

    @classmethod
    def generate_smart_questions(
        cls,
        cost_breakdown: list[FinancialComponent] | None = None,
        extra_cost_analysis: ExtraCostAnalysisResult | dict[str, Any] | None = None,
        validation_checks: list[ValidationCheck] | None = None,
        document: StructuredFinancialDocument | None = None,
        contextual_findings: list[ContextualFinding] | None = None,
    ) -> list[SmartCostReductionQuestion]:
        """Generate questions and convert them to standard SmartCostReductionQuestion."""
        questions = cls.generate_questions(
            cost_breakdown=cost_breakdown,
            extra_cost_analysis=extra_cost_analysis,
            validation_checks=validation_checks,
            document=document,
            contextual_findings=contextual_findings,
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
            (
                c
                for c in components
                if (c.category.value if hasattr(c.category, "value") else str(c.category)).upper()
                in ("SUBTOTAL", "BASE_SUBTOTAL")
            ),
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
                            if item.item_id in c.input_field_ids or (
                                item.description and item.description.normalized_value in c.message
                            ):
                                matched_item = item
                                break
                    if matched_item:
                        item_name = matched_item.description.normalized_value
                        amt_val = float(matched_item.total_price.normalized_value)
                        amt_str = (
                            f"₹{int(amt_val):,}" if amt_val == int(amt_val) else f"₹{amt_val:,.2f}"
                        )
                        mrp_val = (
                            float(matched_item.mrp.normalized_value) if matched_item.mrp else None
                        )
                        rate_val = (
                            float(matched_item.unit_price.normalized_value)
                            if matched_item.unit_price
                            else None
                        )
                        disc_val = (
                            float(matched_item.discount.normalized_value)
                            if matched_item.discount
                            else None
                        )

                        if mrp_val is not None and rate_val is not None and disc_val is not None:
                            mrp_str = (
                                f"₹{int(mrp_val):,}"
                                if mrp_val == int(mrp_val)
                                else f"₹{mrp_val:,.2f}"
                            )
                            rate_str = (
                                f"₹{int(rate_val):,}"
                                if rate_val == int(rate_val)
                                else f"₹{rate_val:,.2f}"
                            )
                            disc_str = (
                                f"₹{int(disc_val):,}"
                                if disc_val == int(disc_val)
                                else f"₹{disc_val:,.2f}"
                            )
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
                                suggested_action=get_canonical_action_for_classification(
                                    CostReviewClassification.INCONSISTENT
                                ),
                                document_id=document.document_id if document else None,
                                page_number=1,
                                ocr_line=f"{c.check_code}: {c.message}",
                            )
                        )
                        continue
                delta = c.absolute_delta
                if delta is None or delta <= 0:
                    delta_match = re.search(
                        r"difference(?:\s+of)?\s+[₹$]?([\d,]+(?:\.\d+)?)", c.message, re.IGNORECASE
                    )
                    if delta_match:
                        try:
                            delta = float(delta_match.group(1).replace(",", ""))
                        except ValueError:
                            delta = None

                if delta and delta > 0:
                    diff_str = f"{int(delta):,}" if delta == int(delta) else f"{delta:,.2f}"
                    is_subtotal = (
                        "subtotal" in c.check_code.lower() or "subtotal" in c.message.lower()
                    )
                    term = "subtotal" if is_subtotal else "total"

                    # 1. Primary question (exact prompt example if listed components and subtotal are available)
                    if (
                        subtotal_comp
                        and cls._get_amount(subtotal_comp) > 0
                        and listed_charges_sum > 0
                    ):
                        stated_amt = cls._get_amount(subtotal_comp)
                        listed_str = (
                            f"{int(listed_charges_sum):,}"
                            if listed_charges_sum == int(listed_charges_sum)
                            else f"{listed_charges_sum:,.2f}"
                        )
                        stated_str = (
                            f"{int(stated_amt):,}"
                            if stated_amt == int(stated_amt)
                            else f"{stated_amt:,.2f}"
                        )
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
                            suggested_action=get_canonical_action_for_classification(
                                CostReviewClassification.INCONSISTENT
                            ),
                            document_id=document.document_id if document else None,
                            page_number=1,
                            ocr_line=f"{c.check_code}: {c.message}",
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
                            suggested_action=get_canonical_action_for_classification(
                                CostReviewClassification.INCONSISTENT
                            ),
                            document_id=document.document_id if document else None,
                            page_number=1,
                            ocr_line=c.check_code,
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
            c1_cat = (
                c1.category.value if hasattr(c1.category, "value") else str(c1.category)
            ).upper()
            if c1_cat in (
                "BASE_PRICE",
                "EX_SHOWROOM_PRICE",
                "TOTAL",
                "SUBTOTAL",
                "AMOUNT_PAID",
                "BALANCE_DUE",
            ):
                continue

            for j in range(i + 1, n):
                if j in paired_indices:
                    continue
                c2 = components[j]
                c2_cat = (
                    c2.category.value if hasattr(c2.category, "value") else str(c2.category)
                ).upper()

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

                    c1_prov = (
                        getattr(c1.amount, "provenance", None) if hasattr(c1, "amount") else None
                    )
                    doc_id = getattr(c1_prov, "document_id", None)
                    page_num = c1.page or 1
                    ocr_ln = c1.source_ocr_line or f"{c1.name} / {c2.name}"
                    bbox = c1.bounding_box
                    action_guidance = get_canonical_action_for_classification(
                        CostReviewClassification.DUPLICATED_OVERLAPPING
                    )

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
                            suggested_action=action_guidance,
                            document_id=doc_id,
                            page_number=page_num,
                            ocr_line=ocr_ln,
                            bounding_box=bbox,
                        )
                    )

                    # 2. Secondary question
                    q2 = (
                        f"Does '{c1.name}' cover services or items already included in '{c2.name}'?"
                    )
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
                            suggested_action=action_guidance,
                            document_id=doc_id,
                            page_number=page_num,
                            ocr_line=ocr_ln,
                            bounding_box=bbox,
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
        cat_str = (
            comp.category.value if hasattr(comp.category, "value") else str(comp.category)
        ).upper()
        amt = cls._get_amount(comp)
        name = comp.name.strip()
        name_lower = name.lower()
        amt_str = f"₹{amt:,.0f}" if amt > 0 else ""
        evidence_str = comp.evidence or f"Quotation line: '{name} — ₹{amt:,.0f}'"

        comp_prov = getattr(comp.amount, "provenance", None) if hasattr(comp, "amount") else None
        comp_doc_id = getattr(comp_prov, "document_id", None)
        comp_page = comp.page or 1
        comp_line = (
            comp.source_ocr_line
            or (getattr(comp_prov, "raw_text", None) if comp_prov else None)
            or comp.name
        )
        comp_bbox = comp.bounding_box

        def _make_comp_q(
            classification: CostReviewClassification,
            question: str,
            reason: str,
            potential_impact: str,
            confidence: float,
            category: str | None = None,
            amount_inv: float | None = (amt if amt > 0 else None),
            review_amt: float | None = (amt if amt > 0 else None),
            evidence: str = evidence_str,
            charge_name: str = name,
        ) -> CostReviewQuestion:
            return CostReviewQuestion(
                question_id=uuid4(),
                classification=classification,
                question=question,
                reason=reason,
                related_charge=charge_name,
                amount_involved=amount_inv,
                potential_amount_to_review=review_amt,
                potential_impact=potential_impact,
                evidence_source=evidence,
                confidence=confidence,
                requires_verification=True,
                category=category,
                suggested_action=get_canonical_action_for_classification(classification),
                document_id=comp_doc_id,
                page_number=comp_page,
                ocr_line=comp_line,
                bounding_box=comp_bbox,
            )

        # ── 0. Unreadable / Missing / Unknown / Not Applicable / Zero Amount Handling ──
        if getattr(comp, "amount_state", None) == AmountState.UNREADABLE:
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.REQUIRES_VERIFICATION,
                    question=f"The quoted amount for '{name}' could not be legibly read from the document. What is the confirmed amount for this item?",
                    reason=f"The line item '{name}' is present on the quotation, but the monetary figure is unreadable from the scan.",
                    potential_impact="Verification of unreadable line item amount before payment authorization.",
                    confidence=0.90,
                    category="REQUIRES_VERIFICATION",
                    amount_inv=None,
                    review_amt=None,
                    evidence=comp.evidence or f"Document line: '{name}'",
                )
            )
            return questions
        elif getattr(comp, "amount_state", None) == AmountState.MISSING:
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.REQUIRES_VERIFICATION,
                    question=f"The line item '{name}' does not specify a monetary amount. Is there an additional charge for this item?",
                    reason=f"The quotation references '{name}' without an explicit stated price.",
                    potential_impact="Confirmation of whether an unpriced component incurs a separate charge.",
                    confidence=0.90,
                    category="REQUIRES_VERIFICATION",
                    amount_inv=None,
                    review_amt=None,
                    evidence=comp.evidence or f"Document line: '{name}'",
                )
            )
            return questions
        elif getattr(comp, "amount_state", None) == AmountState.UNKNOWN:
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.REQUIRES_VERIFICATION,
                    question=f"Could you clarify the exact amount and scope of the '{name}' charge?",
                    reason=f"The amount for '{name}' could not be definitively determined.",
                    potential_impact="Clarification of undetermined charge before proceeding.",
                    confidence=0.85,
                    category="REQUIRES_VERIFICATION",
                    amount_inv=None,
                    review_amt=None,
                    evidence=comp.evidence or f"Document line: '{name}'",
                )
            )
            return questions
        elif getattr(comp, "amount_state", None) == AmountState.NOT_APPLICABLE:
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.REQUIRES_VERIFICATION,
                    question=f"The line item '{name}' is marked as not applicable. Could you confirm whether this item applies to this quotation?",
                    reason=f"The line item '{name}' is marked as not applicable on the document and requires verification of scope.",
                    potential_impact="Verification of whether a not-applicable item carries any terms or obligations.",
                    confidence=0.90,
                    category="REQUIRES_VERIFICATION",
                    amount_inv=None,
                    review_amt=None,
                    evidence=comp.evidence or f"Document line: '{name}'",
                )
            )
            return questions
        elif getattr(comp, "amount_state", None) == AmountState.ZERO or (
            amt == 0.0 and getattr(comp, "amount_state", None) == AmountState.PRESENT
        ):
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.REQUIRES_VERIFICATION,
                    question=f"Could you confirm the {name.lower()} shown in the quotation and whether any associated costs will apply later?",
                    reason=f"The line item '{name}' is listed with zero amount on the quotation, requiring confirmation of whether future fees apply.",
                    potential_impact="Confirmation of zero-cost line item terms before proceeding.",
                    confidence=0.90,
                    category="REQUIRES_VERIFICATION",
                    amount_inv=0.0,
                    review_amt=None,
                    evidence=comp.evidence or f"Document line: '{name}'",
                )
            )
            return questions

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
                _make_comp_q(
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q1,
                    reason="The quotation includes dealer-arranged insurance as a separate line item.",
                    potential_impact=(
                        f"Potential amount to review: {amt_str} if independent third-party insurance provides equivalent coverage at lower premium."
                        if amt > 0
                        else "Potential amount to review if independent coverage is permitted."
                    ),
                    confidence=0.92,
                    category="INSURANCE",
                )
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q2,
                    reason="Dealer-provided insurance quotes may bundle premium rates higher than direct insurer market rates.",
                    potential_impact=(
                        f"Potential amount to review: {amt_str} upon comparing competitive market quotes."
                        if amt > 0
                        else "Potential amount to review upon market comparison."
                    ),
                    confidence=0.90,
                    category="INSURANCE",
                )
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                    question=q3,
                    reason="Insurance line items often combine mandatory third-party liability with discretionary add-on riders.",
                    potential_impact="Potential amount to review if discretionary insurance riders are customized or omitted.",
                    confidence=0.88,
                    category="INSURANCE",
                )
            )
            return questions

        # ── 2. Extended Warranty (Potentially Optional) ──
        if cat_str in ("EXTENDED_WARRANTY", "WARRANTY") or "warranty" in name_lower:
            q1 = (
                f"Is the {amt_str} extended warranty package optional?"
                if amt > 0
                else "Is the extended warranty package optional?"
            )
            q2 = (
                f"Can this vehicle be purchased without the {amt_str} extended warranty?"
                if amt > 0
                else "Can this vehicle be purchased without the extended warranty?"
            )

            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason="The quotation lists warranty as a separate charge from the base vehicle price.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the extended warranty package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if the warranty is optional."
                    ),
                    confidence=0.95,
                    category="EXTENDED_WARRANTY",
                )
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q2,
                    reason="Extended warranties are elective commercial agreements beyond statutory factory guarantees.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if opting for standard factory warranty only."
                        if amt > 0
                        else "Potential amount to review if opting for factory warranty only."
                    ),
                    confidence=0.92,
                    category="EXTENDED_WARRANTY",
                )
            )
            return questions

        # ── 3. Accessories / Accessory Package (Potentially Optional) ──
        if cat_str in ("ACCESSORY", "ACCESSORY_PACKAGE") or "accessor" in name_lower:
            q1 = "Are these accessories required for delivery?"
            q2 = (
                f"Which accessories are included in the {amt_str} package, and can I remove individual accessories I don't need?"
                if amt > 0
                else f"Which accessories are included in '{name}', and can individual items be removed?"
            )

            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason="The quotation lists accessories separately from the base vehicle price.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if accessory package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if accessories are optional."
                    ),
                    confidence=0.93,
                    category="ACCESSORY",
                )
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q2,
                    reason="Dealers frequently bundle multiple cosmetic or utility accessories into a single package line item.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} for unwanted individual items within the package."
                        if amt > 0
                        else "Potential amount to review for individual items within the package."
                    ),
                    confidence=0.91,
                    category="ACCESSORY",
                )
            )
            return questions

        # ── 4. Dealer Handling Charge / Logistics Fee (Potentially Negotiable) ──
        if cat_str in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE") or any(
            t in name_lower
            for t in (
                "handling",
                "logistics",
                "depot",
                "incidental",
                "documentation fee",
                "facilitation",
            )
        ):
            q1 = (
                f"What service does this {amt_str} charge cover, and is it mandatory?"
                if amt > 0
                else f"What service does the '{name}' charge cover, and is it mandatory?"
            )
            q2 = (
                f"Is the {amt_str} {name.lower()} negotiable or waivable under consumer transport guidelines?"
                if amt > 0
                else f"Is the {name.lower()} negotiable or waivable under consumer transport guidelines?"
            )

            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_NEGOTIABLE,
                    question=q1,
                    reason=f"The quotation includes a separate {name.lower()} added by the dealer.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the fee is optional, negotiable, or waived."
                        if amt > 0
                        else "Potential amount to review if the fee is negotiable."
                    ),
                    confidence=0.95,
                    category="HANDLING_FEE",
                )
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_NEGOTIABLE,
                    question=q2,
                    reason="Statutory rulings in multiple jurisdictions prohibit separate dealer logistics or depot charges on vehicle sales.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the charge is waived."
                        if amt > 0
                        else "Potential amount to review if waived."
                    ),
                    confidence=0.92,
                    category="HANDLING_FEE",
                )
            )
            return questions

        # ── 5. Unexplained / Other Fee / Miscellaneous (Unexplained) ──
        if cat_str in ("UNKNOWN", "OTHER_FEE") or "other" in name_lower or "misc" in name_lower:
            if amt > 0:
                q1 = f"What service does this {amt_str} charge cover, and is it mandatory?"
                q2 = f"Can you provide an itemized breakdown of what is included in the '{name}' charge?"

                questions.append(
                    _make_comp_q(
                        classification=CostReviewClassification.UNEXPLAINED,
                        question=q1,
                        reason=f"The quotation lists '{name}' without an itemized explanation of what is covered.",
                        potential_impact=f"Potential amount to review: up to {amt_str} upon clarification of charge scope.",
                        confidence=0.85,
                        category="UNEXPLAINED",
                    )
                )
                questions.append(
                    _make_comp_q(
                        classification=CostReviewClassification.UNEXPLAINED,
                        question=q2,
                        reason=f"Without clear line item descriptions, '{name}' cannot be verified against contractual or statutory obligations.",
                        potential_impact=f"Potential amount to review: up to {amt_str} upon review.",
                        confidence=0.82,
                        category="UNEXPLAINED",
                    )
                )
            return questions

        # ── 6. Registration / R.C. / Road Tax (Requires Verification) ──
        if (
            cat_str in ("REGISTRATION", "ROAD_TAX")
            or "registration" in name_lower
            or "r.c." in name_lower
        ):
            if amt > 0:
                q1 = f"What is the breakdown of the {amt_str} registration charge between statutory RTO road tax and dealer processing fees?"
                questions.append(
                    _make_comp_q(
                        classification=CostReviewClassification.REQUIRES_VERIFICATION,
                        question=q1,
                        reason="Registration and road tax fees are jurisdiction-dependent and require confirmation against official RTO slabs.",
                        potential_impact=f"Potential amount to review: verification of jurisdiction-dependent statutory fee schedule for {amt_str}.",
                        confidence=0.88,
                        category="REGISTRATION",
                    )
                )
            return questions

        # ── 7. Offer / Discount (Requires Verification) ──
        if cat_str in ("OFFER", "DISCOUNT") or "offer" in name_lower or "discount" in name_lower:
            if amt > 0:
                q1 = f"Is the {amt_str} offer already deducted from the stated subtotal, or does it apply to the final payable price?"
                questions.append(
                    _make_comp_q(
                        classification=CostReviewClassification.REQUIRES_VERIFICATION,
                        question=q1,
                        reason=f"The quotation lists '{name}' without clearly indicating whether it has already been deducted from the subtotal.",
                        potential_impact=f"Potential amount to review: confirmation of {amt_str} deduction on net payable amount.",
                        confidence=0.86,
                        category="OFFER",
                    )
                )
            return questions

        # ── 8. Dealer Package / Service Package (Potentially Optional) ──
        if cat_str in ("DEALER_PACKAGE", "SERVICE_PACKAGE") or any(
            t in name_lower
            for t in ("dealer package", "service package", "basic kit", "essential kit")
        ):
            q1 = (
                f"What services are included in the {amt_str} {name.lower()}, and can I purchase the vehicle without this package?"
                if amt > 0
                else f"What services are included in '{name}', and is this package optional?"
            )
            questions.append(
                _make_comp_q(
                    classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                    question=q1,
                    reason=f"The quotation bundles services under '{name}' separately from the base vehicle price.",
                    potential_impact=(
                        f"Potential amount to review: up to {amt_str} if the package is optional and declined."
                        if amt > 0
                        else "Potential amount to review if the package is optional."
                    ),
                    confidence=0.92,
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
                    _make_comp_q(
                        classification=CostReviewClassification.ALTERNATIVE_AVAILABLE,
                        question=q1,
                        reason="Standard FASTag issuance fees are typically ₹200–₹500 including security deposit, with alternative providers available.",
                        potential_impact=f"Potential amount to review: up to ₹{markup:,.0f} if purchasing FASTag directly from issuing banks.",
                        confidence=0.90,
                        category="FASTAG",
                        review_amt=markup,
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
            flag_type = (
                flag.flag_type.value if hasattr(flag.flag_type, "value") else str(flag.flag_type)
            )
            evidence = flag.evidence
            why_flagged = flag.why_flagged

        cat_upper = category.upper() if category else ""
        what_lower = what.lower()
        amt_str = f"₹{amt:,.0f}" if amt > 0 else ""
        evidence_str = evidence or f"Quotation line: '{what} — ₹{amt:,.0f}'"

        # Determine classification from flag
        if (
            flag_type == ExtraCostFlagType.POSSIBLE_DUPLICATE.value
            or "duplicate" in why_flagged.lower()
        ):
            classification = CostReviewClassification.DUPLICATED_OVERLAPPING
            q = f"Can you explain why '{what}' is listed separately, and whether it covers items included in another charge?"
        elif (
            cat_upper in ("HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE")
            or "handling" in what_lower
        ):
            classification = CostReviewClassification.POTENTIALLY_NEGOTIABLE
            q = (
                f"What service does this {amt_str} charge cover, and is it mandatory?"
                if amt > 0
                else f"What service does '{what}' cover, and is it mandatory?"
            )
        elif cat_upper in ("EXTENDED_WARRANTY", "WARRANTY"):
            classification = CostReviewClassification.POTENTIALLY_OPTIONAL
            q = (
                f"Is the {amt_str} extended warranty package optional?"
                if amt > 0
                else "Is the extended warranty package optional?"
            )
        elif cat_upper in ("ACCESSORY", "ACCESSORY_PACKAGE") or "accessor" in what_lower:
            classification = CostReviewClassification.POTENTIALLY_OPTIONAL
            q = "Are these accessories required for delivery?"
        elif cat_upper == "INSURANCE" or "insurance" in what_lower:
            classification = CostReviewClassification.ALTERNATIVE_AVAILABLE
            q = "Can I choose my own insurer or insurance policy?"
        elif flag_type == ExtraCostFlagType.UNCLEAR_CHARGE.value or cat_upper in (
            "UNKNOWN",
            "OTHER_FEE",
        ):
            classification = CostReviewClassification.UNEXPLAINED
            q = (
                f"What service does this {amt_str} charge cover, and is it mandatory?"
                if amt > 0
                else f"What service does '{what}' cover, and is it mandatory?"
            )
        else:
            classification = CostReviewClassification.REQUIRES_VERIFICATION
            q = (
                f"Is the {amt_str} '{what}' charge optional, and can it be removed from the quote?"
                if amt > 0
                else f"Is '{what}' optional, and can it be removed?"
            )

        return [
            CostReviewQuestion(
                question_id=uuid4(),
                classification=classification,
                question=q,
                reason=why_flagged
                or f"The quotation lists '{what}' separately from the base vehicle price.",
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
                suggested_action=get_canonical_action_for_classification(classification),
            )
        ]

    @classmethod
    def _generate_questions_from_contextual_findings(
        cls,
        contextual_findings: list[ContextualFinding],
    ) -> list[CostReviewQuestion]:
        """Generate targeted evidence-based questions from Phase 2 cross-document contextual findings."""
        questions: list[CostReviewQuestion] = []
        for finding in contextual_findings:
            if finding.finding_type == ContextualFindingType.NO_RELEVANT_CONTEXT:
                continue

            # Determine classification
            if finding.finding_type == ContextualFindingType.POTENTIAL_OVERLAP:
                classification = CostReviewClassification.DUPLICATED_OVERLAPPING
            elif finding.finding_type == ContextualFindingType.PRICE_VARIANCE:
                classification = CostReviewClassification.POTENTIALLY_NEGOTIABLE
            elif finding.finding_type == ContextualFindingType.COVERAGE_COMPARISON:
                classification = CostReviewClassification.ALTERNATIVE_AVAILABLE
            else:
                classification = CostReviewClassification.REQUIRES_VERIFICATION

            action = get_canonical_action_for_classification(classification)

            doc_id = None
            page_num = 1
            ocr_ln = None
            bbox = None
            if finding.primary_evidence:
                p_ev = finding.primary_evidence[0]
                doc_id = p_ev.document_id
                page_num = p_ev.page_number
                ocr_ln = p_ev.raw_text
                bbox = p_ev.bounding_box

            evidence_str = finding.description
            if finding.primary_evidence and finding.supporting_evidence:
                evidence_str = f"Primary: '{finding.primary_evidence[0].raw_text}' vs Supporting: '{finding.supporting_evidence[0].raw_text}'"

            amt = finding.primary_amount or finding.delta_amount
            amt_str = (
                f"₹{int(amt):,}"
                if (amt and amt == int(amt))
                else f"₹{amt:,.2f}"
                if (amt and amt > 0)
                else ""
            )

            finding_questions = list(finding.questions_to_ask) if finding.questions_to_ask else []
            if not finding_questions:
                if classification == CostReviewClassification.DUPLICATED_OVERLAPPING:
                    if amt:
                        finding_questions.append(
                            f"Can you confirm whether the {amt_str} {finding.title} component provides coverage beyond what is already included in the supporting document?"
                        )
                    else:
                        finding_questions.append(
                            f"Can you confirm whether the {finding.title} component provides coverage beyond what is already included in the supporting document?"
                        )
                elif classification == CostReviewClassification.POTENTIALLY_NEGOTIABLE:
                    finding_questions.append(
                        f"The quotation lists {finding.title} at {amt_str}, whereas the supporting document indicates a different amount. Can this amount be clarified or revised?"
                    )
                elif classification == CostReviewClassification.ALTERNATIVE_AVAILABLE:
                    finding_questions.append(
                        f"Could you clarify the difference in coverage or terms between the {finding.title} offered and the existing document?"
                    )
                else:
                    finding_questions.append(
                        f"Could you please confirm the terms and scope for {finding.title} compared to the supporting document?"
                    )

            for q_text in finding_questions[:2]:
                questions.append(
                    CostReviewQuestion(
                        question_id=uuid4(),
                        classification=classification,
                        question=q_text,
                        reason=finding.description,
                        related_charge=finding.title,
                        amount_involved=amt,
                        potential_amount_to_review=amt,
                        potential_impact=f"Potential amount to review: {amt_str} upon review against supporting document."
                        if amt_str
                        else "Potential amount to review upon clarification.",
                        evidence_source=evidence_str,
                        confidence=finding.confidence,
                        requires_verification=True,
                        category=finding.finding_type.value,
                        suggested_action=action,
                        document_id=doc_id,
                        page_number=page_num,
                        ocr_line=ocr_ln,
                        bounding_box=bbox,
                    )
                )
        return questions

    @classmethod
    def generate_suggested_negotiation_message(
        cls,
        questions: list[CostReviewQuestion] | list[SmartCostReductionQuestion],
        document: StructuredFinancialDocument | None = None,
        contextual_findings: list[ContextualFinding] | None = None,
        vendor_name: str | None = None,
    ) -> str:
        """Construct a concise, polite, professional, and editable suggested negotiation message.

        The message strictly references actual findings, preserves uncertainty, avoids accusations
        or guaranteed savings, and distinguishes clarification from negotiation.
        """
        v_name = vendor_name
        if not v_name and document and document.vendor_name:
            v_name = document.vendor_name.normalized_value or document.vendor_name.raw_text

        salutation = f"Hello {v_name} Team," if v_name else "Hello,"

        if not questions and not contextual_findings:
            return (
                f"{salutation}\n\n"
                "I have reviewed the quotation and the listed charges appear consistent with standard terms. "
                "Could you please confirm the final payable amount and payment details so we can proceed?\n\n"
                "Thank you for your assistance."
            )

        items_to_mention: list[str] = []
        seen_charges: set[str] = set()

        for q in questions:
            charge = (q.related_charge or "").strip()
            if charge.lower() in seen_charges:
                continue
            seen_charges.add(charge.lower())

            amt = q.amount_involved
            amt_str = (
                f"₹{int(amt):,}"
                if (amt and amt == int(amt))
                else f"₹{amt:,.2f}"
                if (amt and amt > 0)
                else ""
            )

            cls_val = (
                q.classification.value
                if hasattr(q.classification, "value")
                else str(q.classification)
            )

            if cls_val == CostReviewClassification.INCONSISTENT.value:
                items_to_mention.append(f"• Arithmetic / Total: {q.question}")
            elif cls_val == CostReviewClassification.DUPLICATED_OVERLAPPING.value:
                items_to_mention.append(
                    f"• {charge}: Could you please confirm if this covers services or items already included elsewhere in the quotation?"
                )
            elif cls_val == CostReviewClassification.POTENTIALLY_OPTIONAL.value:
                if amt_str:
                    items_to_mention.append(
                        f"• {charge} ({amt_str}): Could you please clarify if this package is optional, and share a revised quotation if it is declined?"
                    )
                else:
                    items_to_mention.append(
                        f"• {charge}: Could you please confirm if this item is optional and whether it can be removed from the quote?"
                    )
            elif cls_val == CostReviewClassification.POTENTIALLY_NEGOTIABLE.value:
                if amt_str:
                    items_to_mention.append(
                        f"• {charge} ({amt_str}): What specific service does this cover, and is there any flexibility or waiver available on this charge?"
                    )
                else:
                    items_to_mention.append(
                        f"• {charge}: What specific service does this charge cover, and is this fee negotiable?"
                    )
            elif cls_val == CostReviewClassification.ALTERNATIVE_AVAILABLE.value:
                if amt_str:
                    items_to_mention.append(
                        f"• {charge} ({amt_str}): Could you please confirm whether I can arrange an independent alternative or adjust the included options?"
                    )
                else:
                    items_to_mention.append(
                        f"• {charge}: Could you please clarify if independent alternative coverage or options can be selected?"
                    )
            elif cls_val == CostReviewClassification.UNEXPLAINED.value:
                items_to_mention.append(
                    f"• {charge}{f' ({amt_str})' if amt_str else ''}: Could you provide an itemized breakdown of what is included in this charge?"
                )
            else:
                items_to_mention.append(
                    f"• {charge}{f' ({amt_str})' if amt_str else ''}: {q.question}"
                )

            if len(items_to_mention) >= 4:
                break

        if contextual_findings and len(items_to_mention) < 4:
            for cf in contextual_findings:
                if (
                    cf.title.lower() in seen_charges
                    or cf.finding_type == ContextualFindingType.NO_RELEVANT_CONTEXT
                ):
                    continue
                seen_charges.add(cf.title.lower())
                c_amt = cf.primary_amount
                c_amt_str = (
                    f"₹{int(c_amt):,}"
                    if (c_amt and c_amt == int(c_amt))
                    else f"₹{c_amt:,.2f}"
                    if (c_amt and c_amt > 0)
                    else ""
                )
                items_to_mention.append(
                    f"• {cf.title}{f' ({c_amt_str})' if c_amt_str else ''}: Could you please confirm if this provides coverage beyond what is already included in my existing policy/records?"
                )
                if len(items_to_mention) >= 4:
                    break

        items_block = "\n".join(items_to_mention)
        body = (
            f"{salutation}\n\n"
            "I reviewed the quotation and wanted to clarify a few specific items before proceeding:\n\n"
            f"{items_block}\n\n"
            "Could you please share a revised quotation or breakdown reflecting these clarifications? "
            "Thank you for your assistance."
        )
        return body

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
                suggested_action=q.suggested_action,
                document_id=q.document_id,
                page_number=q.page_number,
                ocr_line=q.ocr_line,
                bounding_box=q.bounding_box,
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
