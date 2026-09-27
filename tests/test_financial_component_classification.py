"""Regression tests for Phase 1: Semantic Financial Component Classification.

Verifies:
1. Category classification across synonyms, abbreviations, and OCR variations.
2. OCR typo tolerance and fuzzy matching.
3. Preservation of raw_name, normalized_name, and category on FinancialComponent.
4. Comprehensive field support: charge_or_deduction, optionality_status, confidence,
   evidence, source_ocr_line, bounding_box, page, explanation.
5. Serialization round-trip and validation consistency.
"""

from uuid import uuid4

import pytest

from before_you_pay.models import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    StructuredFinancialDocument,
    ValidationStatus,
)
from before_you_pay.services.financial_taxonomy import (
    classify_component_name,
)
from before_you_pay.services.validation import DeterministicValidationEngine


def _make_provenance(raw_text: str = "Component: 1000") -> FieldProvenance:
    return FieldProvenance(
        document_id=uuid4(),
        page_id=uuid4(),
        ocr_line_ids=[uuid4()],
        bounding_box=BoundingBox(
            x=0.1, y=0.15, width=0.45, height=0.03, coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE
        ),
        raw_text=raw_text,
    )


def _make_field(key: str, val: float, raw_text: str = "") -> ExtractedField:
    return ExtractedField(
        field_key=key,
        normalized_value=val,
        unit_or_currency="INR",
        confidence=0.96,
        provenance=_make_provenance(raw_text or f"{key}: {val}"),
    )


