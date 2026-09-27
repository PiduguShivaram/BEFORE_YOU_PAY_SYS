"""Phase 4: Comprehensive Test Suite for Extra Cost and Cost-Reduction Analysis.

Verifies:
1. Correct identification and flagging of charges deserving scrutiny.
2. Neutral language enforcement — never "unnecessary", always evidence-based.
3. Potential saving calculations only when mathematically meaningful.
4. Duplicate charge detection.
5. Bundled package question generation.
6. Base price / statutory taxes NEVER flagged.
7. Complete ExtraCostFlag field population.
8. Reduction summary correctness.
"""

from uuid import uuid4

import pytest

from before_you_pay.models import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OcrLine,
    OcrPage,
    OcrResult,
)
from before_you_pay.services.extra_cost_analysis import (
    ExtraCostAnalysisService,
    ExtraCostFlagType,
)


def _make_component(
    name: str,
    amount: float,
    category: ComponentCategory = ComponentCategory.UNKNOWN,
    charge_nature: ChargeNature = ChargeNature.CHARGE,
    evidence: str | None = None,
) -> FinancialComponent:
    """Create a FinancialComponent for testing."""
    doc_id = uuid4()
    page_id = uuid4()
    line_id = uuid4()
    bbox = BoundingBox(
        x=0.08, y=0.20, width=0.82, height=0.035,
        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
    )
    amt_field = ExtractedField(
        field_id=uuid4(),
        field_key="amount",
        normalized_value=amount,
        unit_or_currency="INR",
        confidence=0.96,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[line_id],
            bounding_box=bbox,
            raw_text=evidence or f"{name} ₹{amount:,.0f}",
        ),
    )
    return FinancialComponent(
        name=name,
        amount=amt_field,
        category=category,
        charge_nature=charge_nature,
        evidence=evidence or f"{name} ₹{amount:,.0f}",
        source_ocr_line=str(line_id),
        bounding_box=bbox,
    )


class TestNeverFlagBasePriceAndStatutoryTaxes:
    """Base price, ex-showroom, TCS, GST, road tax, totals, and deductions are NEVER flagged."""

    @pytest.mark.parametrize(
        "category",
        [
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
        ],
    )
    def test_statutory_and_base_categories_never_flagged(self, category: ComponentCategory):
        comp = _make_component("Test Charge", 100000.0, category=category)
        result = ExtraCostAnalysisService.analyze([comp])
        assert result.total_flagged_count == 0
        assert len(result.flagged_costs) == 0

    def test_deductions_never_flagged(self):
        comp = _make_component(
            "Discount", 15000.0,
            category=ComponentCategory.DISCOUNT,
            charge_nature=ChargeNature.DEDUCTION,
        )
        result = ExtraCostAnalysisService.analyze([comp])
        assert result.total_flagged_count == 0

    def test_offers_never_flagged(self):
        comp = _make_component(
            "Dealer Offer", 10000.0,
            category=ComponentCategory.OFFER,
            charge_nature=ChargeNature.DEDUCTION,
        )
        result = ExtraCostAnalysisService.analyze([comp])
        assert result.total_flagged_count == 0


class TestExtendedWarrantyFlagging:
    """Extended warranty must be flagged as potentially optional with proper neutral language."""

    def test_extended_warranty_flagged(self):
        comp = _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.POTENTIALLY_OPTIONAL
        assert flag.what == "Extended warranty"
        assert flag.amount == 24000.0
        assert flag.potential_saving == 24000.0

    def test_extended_warranty_saving_language_neutral(self):
        comp = _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY)
        result = ExtraCostAnalysisService.analyze([comp])
        flag = result.flagged_costs[0]

        # Must NOT contain "you can save" or "unnecessary"
        assert "you can save" not in flag.saving_language.lower()
        assert "unnecessary" not in flag.saving_language.lower()
        # Must contain conditional phrasing
        assert "if" in flag.saving_language.lower()
        assert "could be removed" in flag.saving_language.lower()

    def test_extended_warranty_what_to_verify(self):
        comp = _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY)
        result = ExtraCostAnalysisService.analyze([comp])
        flag = result.flagged_costs[0]

        assert "optional" in flag.what_to_verify.lower()
        assert "removing" in flag.what_to_verify.lower() or "remove" in flag.what_to_verify.lower()


class TestBundledPackageFlagging:
    """Bundled packages must be flagged with package-specific questions."""

    @pytest.mark.parametrize(
        "category",
        [
            ComponentCategory.ACCESSORY_PACKAGE,
            ComponentCategory.DEALER_PACKAGE,
            ComponentCategory.SERVICE_PACKAGE,
        ],
    )
    def test_bundled_packages_flagged(self, category: ComponentCategory):
        comp = _make_component("Dealer Protection Package", 18000.0, category=category)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.BUNDLED_PACKAGE

    def test_bundled_package_questions_generated(self):
        comp = _make_component(
            "Dealer Protection Package", 18000.0,
            category=ComponentCategory.DEALER_PACKAGE,
        )
        result = ExtraCostAnalysisService.analyze([comp])
        flag = result.flagged_costs[0]

        assert len(flag.bundled_questions) >= 3
        questions_text = " ".join(flag.bundled_questions).lower()
        assert "included" in questions_text
        assert "required" in questions_text or "mandatory" in questions_text
        assert "individual" in questions_text or "separately" in questions_text


