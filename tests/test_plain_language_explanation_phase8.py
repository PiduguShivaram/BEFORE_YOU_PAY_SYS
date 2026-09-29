"""Tests for Phase 8: Plain-Language Financial Explanation.

Covers:
- Concise plain-language sentence structure
- Vehicle quotation example with ex-showroom, insurance, registration, warranty, offers, and arithmetic discrepancy
- Evidence-grounded missing item handling: "not stated", "unclear", "requires verification"
- Practical bulleted clarification items: "Before paying, clarify these items:"
- Integration into ResultAggregatorService
"""

from uuid import uuid4

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
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OptionalityStatus,
    StructuredFinancialDocument,
)
from before_you_pay.services.plain_language_explanation import PlainLanguageExplanationService
from before_you_pay.services.result import ResultAggregatorService


def _make_field(key: str, val: float, text: str) -> ExtractedField:
    doc_id = uuid4()
    return ExtractedField(
        field_key=key,
        normalized_value=val,
        unit_or_currency="INR",
        confidence=0.98,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=uuid4(),
            ocr_line_ids=[uuid4()],
            bounding_box=BoundingBox(x=0.1, y=0.2, width=0.8, height=0.05),
            raw_text=text,
        ),
    )


def _make_component(
    name: str,
    amount: float,
    category: ComponentCategory,
    optionality: OptionalityStatus = OptionalityStatus.UNCLEAR,
    nature: ChargeNature = ChargeNature.CHARGE,
) -> FinancialComponent:
    return FinancialComponent(
        name=name,
        amount=_make_field("amount", amount, f"{name}: ₹{amount:,.0f}"),
        category=category,
        optionality_status=optionality,
        charge_nature=nature,
        charge_or_deduction=nature.value,
        evidence=f"{name}: ₹{amount:,.0f}",
    )


