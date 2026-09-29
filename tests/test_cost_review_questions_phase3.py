"""Comprehensive Test Suite for Phase 3: Cost Review Questions.

Validates:
1. For each relevant charge, the review classification is identified:
   - potentially optional
   - potentially negotiable
   - unexplained
   - duplicated/overlapping
   - alternative available
   - inconsistent
   - requires verification
2. Generates 1–3 specific questions using actual document evidence.
3. Specific example questions:
   - Insurance: "Can I choose my own insurer or insurance policy?"
   - Extended Warranty: "Is the ₹24,000 extended warranty package optional?"
   - Accessories: "Are these accessories required for delivery?"
   - Dealer charge: "What service does this ₹X charge cover, and is it mandatory?"
   - Discrepancy: "The listed components total ₹X, but the stated subtotal is ₹Y. Which amount is correct?"
4. Questions must reference actual extracted values when available.
5. Negative guardrails:
   - No generic discount questions ("Can you give me a discount?")
   - No promises of savings ("You will save", "You can save", "guaranteed savings")
   - Uses "Potential amount to review" framing
   - Never says "You don't need this" or "You can definitely remove this"
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from before_you_pay.models.analysis import (
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.models.cost_review import (
    CostReviewClassification,
    CostReviewQuestion,
)
from before_you_pay.models.document import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OptionalityStatus,
)
from before_you_pay.services.cost_review_questions import CostReviewQuestionsService


def _make_component(
    name: str,
    amount: float,
    category: ComponentCategory,
    opt_status: OptionalityStatus = OptionalityStatus.UNCLEAR,
    evidence: str | None = None,
) -> FinancialComponent:
    """Helper to construct a valid FinancialComponent with evidence."""
    doc_id = uuid4()
    p_id = uuid4()
    line_id = uuid4()
    prov = FieldProvenance(
        document_id=doc_id,
        page_id=p_id,
        ocr_line_ids=[line_id],
        raw_text=f"{name} ₹{amount:,.0f}",
    )
    amt_field = ExtractedField(
        field_key="component_amount",
        normalized_value=amount,
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
        category=category,
        charge_nature=ChargeNature.CHARGE,
        optionality_status=opt_status,
        confidence=0.95,
        evidence=evidence or f"Quotation line: '{name} — ₹{amount:,.0f}'",
        source_ocr_line=f"{name} ₹{amount:,.0f}",
        bounding_box=bbox,
        page=1,
    )


class TestInsuranceCostReviewQuestions:
    """Insurance review questions: alternative available, 1-3 questions, exact prompt example."""

    def test_insurance_classification_and_questions(self) -> None:
        comp = _make_component(
            "Insurance",
            34500.0,
            ComponentCategory.INSURANCE,
            evidence="Quotation line: 'Insurance — ₹34,500'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])

        ins_questions = [q for q in questions if "insurance" in q.related_charge.lower()]
        # 1-3 specific questions generated
        assert 1 <= len(ins_questions) <= 3

        # Primary question matches prompt example
        primary = ins_questions[0]
        assert primary.classification == CostReviewClassification.ALTERNATIVE_AVAILABLE
        assert primary.question == "Can I choose my own insurer or insurance policy?"
        assert primary.amount_involved == 34500.0
        assert primary.potential_amount_to_review == 34500.0
        assert "Potential amount to review" in primary.potential_impact
        assert primary.evidence_source == "Quotation line: 'Insurance — ₹34,500'"

        # Second question references actual extracted value
        secondary = ins_questions[1]
        assert "₹34,500" in secondary.question
        assert "mandatory from the dealer" in secondary.question

        # No savings promises or generic requests
        for q in ins_questions:
            assert "you can save" not in q.potential_impact.lower()
            assert "you will save" not in q.potential_impact.lower()
            assert "Potential amount to review" in q.potential_impact


class TestExtendedWarrantyCostReviewQuestions:
    """Extended Warranty review questions: potentially optional, actual extracted value."""

    def test_extended_warranty_classification_and_questions(self) -> None:
        comp = _make_component(
            "Extended Warranty",
            24000.0,
            ComponentCategory.EXTENDED_WARRANTY,
            evidence="Quotation line: 'Extended Warranty — ₹24,000'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])

        ew_questions = [q for q in questions if "warranty" in q.related_charge.lower()]
        assert 1 <= len(ew_questions) <= 3

        primary = ew_questions[0]
        assert primary.classification == CostReviewClassification.POTENTIALLY_OPTIONAL
        # Exact prompt example with extracted value
        assert primary.question == "Is the ₹24,000 extended warranty package optional?"
        assert primary.amount_involved == 24000.0
        assert primary.potential_amount_to_review == 24000.0
        assert "Potential amount to review" in primary.potential_impact
        assert "24,000" in primary.potential_impact
        assert primary.evidence_source == "Quotation line: 'Extended Warranty — ₹24,000'"

        # Follow-up question references vehicle purchase independence
        secondary = ew_questions[1]
        assert "₹24,000" in secondary.question
        assert "purchased without" in secondary.question.lower()


class TestAccessoriesCostReviewQuestions:
    """Accessories review questions: potentially optional, delivery requirement inquiry."""

    def test_accessories_classification_and_questions(self) -> None:
        comp = _make_component(
            "Accessories Package",
            35000.0,
            ComponentCategory.ACCESSORY_PACKAGE,
            evidence="Quotation line: 'Accessories Package — ₹35,000'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])

        acc_questions = [q for q in questions if "accessor" in q.related_charge.lower()]
        assert 1 <= len(acc_questions) <= 3

        primary = acc_questions[0]
        assert primary.classification == CostReviewClassification.POTENTIALLY_OPTIONAL
        # Exact prompt example
        assert primary.question == "Are these accessories required for delivery?"
        assert primary.amount_involved == 35000.0
        assert "Potential amount to review" in primary.potential_impact

        # Secondary question references package breakdown and individual item removal
        secondary = acc_questions[1]
        assert "₹35,000" in secondary.question
        assert "remove individual accessories" in secondary.question.lower()


class TestDealerChargeCostReviewQuestions:
    """Dealer charge review questions: potentially negotiable, actual extracted value."""

    def test_dealer_charge_classification_and_questions(self) -> None:
        comp = _make_component(
            "Dealer Handling Charge",
            15000.0,
            ComponentCategory.HANDLING_FEE,
            evidence="Quotation line: 'Dealer Handling Charge — ₹15,000'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])

        dealer_questions = [q for q in questions if "handling" in q.related_charge.lower()]
        assert 1 <= len(dealer_questions) <= 3

        primary = dealer_questions[0]
        assert primary.classification == CostReviewClassification.POTENTIALLY_NEGOTIABLE
        # Exact prompt example referencing actual extracted value
        assert (
            primary.question == "What service does this ₹15,000 charge cover, and is it mandatory?"
        )
        assert primary.amount_involved == 15000.0
        assert primary.potential_amount_to_review == 15000.0
        assert "Potential amount to review" in primary.potential_impact
        assert primary.requires_verification is True

        # Secondary question checks negotiability under transport guidelines
        secondary = dealer_questions[1]
        assert "₹15,000" in secondary.question
        assert (
            "negotiable" in secondary.question.lower() or "waivable" in secondary.question.lower()
        )


class TestDiscrepancyCostReviewQuestions:
    """Discrepancy review questions: inconsistent, actual extracted values."""

    def test_discrepancy_classification_and_questions(self) -> None:
        c_base = _make_component(
            "Ex-Showroom Price", 1149900.0, ComponentCategory.EX_SHOWROOM_PRICE
        )
        c_tcs = _make_component("TCS", 11499.0, ComponentCategory.TCS)
        c_subtotal = _make_component("Stated Subtotal", 1158399.0, ComponentCategory.SUBTOTAL)

        f_id = uuid4()
        check = ValidationCheck(
            validation_id=uuid4(),
            check_code="SUBTOTAL_RECONCILIATION_MISMATCH",
            status=ValidationStatus.FAIL,
            severity=ValidationSeverity.CRITICAL,
            message="Sum of listed charges (₹1,161,399) does not match stated subtotal (₹1,158,399), difference of ₹3,000.",
            absolute_delta=3000.0,
            input_field_ids=[f_id],
        )

        questions = CostReviewQuestionsService.generate_questions(
            cost_breakdown=[c_base, c_tcs, c_subtotal],
            validation_checks=[check],
        )

        disc_questions = [
            q for q in questions if q.classification == CostReviewClassification.INCONSISTENT
        ]
        assert 1 <= len(disc_questions) <= 3

        primary = disc_questions[0]
        assert primary.classification == CostReviewClassification.INCONSISTENT
        # References actual extracted values
        assert "total ₹" in primary.question
        assert "stated subtotal is ₹" in primary.question
        assert "Which amount is correct?" in primary.question
        assert primary.amount_involved == 3000.0
        assert primary.potential_amount_to_review == 3000.0
        assert "Potential amount to review" in primary.potential_impact


class TestDuplicatedOverlappingQuestions:
    """Duplicated/overlapping charges inquiry."""

    def test_duplicate_charges_classification_and_questions(self) -> None:
        c1 = _make_component("Essential Accessories", 8000.0, ComponentCategory.ACCESSORY)
        c2 = _make_component("Basic Accessory Kit", 8000.0, ComponentCategory.ACCESSORY)

        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[c1, c2])

        dup_questions = [
            q
            for q in questions
            if q.classification == CostReviewClassification.DUPLICATED_OVERLAPPING
        ]
        assert len(dup_questions) >= 1
        q = dup_questions[0]
        assert "Essential Accessories" in q.question
        assert "Basic Accessory Kit" in q.question
        assert "separately" in q.question
        assert q.amount_involved == 8000.0
        assert "Potential amount to review" in q.potential_impact


class TestUnexplainedChargeQuestions:
    """Unexplained / Other Fee charge inquiry."""

    def test_unexplained_charge_classification_and_questions(self) -> None:
        comp = _make_component(
            "Administrative Fee",
            5000.0,
            ComponentCategory.OTHER_FEE,
            evidence="Quotation line: 'Administrative Fee — ₹5,000'",
        )
        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])

        unexplained_questions = [
            q for q in questions if q.classification == CostReviewClassification.UNEXPLAINED
        ]
        assert len(unexplained_questions) >= 1
        q = unexplained_questions[0]
        assert "₹5,000" in q.question
        assert "What service does this ₹5,000 charge cover, and is it mandatory?" in q.question
        assert q.amount_involved == 5000.0
        assert "Potential amount to review" in q.potential_impact


class TestNegativeGuardrails:
    """Strict adherence to non-generic, non-promising, evidence-based rules."""

    def test_generic_discount_question_strictly_forbidden(self) -> None:
        with pytest.raises(ValueError, match="Generic discount questions"):
            CostReviewQuestion(
                classification=CostReviewClassification.POTENTIALLY_NEGOTIABLE,
                question="Can you give me a discount on this vehicle?",
                reason="Trying to save money.",
                related_charge="Ex-showroom",
                potential_impact="Potential amount to review: lower price.",
                evidence_source="Document line",
                confidence=0.5,
            )

    def test_promising_savings_strictly_forbidden(self) -> None:
        with pytest.raises(ValueError, match="violates savings promise rule"):
            CostReviewQuestion(
                classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                question="Is the warranty optional?",
                reason="Listed separately.",
                related_charge="Warranty",
                potential_impact="You will save ₹24,000 by removing this.",
                evidence_source="Document line",
                confidence=0.9,
            )

    def test_you_can_save_strictly_forbidden(self) -> None:
        with pytest.raises(ValueError, match="violates savings promise rule"):
            CostReviewQuestion(
                classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                question="Is the accessory package optional?",
                reason="Listed separately.",
                related_charge="Accessories",
                potential_impact="You can save ₹35,000 if declined.",
                evidence_source="Document line",
                confidence=0.9,
            )

    def test_you_do_not_need_this_strictly_forbidden(self) -> None:
        with pytest.raises(ValueError, match="violates savings promise rule"):
            CostReviewQuestion(
                classification=CostReviewClassification.POTENTIALLY_OPTIONAL,
                question="Can this charge be removed?",
                reason="You don't need this service package.",
                related_charge="Service Package",
                potential_impact="Potential amount to review: ₹15,000.",
                evidence_source="Document line",
                confidence=0.9,
            )


class TestFullRealisticQuotationReviewQuestions:
    """Verifies complete quotation producing all evidence-grounded review questions."""

    def test_realistic_quotation_produces_all_required_questions(self) -> None:
        c_base = _make_component("Ex-showroom", 1149900.0, ComponentCategory.EX_SHOWROOM_PRICE)
        c_tcs = _make_component("TCS", 11499.0, ComponentCategory.TCS)
        c_reg = _make_component("Registration", 76250.0, ComponentCategory.REGISTRATION)
        c_ins = _make_component("Insurance", 34500.0, ComponentCategory.INSURANCE)
        c_ew = _make_component("Extended Warranty", 24000.0, ComponentCategory.EXTENDED_WARRANTY)
        c_acc = _make_component("Accessories", 35000.0, ComponentCategory.ACCESSORY_PACKAGE)
        c_handling = _make_component(
            "Dealer Handling Charge", 8000.0, ComponentCategory.HANDLING_FEE
        )
        c_offer = _make_component("Offer", 20000.0, ComponentCategory.OFFER)

        questions = CostReviewQuestionsService.generate_questions(
            cost_breakdown=[c_base, c_tcs, c_reg, c_ins, c_ew, c_acc, c_handling, c_offer]
        )

        assert len(questions) >= 5

        # Classifications present
        classifications = {q.classification for q in questions}
        assert CostReviewClassification.ALTERNATIVE_AVAILABLE in classifications
        assert CostReviewClassification.POTENTIALLY_OPTIONAL in classifications
        assert CostReviewClassification.POTENTIALLY_NEGOTIABLE in classifications
        assert CostReviewClassification.REQUIRES_VERIFICATION in classifications

        # Questions reference actual extracted values
        all_questions_text = " ".join(q.question for q in questions)
        assert "24,000" in all_questions_text  # Warranty
        assert "8,000" in all_questions_text  # Handling
        assert "Can I choose my own insurer or insurance policy?" in all_questions_text
        assert "Are these accessories required for delivery?" in all_questions_text

        # Every question has Potential amount to review and evidence
        for q in questions:
            assert "Potential amount to review" in q.potential_impact
            assert q.evidence_source != ""
            assert q.confidence > 0.0

        # SmartCostReductionQuestion conversion compatibility
        smart_questions = CostReviewQuestionsService.generate_smart_questions(
            cost_breakdown=[c_base, c_tcs, c_reg, c_ins, c_ew, c_acc, c_handling, c_offer]
        )
        assert len(smart_questions) == len(questions)
        for sq in smart_questions:
            assert sq.classification in [c.value for c in CostReviewClassification]
            assert "Potential amount to review" in sq.potential_impact


class TestAllSevenClassificationsCovered:
    """Verifies all 7 required Phase 3 classifications are tested and supported."""

    def test_all_seven_classifications_exist(self) -> None:
        expected = {
            "potentially optional",
            "potentially negotiable",
            "unexplained",
            "duplicated/overlapping",
            "alternative available",
            "inconsistent",
            "requires verification",
        }
        actual = {c.value for c in CostReviewClassification}
        assert actual == expected

    def test_charge_produces_between_one_and_three_questions(self) -> None:
        charges = [
            _make_component("Insurance", 34500.0, ComponentCategory.INSURANCE),
            _make_component("Extended Warranty", 24000.0, ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Accessories", 35000.0, ComponentCategory.ACCESSORY_PACKAGE),
            _make_component("Dealer Handling Charge", 15000.0, ComponentCategory.HANDLING_FEE),
            _make_component("Registration", 76250.0, ComponentCategory.REGISTRATION),
            _make_component("Admin Charge", 5000.0, ComponentCategory.OTHER_FEE),
            _make_component("Festival Offer", 10000.0, ComponentCategory.OFFER),
        ]

        for comp in charges:
            questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[comp])
            comp_questions = [q for q in questions if q.related_charge.lower() == comp.name.lower()]
            assert 1 <= len(comp_questions) <= 3, (
                f"Component '{comp.name}' produced {len(comp_questions)} questions, expected 1 to 3."
            )
            for q in comp_questions:
                assert q.classification in list(CostReviewClassification)
                assert "Potential amount to review" in q.potential_impact
                assert "you can save" not in q.potential_impact.lower()
                assert "you will save" not in q.potential_impact.lower()