class TestSemanticComponentClassification:
    """Test suite for semantic taxonomy classification across synonyms and aliases."""

    @pytest.mark.parametrize(
        "raw_text,expected_category,expected_normalized_name",
        [
            ("Ex showroom", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex-showroom", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex Showroom Price", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex. Showroom", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex-Showroom Price", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex Showroom ₹11,49,900", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Exshowroom", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Ex-Showroom Cost", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
            ("Vehicle Base Price", ComponentCategory.EX_SHOWROOM_PRICE, "Ex-showroom price"),
        ],
    )
    def test_ex_showroom_synonyms_and_variations(
        self, raw_text: str, expected_category: ComponentCategory, expected_normalized_name: str
    ):
        cat, norm_name, nature, opt, exp = classify_component_name(raw_text)
        assert cat == expected_category
        assert norm_name == expected_normalized_name
        assert nature == ChargeNature.CHARGE
        assert opt == "mandatory"
        assert len(exp) > 0

    @pytest.mark.parametrize(
        "raw_text,expected_category,expected_normalized_name",
        [
            ("Ins.", ComponentCategory.INSURANCE, "Insurance"),
            ("Insurance", ComponentCategory.INSURANCE, "Insurance"),
            ("Vehicle Insurance", ComponentCategory.INSURANCE, "Insurance"),
            ("Motor Insurance", ComponentCategory.INSURANCE, "Insurance"),
            ("Insurance Premium", ComponentCategory.INSURANCE, "Insurance"),
            ("Zero Dep Insurance", ComponentCategory.INSURANCE, "Insurance"),
            ("Comprehensive Insurance", ComponentCategory.INSURANCE, "Insurance"),
            ("1 Yr OD + 3 Yr TP", ComponentCategory.INSURANCE, "Insurance"),
        ],
    )
    def test_insurance_synonyms(
        self, raw_text: str, expected_category: ComponentCategory, expected_normalized_name: str
    ):
        cat, norm_name, nature, opt, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert norm_name == expected_normalized_name
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "raw_text,expected_category",
        [
            ("R.C.", ComponentCategory.RC),
            ("RC", ComponentCategory.RC),
            ("RC Book", ComponentCategory.RC),
            ("Smart Card RC", ComponentCategory.RC),
            ("Registration", ComponentCategory.REGISTRATION),
            ("Registration Charges", ComponentCategory.REGISTRATION),
            ("Regn.", ComponentCategory.REGISTRATION),
            ("Regn Charges", ComponentCategory.REGISTRATION),
            ("Road Tax", ComponentCategory.ROAD_TAX),
            ("M.V. Tax", ComponentCategory.ROAD_TAX),
            ("One Time Tax", ComponentCategory.ROAD_TAX),
            ("RTO Tax", ComponentCategory.ROAD_TAX),
        ],
    )
    def test_registration_rc_and_road_tax_disambiguation(
        self, raw_text: str, expected_category: ComponentCategory
    ):
        cat, _, nature, _, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "raw_text,expected_category,expected_opt",
        [
            ("Warranty", ComponentCategory.WARRANTY, "recommended"),
            ("Std Warranty", ComponentCategory.WARRANTY, "recommended"),
            ("Standard Warranty", ComponentCategory.WARRANTY, "recommended"),
            ("Extended Warranty", ComponentCategory.EXTENDED_WARRANTY, "optional"),
            ("Ext Warranty", ComponentCategory.EXTENDED_WARRANTY, "optional"),
            ("Ext. Warranty", ComponentCategory.EXTENDED_WARRANTY, "optional"),
            ("Shield Warranty", ComponentCategory.EXTENDED_WARRANTY, "optional"),
            ("E.W. Charges", ComponentCategory.EXTENDED_WARRANTY, "optional"),
        ],
    )
    def test_warranty_vs_extended_warranty(
        self, raw_text: str, expected_category: ComponentCategory, expected_opt: str
    ):
        cat, _, nature, opt, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert nature == ChargeNature.CHARGE
        assert opt == expected_opt

    @pytest.mark.parametrize(
        "raw_text,expected_category",
        [
            ("Accessories", ComponentCategory.ACCESSORY),
            ("Floor Mats", ComponentCategory.ACCESSORY),
            ("Seat Covers", ComponentCategory.ACCESSORY),
            ("Accessories Package", ComponentCategory.ACCESSORY_PACKAGE),
            ("Dealer Accessories", ComponentCategory.ACCESSORY_PACKAGE),
            ("Accessory Kit", ComponentCategory.ACCESSORY_PACKAGE),
            ("Essential Kit", ComponentCategory.ACCESSORY_PACKAGE),
        ],
    )
    def test_accessories_and_packages(
        self, raw_text: str, expected_category: ComponentCategory
    ):
        cat, _, _, opt, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert opt == "optional"

    @pytest.mark.parametrize(
        "raw_text,expected_category,expected_normalized_name",
        [
            ("Handling", ComponentCategory.HANDLING_FEE, "Handling charges"),
            ("Handling Charges", ComponentCategory.HANDLING_FEE, "Handling charges"),
            ("Depot Charges", ComponentCategory.HANDLING_FEE, "Handling charges"),
            ("Logistics", ComponentCategory.LOGISTICS_FEE, "Logistics charges"),
            ("Logistics Charges", ComponentCategory.LOGISTICS_FEE, "Logistics charges"),
            ("Freight Charges", ComponentCategory.LOGISTICS_FEE, "Logistics charges"),
            ("Processing", ComponentCategory.PROCESSING_FEE, "Processing / documentation fee"),
            ("Processing Fee", ComponentCategory.PROCESSING_FEE, "Processing / documentation fee"),
            ("Documentation Charges", ComponentCategory.PROCESSING_FEE, "Processing / documentation fee"),
            ("Doc Charges", ComponentCategory.PROCESSING_FEE, "Processing / documentation fee"),
        ],
    )
    def test_fee_categories(
        self, raw_text: str, expected_category: ComponentCategory, expected_normalized_name: str
    ):
        cat, norm_name, nature, opt, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert norm_name == expected_normalized_name
        assert nature == ChargeNature.CHARGE
        assert opt == "optional"

    @pytest.mark.parametrize(
        "raw_text,expected_category",
        [
            ("Temp + MSRP", ComponentCategory.HSRP),
            ("MSRP/HSRP", ComponentCategory.HSRP),
            ("HSRP", ComponentCategory.HSRP),
            ("High Security Registration Plate", ComponentCategory.HSRP),
            ("Number Plate", ComponentCategory.HSRP),
            ("TCS", ComponentCategory.TCS),
            ("TCS @ 1%", ComponentCategory.TCS),
            ("GST", ComponentCategory.GST),
            ("CGST", ComponentCategory.GST),
            ("FASTag", ComponentCategory.FASTAG),
            ("Fas Tag", ComponentCategory.FASTAG),
        ],
    )
    def test_hsrp_tax_and_fastag(self, raw_text: str, expected_category: ComponentCategory):
        cat, _, nature, _, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "raw_text,expected_category,expected_nature",
        [
            ("Offer", ComponentCategory.OFFER, ChargeNature.DEDUCTION),
            ("Extra offer", ComponentCategory.OFFER, ChargeNature.DEDUCTION),
            ("Dealer Offer", ComponentCategory.OFFER, ChargeNature.DEDUCTION),
            ("Exchange Bonus", ComponentCategory.OFFER, ChargeNature.DEDUCTION),
            ("Discount", ComponentCategory.DISCOUNT, ChargeNature.DEDUCTION),
            ("Total Discount", ComponentCategory.DISCOUNT, ChargeNature.DEDUCTION),
            ("Cash Discount", ComponentCategory.DISCOUNT, ChargeNature.DEDUCTION),
            ("Rebate", ComponentCategory.DISCOUNT, ChargeNature.DEDUCTION),
            ("Subtotal", ComponentCategory.SUBTOTAL, ChargeNature.CHARGE),
            ("Total before offers", ComponentCategory.SUBTOTAL, ChargeNature.CHARGE),
            ("Total", ComponentCategory.TOTAL, ChargeNature.CHARGE),
            ("On-Road Total", ComponentCategory.TOTAL, ChargeNature.CHARGE),
            ("Amount Paid", ComponentCategory.AMOUNT_PAID, ChargeNature.DEDUCTION),
            ("Advance", ComponentCategory.AMOUNT_PAID, ChargeNature.DEDUCTION),
            ("Balance Due", ComponentCategory.BALANCE_DUE, ChargeNature.CHARGE),
        ],
    )
    def test_deductions_and_aggregates(
        self, raw_text: str, expected_category: ComponentCategory, expected_nature: ChargeNature
    ):
        cat, _, nature, _, _ = classify_component_name(raw_text)
        assert cat == expected_category
        assert nature == expected_nature

    def test_fuzzy_matching_ocr_typos(self):
        """Verify fuzzy distance matching correctly recovers noisy OCR readings."""
        assert classify_component_name("Exshowrom")[0] == ComponentCategory.EX_SHOWROOM_PRICE
        assert classify_component_name("Insuranse")[0] == ComponentCategory.INSURANCE
        assert classify_component_name("Registraton")[0] == ComponentCategory.REGISTRATION
        assert classify_component_name("Waranty")[0] == ComponentCategory.WARRANTY
        assert classify_component_name("Accesorries")[0] == ComponentCategory.ACCESSORY


