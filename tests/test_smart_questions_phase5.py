"""Phase 5 Test Suite: Smart Cost-Reduction Questions.

Validates that:
1. Every question includes:
   - question
   - reason
   - related_charge
   - amount_involved
   - potential_impact
   - evidence_source
   - confidence
2. Practical questions are generated for:
   - Extended Warranty (₹24,000)
   - Accessories / Accessory Package (₹35,000)
   - Insurance (₹34,500) — without asserting legal rights
   - Handling / Logistics Fee (₹8,000)
   - Dealer Package (₹15,000)
   - Duplicate-looking charges
   - Subtotal / arithmetic discrepancies (e.g. ₹6)
   - Unclear offers / discounts (₹50,000)
3. Negative guardrails:
   - No generic questions ("Can you give me a discount?")
   - Every question connected to an actual document finding
   - Strictly neutral, non-negotiating discovery tone
4. Ranking:
   - Transparent measurable ordering based on amount, uncertainty, potential impact, duplication risk, and optionality.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from before_you_pay.models.analysis import (
    SmartCostReductionQuestion,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
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
from before_you_pay.services.extra_cost_analysis import (
    ExtraCostAnalysisService,
)
from before_you_pay.services.smart_questions import SmartCostReductionQuestionsService


def _make_component(
    name: str,
    amount: float,
    category: ComponentCategory,
    opt_status: OptionalityStatus = OptionalityStatus.UNCLEAR,
    evidence: str | None = None,
) -> FinancialComponent:
    """Helper to construct a valid FinancialComponent."""
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
        evidence=evidence or f"{name} ₹{amount:,.0f}",
        source_ocr_line=f"{name} ₹{amount:,.0f}",
        bounding_box=bbox,
        page=1,
    )


class TestExtendedWarrantyQuestion:
    """Test question generation for Extended Warranty (₹24,000 example)."""

    def test_extended_warranty_question_formulation(self) -> None:
        comp = _make_component(
            "Extended Warranty",
            24000.0,
            ComponentCategory.EXTENDED_WARRANTY,
            OptionalityStatus.POTENTIALLY_OPTIONAL,
            evidence="Quotation line: 'Extended Warranty — ₹24,000'",
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "warranty" in q.question.lower())

        # 1. Question phrasing
        assert "24,000" in q.question
        assert "extended warranty" in q.question.lower()
        assert "optional" in q.question.lower()

        # 2. Reason
        assert (
            "lists warranty as a separate charge" in q.reason.lower()
            or "separate" in q.reason.lower()
        )

        # 3. Related charge
        assert "warranty" in q.related_charge.lower()

        # 4. Amount involved
        assert q.amount_involved == 24000.0

        # 5. Potential impact
        assert "24,000" in q.potential_impact
        assert "optional" in q.potential_impact.lower()

        # 6. Evidence source
        assert "Extended Warranty" in q.evidence_source

        # 7. Confidence
        assert q.confidence >= 0.90


class TestAccessoriesQuestion:
    """Test question generation for Accessories (₹35,000 example)."""

    def test_accessories_package_question_formulation(self) -> None:
        comp = _make_component(
            "Accessories Package",
            35000.0,
            ComponentCategory.ACCESSORY_PACKAGE,
            OptionalityStatus.CONFIRMED_OPTIONAL,
            evidence="Quotation line: 'Accessories Package — ₹35,000'",
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "accessories" in q.question.lower())

        assert "35,000" in q.question
        assert "included" in q.question.lower()
        assert (
            "remove individual" in q.question.lower()
            or "individual accessories" in q.question.lower()
        )
        assert q.amount_involved == 35000.0
        assert "35,000" in q.potential_impact


class TestInsuranceQuestion:
    """Test insurance inquiry (₹34,500 example) with strict non-accusatory guardrails."""

    def test_insurance_inquiry_does_not_assert_legal_rights(self) -> None:
        comp = _make_component(
            "Comprehensive Insurance",
            34500.0,
            ComponentCategory.INSURANCE,
            OptionalityStatus.POTENTIALLY_OPTIONAL,
            evidence="Quotation line: 'Comprehensive Insurance — ₹34,500'",
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "insurance" in q.question.lower())

        # Exact expected prompt phrasing
        assert (
            "mandatory from the dealer" in q.question.lower()
            or "choose another insurer" in q.question.lower()
        )
        assert (
            "Is this insurance package mandatory from the dealer, or can I choose another insurer?"
            in q.question
        )

        # STRICT GUARDRAIL: Must NOT state the user has a legal right to choose another insurer
        assert "you have a legal right" not in q.reason.lower()
        assert "law requires" not in q.reason.lower()
        assert "illegal" not in q.reason.lower()
        assert "court" not in q.reason.lower()

        assert q.amount_involved == 34500.0


class TestHandlingFeeQuestion:
    """Test handling fee inquiry (₹8,000 example)."""

    def test_handling_fee_question_formulation(self) -> None:
        comp = _make_component(
            "Handling Charges",
            8000.0,
            ComponentCategory.HANDLING_FEE,
            OptionalityStatus.POTENTIALLY_OPTIONAL,
            evidence="Quotation line: 'Handling Charges — ₹8,000'",
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "handling" in q.question.lower())

        assert "8,000" in q.question
        assert "cover" in q.question.lower()
        assert "required" in q.question.lower()
        assert q.amount_involved == 8000.0
        assert "8,000" in q.potential_impact


class TestDealerPackageQuestion:
    """Test dealer package inquiry (₹15,000 example)."""

    def test_dealer_package_question_formulation(self) -> None:
        comp = _make_component(
            "Dealer Essential Package",
            15000.0,
            ComponentCategory.DEALER_PACKAGE,
            OptionalityStatus.POTENTIALLY_OPTIONAL,
            evidence="Quotation line: 'Dealer Essential Package — ₹15,000'",
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(
            q
            for q in questions
            if "dealer" in q.question.lower() or "package" in q.question.lower()
        )

        assert "15,000" in q.question
        assert "included" in q.question.lower()
        assert "without this package" in q.question.lower()
        assert q.amount_involved == 15000.0
        assert "15,000" in q.potential_impact


class TestDuplicateChargesQuestion:
    """Test question generation for duplicate-looking charges."""

    def test_duplicate_charges_inquiry(self) -> None:
        comp1 = _make_component(
            "Basic Accessory Kit",
            8500.0,
            ComponentCategory.ACCESSORY_PACKAGE,
        )
        comp2 = _make_component(
            "Essential Accessories",
            6000.0,
            ComponentCategory.ACCESSORY_PACKAGE,
        )
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp1, comp2],
        )

        dup_q = [
            q
            for q in questions
            if "separately" in q.question.lower() or "both" in q.question.lower()
        ]
        assert len(dup_q) >= 1
        q = dup_q[0]

        assert "Basic Accessory Kit" in q.question or "Essential Accessories" in q.question
        assert (
            "charged separately" in q.question.lower() or "listed separately" in q.question.lower()
        )
        assert q.amount_involved in (6000.0, 8500.0)


class TestArithmeticDiscrepancyQuestion:
    """Test subtotal discrepancy inquiry (₹6 example)."""

    def test_subtotal_difference_question(self) -> None:
        check = ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_SUBTOTAL_MATCH",
            status=ValidationStatus.FAIL,
            input_field_ids=[uuid4()],
            expected_value=1245000.0,
            calculated_value=1245006.0,
            absolute_delta=6.0,
            severity=ValidationSeverity.WARNING,
            message="Calculated subtotal ₹1,245,006 differs from stated subtotal ₹1,245,000 by difference of ₹6.",
        )
        questions = SmartCostReductionQuestionsService.generate_questions(
            validation_checks=[check],
        )

        assert len(questions) >= 1
        q = questions[0]

        assert "6" in q.question
        assert "subtotal" in q.question.lower()
        assert "difference" in q.question.lower()
        assert q.amount_involved == 6.0
        assert "6" in q.potential_impact
        assert "ARITHMETIC_SUBTOTAL_MATCH" in q.evidence_source


class TestUnclearOfferQuestion:
    """Test unclear offer/discount inquiry (₹50,000 example)."""

    def test_unclear_offer_question(self) -> None:
        comp = _make_component(
            "Special Consumer Offer",
            50000.0,
            ComponentCategory.OFFER,
            evidence="Quotation line: 'Special Consumer Offer: ₹50,000'",
        )
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "offer" in q.question.lower())

        assert "50,000" in q.question
        assert "already included" in q.question.lower()
        assert "applied separately" in q.question.lower()
        assert q.amount_involved == 50000.0


class TestFastagMarkupQuestion:
    """Test FASTag with markup (e.g. ₹600 vs official rate)."""

    def test_fastag_markup_question(self) -> None:
        comp = _make_component(
            "FASTag Fee",
            800.0,
            ComponentCategory.FASTAG,
        )
        eca = ExtraCostAnalysisService.analyze([comp])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 1
        q = next(q for q in questions if "fastag" in q.question.lower())

        assert "800" in q.question
        assert "breakdown" in q.question.lower()
        assert "security deposit" in q.question.lower()


class TestNoGenericQuestionsAllowed:
    """Ensure the system NEVER generates or permits generic questions like 'Can you give me a discount?'."""

    def test_generic_discount_question_rejected_by_model(self) -> None:
        with pytest.raises(ValueError, match="Generic questions like '.*' are prohibited"):
            SmartCostReductionQuestion(
                question="Can you give me a discount?",
                reason="Looking for price reduction.",
                related_charge="General Price",
                amount_involved=None,
                potential_impact="Unknown",
                evidence_source="None",
                confidence=0.5,
            )

    def test_accusatory_language_rejected_by_model(self) -> None:
        with pytest.raises(ValueError, match="prohibited language"):
            SmartCostReductionQuestion(
                question="Why is this scam charge included?",
                reason="Suspicious dealer fee.",
                related_charge="Scam Fee",
                amount_involved=500.0,
                potential_impact="Removal",
                evidence_source="Document",
                confidence=0.5,
            )


class TestRankingCriteria:
    """Validate transparent, measurable ranking without political or subjective bias."""

    def test_ranking_by_amount_and_impact(self) -> None:
        comp_small = _make_component("Small Fee", 500.0, ComponentCategory.OTHER_FEE)
        comp_large = _make_component(
            "Extended Warranty", 45000.0, ComponentCategory.EXTENDED_WARRANTY
        )
        comp_mid = _make_component("Accessories", 15000.0, ComponentCategory.ACCESSORY_PACKAGE)

        eca = ExtraCostAnalysisService.analyze([comp_small, comp_large, comp_mid])
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=[comp_small, comp_large, comp_mid],
            extra_cost_analysis=eca,
        )

        assert len(questions) >= 3
        # Large extended warranty must rank higher than small 500 fee
        warranty_q = next(q for q in questions if "warranty" in q.question.lower())
        small_q = next(q for q in questions if "small fee" in q.question.lower())

        assert warranty_q.priority_score > small_q.priority_score
        assert (
            questions[0].priority_score
            >= questions[1].priority_score
            >= questions[2].priority_score
        )

        # Verify transparent factors exist on each question
        for q in questions:
            assert "amount_factor" in q.ranking_factors
            assert "impact_factor" in q.ranking_factors
            assert "optionality_uncertainty_factor" in q.ranking_factors
            assert "duplication_risk_factor" in q.ranking_factors
            assert "general_uncertainty_factor" in q.ranking_factors


class TestFullRealisticQuotationScenario:
    """End-to-end integration test with full vehicle quotation."""

    def test_realistic_quotation_produces_all_required_questions(self) -> None:
        components = [
            _make_component("Ex-Showroom Price", 1149900.0, ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("Road Tax / RTO", 114990.0, ComponentCategory.ROAD_TAX),
            _make_component("TCS (1%)", 11499.0, ComponentCategory.TCS),
            _make_component("Comprehensive Insurance", 34500.0, ComponentCategory.INSURANCE),
            _make_component("Extended Warranty", 24000.0, ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Accessory Package", 35000.0, ComponentCategory.ACCESSORY_PACKAGE),
            _make_component("Handling Fee", 8000.0, ComponentCategory.HANDLING_FEE),
            _make_component("Dealer Package", 15000.0, ComponentCategory.DEALER_PACKAGE),
            _make_component("FASTag", 800.0, ComponentCategory.FASTAG),
            _make_component("Festive Consumer Offer", 50000.0, ComponentCategory.OFFER),
        ]
        subtotal_check = ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_SUBTOTAL_MATCH",
            status=ValidationStatus.FAIL,
            input_field_ids=[uuid4()],
            expected_value=1393689.0,
            calculated_value=1393695.0,
            absolute_delta=6.0,
            severity=ValidationSeverity.WARNING,
            message="Calculated sum ₹1,393,695 differs from stated subtotal ₹1,393,689 by difference of ₹6.",
        )

        eca = ExtraCostAnalysisService.analyze(components)
        questions = SmartCostReductionQuestionsService.generate_questions(
            cost_breakdown=components,
            extra_cost_analysis=eca,
            validation_checks=[subtotal_check],
        )

        # 1. Base price and statutory road tax / TCS MUST NOT have cost-reduction questions
        for q in questions:
            assert "ex-showroom" not in q.related_charge.lower()
            assert "tcs" not in q.related_charge.lower()

        # 2. Every single question has valid fields
        for q in questions:
            assert q.question and len(q.question) > 5
            assert q.reason and len(q.reason) > 5
            assert q.related_charge and len(q.related_charge) > 0
            assert q.potential_impact and len(q.potential_impact) > 0
            assert q.evidence_source and len(q.evidence_source) > 0
            assert 0.0 <= q.confidence <= 1.0
            assert q.priority_score >= 0.0

        # 3. Check presence of all key categories
        question_texts = " ".join(q.question for q in questions)
        assert "extended warranty" in question_texts.lower()
        assert "accessories" in question_texts.lower()
        assert "insurance" in question_texts.lower()
        assert "handling" in question_texts.lower()
        assert "dealer package" in question_texts.lower() or "dealer" in question_texts.lower()
        assert "6" in question_texts
        assert "offer" in question_texts.lower()