class TestPlainLanguageExplanation:
    """Phase 8 specification test suite."""

    def test_complete_vehicle_quotation_explanation(self):
        """Matches the complete vehicle quotation scenario with ex-showroom, insurance, registration, warranty, offers, and a ₹6 discrepancy."""
        doc_id = uuid4()
        user_id = uuid4()

        comps = [
            _make_component(
                "Ex-showroom price",
                1149900.0,
                ComponentCategory.EX_SHOWROOM_PRICE,
                OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "Insurance",
                34500.0,
                ComponentCategory.INSURANCE,
                OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "Registration / R.C.",
                76250.0,
                ComponentCategory.REGISTRATION,
                OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "Warranty",
                24000.0,
                ComponentCategory.WARRANTY,
                OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            _make_component(
                "TCS", 11499.0, ComponentCategory.TCS, OptionalityStatus.CONFIRMED_MANDATORY
            ),
            _make_component(
                "Temporary registration / HSRP",
                2250.0,
                ComponentCategory.HSRP,
                OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            # Offers totaling ₹70,000
            _make_component(
                "Offer",
                20000.0,
                ComponentCategory.OFFER,
                OptionalityStatus.CONFIRMED_OPTIONAL,
                nature=ChargeNature.DEDUCTION,
            ),
            _make_component(
                "Extra offer",
                50000.0,
                ComponentCategory.OFFER,
                OptionalityStatus.CONFIRMED_OPTIONAL,
                nature=ChargeNature.DEDUCTION,
            ),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            document_type=DocumentClassification.QUOTATION,
            total_amount=_make_field("total_amount", 1228399.0, "Final Quoted Price: ₹12,28,399"),
            subtotal=_make_field("subtotal", 1298399.0, "Total before offers: ₹12,98,399"),
            cost_breakdown=comps,
        )

        # Listed charges sum: 1149900 + 34500 + 76250 + 24000 + 11499 + 2250 = 1298405
        # Stated subtotal: 1298399
        # Discrepancy: ₹6
        val_checks = [
            ValidationCheck(
                validation_id=uuid4(),
                check_code="QUOTATION_SUBTOTAL_CONSISTENCY",
                status=ValidationStatus.FAIL,
                input_field_ids=[doc.subtotal.field_id],
                expected_value=1298399.0,
                calculated_value=1298405.0,
                absolute_delta=6.0,
                severity=ValidationSeverity.WARNING,
                message="Component reconciliation discrepancy: difference of ₹6.",
            )
        ]

        questions = [
            SmartCostReductionQuestion(
                question="Is the ₹24,000 extended warranty optional?",
                reason="Warranty is listed as a separate charge.",
                related_charge="Warranty",
                amount_involved=24000.0,
                potential_impact="Up to ₹24,000 if removable.",
                evidence_source="Quotation line 'Warranty — ₹24,000'",
                confidence=0.95,
            ),
            SmartCostReductionQuestion(
                question="Is this insurance package mandatory from the dealer, or can I obtain external quotes?",
                reason="Motor insurance is statutory, but dealer sourcing is optional.",
                related_charge="Insurance",
                amount_involved=34500.0,
                potential_impact="Price difference if lower external quote accepted.",
                evidence_source="Quotation line 'Insurance — ₹34,500'",
                confidence=0.95,
            ),
        ]

        explanation = PlainLanguageExplanationService.generate_explanation(
            document=doc,
            validation_checks=val_checks,
            smart_questions=questions,
        )

        assert (
            "You're being quoted ₹12,28,399 for the vehicle." in explanation.quoted_amount_sentence
        )
        assert "₹11,49,900 is the ex-showroom price." in explanation.base_price_sentence
        assert any(
            "An additional ₹34,500 is listed for insurance." in s
            for s in explanation.charge_breakdown_sentences
        )
        assert any(
            "₹76,250 is listed for registration." in s
            for s in explanation.charge_breakdown_sentences
        )
        assert any(
            "₹24,000 is listed for warranty." in s for s in explanation.charge_breakdown_sentences
        )
        assert explanation.offers_sentence == "₹70,000 in offers reduce the stated subtotal."
        assert (
            explanation.discrepancy_sentence
            == "One ₹6 discrepancy exists between the listed charges and the stated subtotal."
        )

        assert explanation.clarification_heading == "Before paying, clarify these items:"
        assert len(explanation.clarification_items) >= 2
        assert any("₹6 discrepancy" in item for item in explanation.clarification_items)
        assert any("warranty optional" in item.lower() for item in explanation.clarification_items)

        # Full text verification
        assert "You're being quoted ₹12,28,399 for the vehicle." in explanation.full_explanation
        assert "One ₹6 discrepancy exists" in explanation.full_explanation
        assert "Before paying, clarify these items:" in explanation.full_explanation

    def test_missing_information_uses_strict_fallback(self):
        """When components are missing, states 'not stated' or 'requires verification' instead of guessing."""
        doc_id = uuid4()
        user_id = uuid4()

        comps = [
            _make_component(
                "Handling Fee",
                8500.0,
                ComponentCategory.HANDLING_FEE,
                OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            document_type=DocumentClassification.QUOTATION,
            total_amount=_make_field("total_amount", 900000.0, "Total: ₹9,00,000"),
            cost_breakdown=comps,
        )

        explanation = PlainLanguageExplanationService.generate_explanation(doc)

        # Base price and major statutory charges are missing
        assert "The ex-showroom price is not stated." in explanation.base_price_sentence
        assert "Insurance is not stated." in explanation.charge_breakdown_sentences
        assert "Registration is not stated." in explanation.charge_breakdown_sentences
        assert any("requires verification" in s for s in explanation.charge_breakdown_sentences)

        # Clarification points flag the missing items
        assert any("insurance" in item.lower() for item in explanation.clarification_items)
        assert any("registration" in item.lower() for item in explanation.clarification_items)

    def test_no_discrepancy_when_totals_reconcile(self):
        """When math reconciles, discrepancy_sentence is None."""
        doc_id = uuid4()
        user_id = uuid4()

        comps = [
            _make_component("Ex-showroom price", 1000000.0, ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("Insurance", 30000.0, ComponentCategory.INSURANCE),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            total_amount=_make_field("total_amount", 1030000.0, "Total: ₹10,30,000"),
            subtotal=_make_field("subtotal", 1030000.0, "Subtotal: ₹10,30,000"),
            cost_breakdown=comps,
        )

        val_checks = [
            ValidationCheck(
                validation_id=uuid4(),
                check_code="QUOTATION_SUBTOTAL_CONSISTENCY",
                status=ValidationStatus.PASS,
                input_field_ids=[doc.subtotal.field_id],
                expected_value=1030000.0,
                calculated_value=1030000.0,
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message="Subtotal matches.",
            )
        ]

        explanation = PlainLanguageExplanationService.generate_explanation(
            document=doc,
            validation_checks=val_checks,
        )

        assert explanation.discrepancy_sentence is None

    def test_result_aggregator_service_populates_explanation(self):
        """ResultAggregatorService compiles plain_language_explanation in FinalDecisionSupportResult."""
        doc_id = uuid4()
        user_id = uuid4()

        comps = [
            _make_component("Ex-showroom price", 800000.0, ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("Insurance", 25000.0, ComponentCategory.INSURANCE),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            total_amount=_make_field("total_amount", 825000.0, "Total: ₹8,25,000"),
            cost_breakdown=comps,
        )

        aggregator = ResultAggregatorService()
        result = aggregator.compile_result(
            document_id=doc_id,
            user_id=user_id,
            document=doc,
            reasoning_claims=[],
            validation_checks=[],
        )

        assert result.plain_language_explanation is not None
        assert (
            "You're being quoted ₹8,25,000 for the vehicle."
            in result.plain_language_explanation.quoted_amount_sentence
        )
        assert (
            "₹8,00,000 is the ex-showroom price."
            in result.plain_language_explanation.base_price_sentence
        )
        assert (
            result.plain_language_explanation.clarification_heading
            == "Before paying, clarify these items:"
        )