class TestFinancialComponentModelBehavior:
    """Test suite verifying FinancialComponent fields, provenance, and defaults."""

    def test_model_preserves_raw_name_and_provides_normalized_name(self):
        """Do not destroy original text: store raw_name, normalized_name, and category."""
        prov = _make_provenance("Ex-Showroom: ₹11,49,900")
        amt = ExtractedField(
            field_key="ex_showroom", normalized_value=1149900.0, confidence=0.98, provenance=prov
        )

        comp = FinancialComponent(
            name="Ex-Showroom",
            amount=amt,
        )

        # 1. Original text preserved
        assert comp.name == "Ex-Showroom"
        assert comp.raw_name == "Ex-Showroom"

        # 2. Human-friendly normalized name
        assert comp.normalized_name == "Ex-showroom price"

        # 3. Category
        assert comp.category == ComponentCategory.EX_SHOWROOM_PRICE
        assert comp.category == "EX_SHOWROOM_PRICE"
        assert comp.category == "ex_showroom_price"

        # 4. Mandatory attributes
        assert comp.charge_nature == ChargeNature.CHARGE
        assert comp.charge_or_deduction == "charge"
        assert comp.optionality_status == "mandatory"
        assert not comp.is_optional
        assert comp.confidence == 0.98
        assert comp.evidence == "Ex-Showroom: ₹11,49,900"
        assert comp.source_ocr_line == str(prov.ocr_line_ids[0])
        assert comp.bounding_box is not None
        assert comp.bounding_box.x == 0.1
        assert comp.page == 1
        assert "Vehicle manufacturer base price" in comp.explanation

    def test_deduction_component_populates_correct_nature_and_status(self):
        """Deduction components (e.g. Extra offer) automatically derive deduction nature."""
        amt = _make_field("offer", 50000.0, "Extra offer: -50,000")
        comp = FinancialComponent(
            name="Extra offer",
            amount=amt,
        )

        assert comp.raw_name == "Extra offer"
        assert comp.normalized_name == "Dealer offer"
        assert comp.category == ComponentCategory.OFFER
        assert comp.charge_nature == ChargeNature.DEDUCTION
        assert comp.charge_or_deduction == "deduction"

    def test_optional_component_populates_optionality_status(self):
        """Extended warranty and accessories are classified as optional."""
        amt = _make_field("ext_warranty", 24000.0, "Ext Warranty: 24,000")
        comp = FinancialComponent(
            name="Ext Warranty",
            amount=amt,
        )

        assert comp.category == ComponentCategory.EXTENDED_WARRANTY
        assert comp.normalized_name == "Extended warranty"
        assert comp.optionality_status == "optional"
        assert comp.is_optional is True

    def test_serialization_and_deserialization_roundtrip(self):
        """FinancialComponent serializes to JSON/dict and reconstructs identically."""
        amt = _make_field("rc", 76250.0, "R.C.: 76,250")
        comp = FinancialComponent(
            name="R.C.",
            amount=amt,
        )

        serialized = comp.model_dump(mode="json")
        assert serialized["raw_name"] == "R.C."
        assert serialized["normalized_name"] == "Registration / R.C."
        assert serialized["category"] == "rc"
        assert serialized["charge_or_deduction"] == "charge"
        assert serialized["optionality_status"] in ("unclear", "mandatory", "confirmed_mandatory")

        reconstructed = FinancialComponent.model_validate(serialized)
        assert reconstructed.category == ComponentCategory.RC
        assert reconstructed.normalized_name == "Registration / R.C."
        assert reconstructed.raw_name == "R.C."
        assert reconstructed.optionality_status in ("unclear", "mandatory", "confirmed_mandatory")

    def test_validation_engine_reconciles_with_upgraded_components(self):
        """Quotation consistency validation functions seamlessly with the upgraded semantic components."""
        doc_id = uuid4()
        user_id = uuid4()

        components = [
            FinancialComponent(
                name="Ex-showroom",
                amount=_make_field("ex_showroom", 1149900.0),
            ),
            FinancialComponent(
                name="TCS",
                amount=_make_field("tcs", 11499.0),
            ),
            FinancialComponent(
                name="Insurance",
                amount=_make_field("insurance", 34500.0),
            ),
            FinancialComponent(
                name="R.C.",
                amount=_make_field("rc", 76250.0),
            ),
            FinancialComponent(
                name="Warranty",
                amount=_make_field("warranty", 24000.0),
            ),
            FinancialComponent(
                name="Temp + MSRP",
                amount=_make_field("msrp", 2250.0),
            ),
            FinancialComponent(
                name="Offer",
                amount=_make_field("offer", 20000.0),
            ),
            FinancialComponent(
                name="Extra offer",
                amount=_make_field("extra_offer", 50000.0),
            ),
        ]

        # Verify semantic categories were automatically resolved
        assert components[0].category == ComponentCategory.EX_SHOWROOM_PRICE
        assert components[1].category == ComponentCategory.TCS
        assert components[2].category == ComponentCategory.INSURANCE
        assert components[3].category == ComponentCategory.RC
        assert components[4].category == ComponentCategory.WARRANTY
        assert components[5].category == ComponentCategory.HSRP
        assert components[6].category == ComponentCategory.OFFER
        assert components[7].category == ComponentCategory.OFFER

        # Charges sum: 1149900 + 11499 + 34500 + 76250 + 24000 + 2250 = 12,98,399
        # Deductions sum: 20000 + 50000 = 70,000
        # Quoted Total: 1298399 - 70000 = 12,28,399
        subtotal_field = _make_field("subtotal", 1298399.0)
        total_field = _make_field("total", 1228399.0)

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            subtotal=subtotal_field,
            total_amount=total_field,
            cost_breakdown=components,
        )

        validator = DeterministicValidationEngine()
        checks = validator.validate(doc)
        checks_by_code = {c.check_code: c for c in checks}

        assert checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"].status == ValidationStatus.PASS
        assert checks_by_code["QUOTATION_NET_TOTAL_CONSISTENCY"].status == ValidationStatus.PASS