class TestDealerAddedCharges:
    """Individual accessories must be flagged as dealer-added charges."""

    def test_accessory_flagged_as_dealer_added(self):
        comp = _make_component("Seat Cover", 5000.0, category=ComponentCategory.ACCESSORY)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.DEALER_ADDED
        assert flag.potential_saving == 5000.0


class TestHandlingAndProcessingFees:
    """Handling, logistics, and processing fees must be flagged as additional charges."""

    @pytest.mark.parametrize(
        "category,name",
        [
            (ComponentCategory.HANDLING_FEE, "Handling Charges"),
            (ComponentCategory.LOGISTICS_FEE, "Logistics Fee"),
            (ComponentCategory.PROCESSING_FEE, "Documentation Fee"),
            (ComponentCategory.OTHER_FEE, "Miscellaneous Fee"),
        ],
    )
    def test_fee_categories_flagged(self, category: ComponentCategory, name: str):
        comp = _make_component(name, 8500.0, category=category)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.ADDITIONAL_CHARGE
        assert flag.potential_saving == 8500.0


class TestInsuranceFlagging:
    """Insurance is flagged for verification but without a potential saving (it's mandatory, just source-negotiable)."""

    def test_insurance_flagged_for_verification(self):
        comp = _make_component("Insurance", 34500.0, category=ComponentCategory.INSURANCE)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.REQUIRES_VERIFICATION
        assert flag.potential_saving is None  # Not directly removable
        assert flag.saving_language is None


class TestRegistrationFlagging:
    """Registration-related charges are flagged for verification but without claiming they can be removed."""

    @pytest.mark.parametrize(
        "category",
        [
            ComponentCategory.REGISTRATION,
            ComponentCategory.RC,
            ComponentCategory.HSRP,
        ],
    )
    def test_registration_charges_flagged_for_verification(self, category: ComponentCategory):
        comp = _make_component("Registration", 76250.0, category=category)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.REQUIRES_VERIFICATION
        assert flag.potential_saving is None  # Can't remove registration


class TestFastagFlagging:
    """FASTag is flagged with potential saving only when dealer charges above ~₹500."""

    def test_fastag_with_markup_flagged(self):
        comp = _make_component("FASTag", 1500.0, category=ComponentCategory.FASTAG)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.ADDITIONAL_CHARGE
        assert flag.potential_saving == 1000.0  # 1500 - 500

    def test_fastag_at_official_rate_no_saving(self):
        comp = _make_component("FASTag", 500.0, category=ComponentCategory.FASTAG)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.potential_saving is None  # At official rate


class TestUnclearChargeFlagging:
    """Unclear/unknown charges must be flagged as unclear with full potential saving."""

    def test_unclear_charge_flagged(self):
        comp = _make_component("XYZ", 5000.0, category=ComponentCategory.UNCLEAR)
        result = ExtraCostAnalysisService.analyze([comp])

        assert result.total_flagged_count == 1
        flag = result.flagged_costs[0]
        assert flag.flag_type == ExtraCostFlagType.UNCLEAR_CHARGE
        assert flag.potential_saving == 5000.0
        assert "clarify" in flag.what_to_verify.lower()


class TestDuplicateDetection:
    """Multiple charges in the same non-statutory category should flag possible duplicates."""

    def test_duplicate_accessories_detected(self):
        comp1 = _make_component("Floor Mats", 3000.0, category=ComponentCategory.ACCESSORY)
        comp2 = _make_component("Floor Mats Premium", 4500.0, category=ComponentCategory.ACCESSORY)
        result = ExtraCostAnalysisService.analyze([comp1, comp2])

        # Both should be flagged (first as dealer_added, second as possible_duplicate)
        assert result.total_flagged_count == 2
        flag_types = {f.flag_type for f in result.flagged_costs}
        assert ExtraCostFlagType.POSSIBLE_DUPLICATE in flag_types


