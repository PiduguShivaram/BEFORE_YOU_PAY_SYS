"""Comprehensive Phase 3 Verification Suite: EXPLAIN -> ASK -> ACT.

Validates all Phase 3 requirements (A through U):
A. Finding -> Question
B. Finding -> Suggested Message
C. Potentially Optional
D. Potentially Negotiable
E. Alternatives to Compare
F. Potential Overlap
G. Amount Discrepancy
H. Unexplained Charge
I. Missing amount
J. Unknown amount
K. Unreadable amount
L. Zero amount
M. Not applicable amount
N. Evidence/provenance propagation
O. No unsupported claims
P. No guaranteed-savings language
Q. No fabricated amount
R. Supporting-document contextual finding -> question
S. Zetran regression
T. Vehicle quotation regression
U. Phase 2 cross-document regression
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from before_you_pay.models.analysis import (
    ContextualEvidence,
    ContextualFinding,
    ContextualFindingType,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.models.cost_review import (
    CostReviewClassification,
    get_canonical_action_for_classification,
)
from before_you_pay.models.document import (
    AmountState,
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    LineItem,
    OptionalityStatus,
    StructuredFinancialDocument,
)
from before_you_pay.services.cost_review_questions import CostReviewQuestionsService
from before_you_pay.services.result import ResultAggregatorService


def _make_field(key: str, val: Any, raw: str = "") -> ExtractedField:
    prov = FieldProvenance(
        document_id=uuid4(),
        page_id=uuid4(),
        ocr_line_ids=[uuid4()],
        raw_text=raw or str(val),
    )
    return ExtractedField(
        field_key=key,
        normalized_value=val,
        confidence=0.95,
        provenance=prov,
    )


def _make_component_with_state(
    name: str,
    amount: float,
    category: ComponentCategory,
    amount_state: AmountState = AmountState.PRESENT,
    opt_status: OptionalityStatus = OptionalityStatus.UNCLEAR,
    evidence: str | None = None,
    doc_id: str | None = None,
) -> FinancialComponent:
    """Helper to build a FinancialComponent with explicit AmountState and provenance."""
    d_id = uuid4() if not doc_id else uuid4()
    p_id = uuid4()
    l_id = uuid4()
    prov = FieldProvenance(
        document_id=d_id,
        page_id=p_id,
        ocr_line_ids=[l_id],
        raw_text=f"{name} — ₹{amount:,.0f}" if amount > 0 else name,
    )
    amt_field = ExtractedField(
        field_key="component_amount",
        normalized_value=amount
        if amount_state in (AmountState.PRESENT, AmountState.ZERO)
        else None,
        confidence=0.95,
        provenance=prov,
    )
    bbox = BoundingBox(
        x=0.1, y=0.2, width=0.8, height=0.03, coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE
    )
    return FinancialComponent(
        component_id=uuid4(),
        name=name,
        raw_name=name,
        normalized_name=name.lower(),
        amount=amt_field,
        amount_state=amount_state,
        category=category,
        charge_nature=ChargeNature.CHARGE,
        optionality_status=opt_status,
        confidence=0.95,
        evidence=evidence or f"Document line: '{name}'",
        source_ocr_line=f"{name} — ₹{amount:,.0f}" if amount > 0 else name,
        bounding_box=bbox,
        page=1,
    )


class TestPhase3ExplainAskAct:
    """Rigorous verification of the Phase 3 EXPLAIN -> ASK -> ACT layer."""

    # ── A. Finding -> Question ──
    def test_a_finding_to_question(self):
        comp = _make_component_with_state(
            "Extended Warranty",
            24000.0,
            ComponentCategory.EXTENDED_WARRANTY,
            evidence="Quotation line: 'Extended Warranty — ₹24,000'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert "warranty" in q.question.lower()
        assert q.related_charge == "Extended Warranty"
        assert q.amount_involved == 24000.0
        assert q.evidence_source is not None
        assert "24,000" in q.evidence_source or "Extended Warranty" in q.evidence_source

    # ── B. Finding -> Suggested Message ──
    def test_b_finding_to_suggested_message(self):
        comp = _make_component_with_state(
            "Extended Warranty",
            24000.0,
            ComponentCategory.EXTENDED_WARRANTY,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        msg = CostReviewQuestionsService.generate_suggested_negotiation_message(
            questions=questions,
            vendor_name="Apex Motors",
        )
        assert "Hello Apex Motors Team," in msg
        assert "Extended Warranty" in msg
        assert "₹24,000" in msg
        assert "revised quotation" in msg.lower()
        # Verify it remains editable and non-accusatory
        assert "illegal" not in msg.lower()
        assert "scam" not in msg.lower()
        assert "you will save" not in msg.lower()

    # ── C. Potentially Optional ──
    def test_c_potentially_optional(self):
        comp = _make_component_with_state(
            "Basic Accessory Kit",
            8500.0,
            ComponentCategory.ACCESSORY,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.classification == CostReviewClassification.POTENTIALLY_OPTIONAL
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.POTENTIALLY_OPTIONAL
        )
        assert q.suggested_action == "Ask whether the item can be removed or declined."

    # ── D. Potentially Negotiable ──
    def test_d_potentially_negotiable(self):
        comp = _make_component_with_state(
            "Dealer Handling Charges",
            9500.0,
            ComponentCategory.HANDLING_FEE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.classification == CostReviewClassification.POTENTIALLY_NEGOTIABLE
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.POTENTIALLY_NEGOTIABLE
        )
        assert q.suggested_action == "Ask whether the amount can be revised."

    # ── E. Alternatives to Compare ──
    def test_e_alternatives_to_compare(self):
        comp = _make_component_with_state(
            "Comprehensive Insurance",
            34500.0,
            ComponentCategory.INSURANCE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.classification == CostReviewClassification.ALTERNATIVE_AVAILABLE
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.ALTERNATIVE_AVAILABLE
        )
        assert q.suggested_action == "Ask for alternative products/services/pricing."

    # ── F. Potential Overlap ──
    def test_f_potential_overlap(self):
        c1 = _make_component_with_state(
            "Roadside Assistance", 4000.0, ComponentCategory.SERVICE_PACKAGE
        )
        c2 = _make_component_with_state(
            "24x7 Road Assistance", 3500.0, ComponentCategory.SERVICE_PACKAGE
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[c1, c2])
        overlap_qs = [
            q
            for q in questions
            if q.classification == CostReviewClassification.DUPLICATED_OVERLAPPING
        ]
        assert len(overlap_qs) >= 1
        q = overlap_qs[0]
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.DUPLICATED_OVERLAPPING
        )
        assert q.suggested_action == "Ask whether existing coverage already covers the same area."

    # ── G. Amount Discrepancy ──
    def test_g_amount_discrepancy(self):
        c1 = _make_component_with_state(
            "Base Vehicle", 800000.0, ComponentCategory.EX_SHOWROOM_PRICE
        )
        subtotal_comp = _make_component_with_state("Subtotal", 805000.0, ComponentCategory.SUBTOTAL)
        val_check = ValidationCheck(
            validation_id=uuid4(),
            check_code="QUOTATION_SUBTOTAL_CONSISTENCY",
            status=ValidationStatus.FAIL,
            input_field_ids=[uuid4()],
            expected_value=805000.0,
            calculated_value=800000.0,
            absolute_delta=5000.0,
            severity=ValidationSeverity.WARNING,
            message="Component reconciliation discrepancy: difference of ₹5,000.",
        )
        questions = CostReviewQuestionsService.generate_questions(
            cost_breakdown=[c1, subtotal_comp],
            validation_checks=[val_check],
        )
        inconsistent_qs = [
            q for q in questions if q.classification == CostReviewClassification.INCONSISTENT
        ]
        assert len(inconsistent_qs) >= 1
        q = inconsistent_qs[0]
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.INCONSISTENT
        )
        assert q.suggested_action == "Ask the provider to explain/reconcile the difference."
        assert "5,000" in q.potential_impact or "805,000" in q.question

    # ── H. Unexplained Charge ──
    def test_h_unexplained_charge(self):
        comp = _make_component_with_state(
            "Administrative & Sundry Charges",
            4500.0,
            ComponentCategory.OTHER_FEE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        unexp_qs = [
            q for q in questions if q.classification == CostReviewClassification.UNEXPLAINED
        ]
        assert len(unexp_qs) >= 1
        q = unexp_qs[0]
        assert q.suggested_action == get_canonical_action_for_classification(
            CostReviewClassification.UNEXPLAINED
        )
        assert q.suggested_action == "Ask the provider to explain what the charge represents."

    # ── I. Missing Amount ──
    def test_i_missing_amount(self):
        comp = _make_component_with_state(
            "Registration Fee",
            0.0,
            ComponentCategory.REGISTRATION,
            amount_state=AmountState.MISSING,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.amount_involved is None
        assert "₹0" not in q.question
        assert (
            "does not specify" in q.question.lower()
            or "not stated" in q.question.lower()
            or "confirm" in q.question.lower()
        )

    # ── J. Unknown Amount ──
    def test_j_unknown_amount(self):
        comp = _make_component_with_state(
            "Dealer Logistics",
            0.0,
            ComponentCategory.HANDLING_FEE,
            amount_state=AmountState.UNKNOWN,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.amount_involved is None
        assert "₹0" not in q.question
        assert "unspecified" in q.question.lower() or "amount" in q.question.lower()

    # ── K. Unreadable Amount ──
    def test_k_unreadable_amount(self):
        comp = _make_component_with_state(
            "FASTag Tag Charge",
            0.0,
            ComponentCategory.FASTAG,
            amount_state=AmountState.UNREADABLE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.amount_involved is None
        assert "₹0" not in q.question
        assert "unreadable" in q.reason.lower()

    # ── L. Zero Amount ──
    def test_l_zero_amount(self):
        comp = _make_component_with_state(
            "Zero Dep Cover",
            0.0,
            ComponentCategory.INSURANCE,
            amount_state=AmountState.ZERO,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        # Never ask "Why is the ₹0 charge present?"
        assert "why is the ₹0" not in q.question.lower()
        assert "zero amount" in q.reason.lower() or "apply later" in q.question.lower()

    # ── M. Not Applicable Amount ──
    def test_m_not_applicable_amount(self):
        comp = _make_component_with_state(
            "State Entry Tax",
            0.0,
            ComponentCategory.ROAD_TAX,
            amount_state=AmountState.NOT_APPLICABLE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert "applies" in q.question.lower() or "not applicable" in q.reason.lower()

    # ── N. Evidence / Provenance Propagation ──
    def test_n_evidence_provenance_propagation(self):
        comp = _make_component_with_state(
            "Extended Warranty",
            24000.0,
            ComponentCategory.EXTENDED_WARRANTY,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        assert len(questions) >= 1
        q = questions[0]
        assert q.document_id is not None
        assert q.page_number == 1
        assert q.ocr_line is not None
        assert q.bounding_box is not None

        smart_q = q.to_smart_question()
        assert smart_q.document_id == q.document_id
        assert smart_q.page_number == q.page_number
        assert smart_q.ocr_line == q.ocr_line
        assert smart_q.bounding_box == q.bounding_box
        assert smart_q.suggested_action == q.suggested_action

    # ── O. No Unsupported Claims ──
    def test_o_no_unsupported_claims(self):
        comp = _make_component_with_state(
            "Documentation Charge",
            5000.0,
            ComponentCategory.HANDLING_FEE,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        forbidden = re.compile(
            r"\b(scam|fraud|illegal|criminal|unnecessary|you don't need this|cheating|do not pay)\b",
            re.IGNORECASE,
        )
        for q in questions:
            assert not forbidden.search(q.question)
            assert not forbidden.search(q.reason)
            assert not forbidden.search(q.potential_impact)

    # ── P. No Guaranteed-Savings Language ──
    def test_p_no_guaranteed_savings_language(self):
        comp = _make_component_with_state(
            "Accessories Kit",
            15000.0,
            ComponentCategory.ACCESSORY,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        forbidden_savings = re.compile(
            r"\b(you will save|guaranteed saving|you can definitely save|your savings are)\b",
            re.IGNORECASE,
        )
        for q in questions:
            assert not forbidden_savings.search(q.question)
            assert not forbidden_savings.search(q.reason)
            assert not forbidden_savings.search(q.potential_impact)
            assert "potential amount to review" in q.potential_impact.lower()

    # ── Q. No Fabricated Amount ──
    def test_q_no_fabricated_amount(self):
        comp = _make_component_with_state(
            "Hypothecation Facilitation",
            0.0,
            ComponentCategory.OTHER_FEE,
            amount_state=AmountState.MISSING,
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
        for q in questions:
            assert q.amount_involved is None
            assert q.potential_amount_to_review is None
            assert "₹0" not in q.question

    # ── R. Supporting-Document Contextual Finding -> Question ──
    def test_r_supporting_document_contextual_finding(self):
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        finding = ContextualFinding(
            finding_id=uuid4(),
            finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
            title="Insurance Coverage Overlap",
            description="Quotation includes dealer insurance ₹34,500 whereas supporting policy document reflects existing coverage ₹32,000.",
            primary_evidence=[
                ContextualEvidence(
                    document_role="primary",
                    document_id=doc_id1,
                    source_document_type="quotation",
                    raw_text="Insurance Premium: ₹34,500",
                    amount=34500.0,
                )
            ],
            supporting_evidence=[
                ContextualEvidence(
                    document_role="supporting",
                    document_id=doc_id2,
                    source_document_type="insurance_policy",
                    raw_text="Active Policy Coverage: ₹32,000",
                    amount=32000.0,
                )
            ],
            what_to_verify=["Verify whether existing policy covers the vehicle variant."],
            questions_to_ask=[
                "Can you confirm whether the ₹34,500 insurance component provides coverage beyond the existing policy?"
            ],
            confidence=0.92,
            primary_amount=34500.0,
            supporting_amount=32000.0,
        )

        questions = CostReviewQuestionsService.generate_questions(
            contextual_findings=[finding],
        )
        assert len(questions) >= 1
        q = questions[0]
        assert q.classification == CostReviewClassification.DUPLICATED_OVERLAPPING
        assert q.suggested_action == "Ask whether existing coverage already covers the same area."
        assert q.amount_involved == 34500.0
        assert q.document_id == doc_id1
        assert "beyond the existing policy" in q.question

        msg = CostReviewQuestionsService.generate_suggested_negotiation_message(
            questions=questions,
            contextual_findings=[finding],
        )
        assert "existing policy" in msg.lower() or "Insurance Coverage Overlap" in msg

    # ── S. Zetran Regression ──
    def test_s_zetran_regression(self):
        item = LineItem(
            item_id=uuid4(),
            description=_make_field("description", "Boat Rockers 510"),
            mrp=_make_field("mrp", 3990.0),
            unit_price=_make_field("unit_price", 1299.0),
            discount=_make_field("discount", 2691.0),
            total_price=_make_field("total_price", 1299.0),
            quantity=_make_field("quantity", 1.0),
        )
        doc = StructuredFinancialDocument(
            document_id=uuid4(),
            user_id=uuid4(),
            document_type=DocumentClassification.INVOICE,
            line_items=[item],
            total_amount=_make_field("total_amount", 1299.0),
        )
        check = ValidationCheck(
            validation_id=uuid4(),
            check_code="LINE_ITEM_EXTENSION_MATCH",
            status=ValidationStatus.FAIL,
            input_field_ids=[item.item_id],
            message="Line item arithmetic extension mismatch for Boat Rockers 510.",
            severity=ValidationSeverity.WARNING,
        )

        questions = CostReviewQuestionsService.generate_questions(
            document=doc,
            validation_checks=[check],
        )
        assert len(questions) >= 1
        q = questions[0]
        assert "Boat Rockers 510" in q.question
        assert q.classification == CostReviewClassification.INCONSISTENT
        assert q.suggested_action == "Ask the provider to explain/reconcile the difference."

    # ── T. Vehicle Quotation Regression ──
    def test_t_vehicle_quotation_regression(self):
        c_base = _make_component_with_state(
            "Ex-showroom", 1149900.0, ComponentCategory.EX_SHOWROOM_PRICE
        )
        c_ins = _make_component_with_state("Insurance", 34500.0, ComponentCategory.INSURANCE)
        c_war = _make_component_with_state(
            "Extended Warranty", 24000.0, ComponentCategory.EXTENDED_WARRANTY
        )
        c_hnd = _make_component_with_state(
            "Handling Charges", 8500.0, ComponentCategory.HANDLING_FEE
        )

        doc = StructuredFinancialDocument(
            document_id=uuid4(),
            user_id=uuid4(),
            document_type=DocumentClassification.QUOTATION,
            cost_breakdown=[c_base, c_ins, c_war, c_hnd],
            total_amount=_make_field("total_amount", 1216900.0),
        )

        aggregator = ResultAggregatorService()
        result = aggregator.compile_result(
            document_id=doc.document_id,
            user_id=doc.user_id,
            document=doc,
            reasoning_claims=[],
            validation_checks=[],
        )

        assert len(result.smart_questions) >= 3
        assert result.suggested_negotiation_message is not None
        assert "Extended Warranty" in result.suggested_negotiation_message
        assert "Handling Charges" in result.suggested_negotiation_message
        assert "Insurance" in result.suggested_negotiation_message

    # ── U. Phase 2 Cross-Document Regression ──
    def test_u_phase2_cross_document_regression(self):
        c_ins = _make_component_with_state("Insurance", 34500.0, ComponentCategory.INSURANCE)
        doc = StructuredFinancialDocument(
            document_id=uuid4(),
            user_id=uuid4(),
            document_type=DocumentClassification.QUOTATION,
            cost_breakdown=[c_ins],
            total_amount=_make_field("total_amount", 34500.0),
        )

        finding = ContextualFinding(
            finding_id=uuid4(),
            finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
            title="Insurance",
            description="Potential overlap with existing insurance policy.",
            primary_evidence=[
                ContextualEvidence(
                    document_role="primary",
                    document_id=doc.document_id,
                    source_document_type="quotation",
                    raw_text="Insurance: ₹34,500",
                    amount=34500.0,
                )
            ],
            confidence=0.90,
            primary_amount=34500.0,
        )

        aggregator = ResultAggregatorService()
        result = aggregator.compile_result(
            document_id=doc.document_id,
            user_id=doc.user_id,
            document=doc,
            reasoning_claims=[],
            validation_checks=[],
            contextual_findings=[finding],
        )

        overlap_qs = [
            q
            for q in result.smart_questions
            if q.classification == CostReviewClassification.DUPLICATED_OVERLAPPING
        ]
        assert len(overlap_qs) >= 1
        assert (
            overlap_qs[0].suggested_action
            == "Ask whether existing coverage already covers the same area."
        )