class TestNeutralLanguageEnforcement:
    """The system must NEVER use prohibited language like 'unnecessary', 'you can save', or 'you should remove'."""

    PROHIBITED_PHRASES = [
        "unnecessary",
        "you can save",
        "you should remove",
        "waste of money",
        "rip off",
        "scam",
        "fraud",
        "definitely",
    ]

    def test_no_prohibited_language_in_any_flag(self):
        components = [
            _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Dealer Protection Package", 18000.0, category=ComponentCategory.DEALER_PACKAGE),
            _make_component("Handling Charges", 8500.0, category=ComponentCategory.HANDLING_FEE),
            _make_component("XYZ", 5000.0, category=ComponentCategory.UNCLEAR),
            _make_component("Seat Cover", 3000.0, category=ComponentCategory.ACCESSORY),
        ]
        result = ExtraCostAnalysisService.analyze(components)

        for flag in result.flagged_costs:
            all_text = (
                f"{flag.flag_label} {flag.why_flagged} {flag.what_to_verify} "
                f"{flag.saving_language or ''}"
            ).lower()
            for phrase in self.PROHIBITED_PHRASES:
                assert phrase not in all_text, (
                    f"Prohibited phrase '{phrase}' found in flag for '{flag.what}'"
                )


class TestCompleteFlagFieldPopulation:
    """Every ExtraCostFlag must have all required fields populated."""

    def test_all_fields_populated(self):
        comp = _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY)
        result = ExtraCostAnalysisService.analyze([comp])
        flag = result.flagged_costs[0]

        # Required fields
        assert flag.component_id is not None
        assert flag.flag_type is not None
        assert flag.flag_label is not None and len(flag.flag_label) > 0
        assert flag.what is not None and len(flag.what) > 0
        assert flag.normalized_name is not None
        assert flag.category is not None
        assert flag.amount > 0
        assert flag.why_flagged is not None and len(flag.why_flagged) > 0
        assert flag.what_to_verify is not None and len(flag.what_to_verify) > 0


class TestReductionSummary:
    """Reduction summary must be accurate and evidence-appropriate."""

    def test_no_flags_summary(self):
        comp = _make_component("Ex-Showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE)
        result = ExtraCostAnalysisService.analyze([comp])
        assert "no charges" in result.reduction_summary.lower()

    def test_with_flags_summary_mentions_count_and_amount(self):
        components = [
            _make_component("Ex-Showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Handling Charges", 8500.0, category=ComponentCategory.HANDLING_FEE),
        ]
        result = ExtraCostAnalysisService.analyze(components)
        assert result.total_flagged_count == 2
        assert result.total_potential_reduction == 32500.0
        assert "2" in result.reduction_summary
        assert "verify" in result.reduction_summary.lower()


class TestFullQuotationScenario:
    """End-to-end test with a realistic vehicle quotation cost breakdown."""

    def test_realistic_quotation_analysis(self):
        components = [
            _make_component("Ex-Showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("TCS", 11499.0, category=ComponentCategory.TCS),
            _make_component("Road Tax", 85000.0, category=ComponentCategory.ROAD_TAX),
            _make_component("Insurance", 34500.0, category=ComponentCategory.INSURANCE),
            _make_component("Registration", 76250.0, category=ComponentCategory.REGISTRATION),
            _make_component("HSRP", 2250.0, category=ComponentCategory.HSRP),
            _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Accessories Package", 15500.0, category=ComponentCategory.ACCESSORY_PACKAGE),
            _make_component("Handling Charges", 8500.0, category=ComponentCategory.HANDLING_FEE),
            _make_component("Dealer Offer", 15000.0, category=ComponentCategory.OFFER),
        ]
        result = ExtraCostAnalysisService.analyze(components)

        # Should NOT flag: Ex-Showroom, TCS, Road Tax, Dealer Offer
        # SHOULD flag: Insurance, Registration, HSRP, Extended Warranty, Accessories Package, Handling Charges
        assert result.total_flagged_count == 6
        assert result.total_charges_analyzed == 10  # All 10 are charge-nature (offer passed as charge in test data)

        flagged_names = {f.what for f in result.flagged_costs}
        # Verify expected items are flagged
        assert any("warranty" in n.lower() for n in flagged_names)
        assert any("handling" in n.lower() for n in flagged_names)
        assert any("insurance" in n.lower() for n in flagged_names)

        # Verify unflagged items
        flag_ids = {f.component_id for f in result.flagged_costs}
        for comp in components:
            if comp.category in (
                ComponentCategory.EX_SHOWROOM_PRICE,
                ComponentCategory.TCS,
                ComponentCategory.ROAD_TAX,
                ComponentCategory.OFFER,
            ):
                assert str(comp.component_id) not in flag_ids

    def test_potential_saving_is_sum_of_removable_only(self):
        """Potential saving must NOT include insurance or registration (not directly removable)."""
        components = [
            _make_component("Ex-Showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE),
            _make_component("Insurance", 34500.0, category=ComponentCategory.INSURANCE),
            _make_component("Registration", 76250.0, category=ComponentCategory.REGISTRATION),
            _make_component("Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY),
            _make_component("Handling Charges", 8500.0, category=ComponentCategory.HANDLING_FEE),
        ]
        result = ExtraCostAnalysisService.analyze(components)

        # Insurance: no saving. Registration: no saving.
        # Extended Warranty: 24000. Handling: 8500.
        assert result.total_potential_reduction == 32500.0
