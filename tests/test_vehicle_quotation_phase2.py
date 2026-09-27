"""Phase 2: Comprehensive Test Suite for Vehicle Quotation OCR + Semantic Extraction.

Verifies:
1. Exact vehicle quotation charge recognition and normalization:
   - Ex-showroom price
   - Insurance
   - TCS
   - Registration / R.C.
   - Warranty
   - Temporary registration / HSRP
   - Accessories
   - Handling charges
   - Road tax
   - Dealer offers
   - Discounts
2. Spelling, abbreviation, and OCR noise variants across printed, PDF, and handwritten formats.
3. Charge payload structure: {raw_label, normalized_label, category, amount, confidence, evidence}.
4. Prevention of generic placeholders ("Financial Component 1", "Other charge", "Detected amount").
5. Strict guardrail against hallucinating meaning when evidence is insufficient:
   "XYZ ₹5,000" -> raw_label="XYZ", normalized_label="XYZ", category="Unclear", amount=5000.0.
6. Preservation of exact monetary values, decimal values, ₹ symbol, line relationships, and bounding boxes.
"""

from uuid import UUID, uuid4

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
from before_you_pay.services.extraction import FinancialExtractionEngine
from before_you_pay.services.financial_taxonomy import (
    classify_component_name,
    clean_component_text,
)


def _make_line(
    text: str,
    line_id: UUID | None = None,
    doc_id: UUID | None = None,
    page_id: UUID | None = None,
    line_number: int = 1,
    bbox: BoundingBox | None = None,
    confidence: float = 0.95,
) -> OcrLine:
    d_id = doc_id or uuid4()
    p_id = page_id or uuid4()
    return OcrLine(
        document_id=d_id,
        page_id=p_id,
        line_id=line_id or uuid4(),
        line_number=line_number,
        bounding_box=bbox
        or BoundingBox(
            x=0.08,
            y=0.20,
            width=0.82,
            height=0.035,
            coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
        ),
        text=text,
        confidence=confidence,
    )


def _make_amount_field(
    val: float, raw_text: str, line_id: UUID, doc_id: UUID, page_id: UUID, bbox: BoundingBox
) -> ExtractedField:
    return ExtractedField(
        field_id=uuid4(),
        field_key="test_amount",
        normalized_value=val,
        unit_or_currency="INR",
        confidence=0.96,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[line_id],
            bounding_box=bbox,
            raw_text=raw_text,
        ),
    )


class TestPromptExamplesAndExactDisplay:
    """Verifies all exact examples listed in the Phase 2 specification."""

    def test_ex_showroom_example(self):
        """'Ex-Showroom ₹11,49,900' -> Display: Ex-showroom price, ₹11,49,900."""
        text = "Ex-Showroom ₹11,49,900"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.EX_SHOWROOM_PRICE
        assert norm_name == "Ex-showroom price"
        assert nature == ChargeNature.CHARGE

        cleaned = clean_component_text(text)
        assert cleaned == "Ex-Showroom"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(1149900.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "Ex-Showroom"
        assert payload["normalized_label"] in ("Ex-showroom", "Ex-showroom price")
        assert payload["category"] in (ComponentCategory.EX_SHOWROOM_PRICE, "ex_showroom_price")
        assert payload["amount"] == 1149900.0
        assert payload["evidence"] == text

    def test_insurance_example(self):
        """'Insurance ₹34,500' -> Display: Insurance, ₹34,500."""
        text = "Insurance ₹34,500"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.INSURANCE
        assert norm_name == "Insurance"

        cleaned = clean_component_text(text)
        assert cleaned == "Insurance"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(34500.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "Insurance"
        assert payload["normalized_label"] == "Insurance"
        assert payload["category"] in (ComponentCategory.INSURANCE, "insurance")
        assert payload["amount"] == 34500.0

    def test_tcs_example(self):
        """'TCS ₹11,499' -> Display: TCS, ₹11,499."""
        text = "TCS ₹11,499"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.TCS
        assert norm_name == "TCS"

        cleaned = clean_component_text(text)
        assert cleaned == "TCS"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(11499.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "TCS"
        assert payload["normalized_label"] == "TCS"
        assert payload["category"] in (ComponentCategory.TCS, "tcs")
        assert payload["amount"] == 11499.0

    def test_rc_example(self):
        """'R.C. ₹76,250' -> Display: Registration / R.C., ₹76,250."""
        text = "R.C. ₹76,250"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.RC
        assert norm_name == "Registration / R.C."

        cleaned = clean_component_text(text)
        assert cleaned == "R.C."

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(76250.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "R.C."
        assert payload["normalized_label"] in ("Registration", "Registration / R.C.")
        assert payload["category"] in (ComponentCategory.RC, "rc")
        assert payload["amount"] == 76250.0

    def test_warranty_example(self):
        """'Warranty ₹24,000' -> Display: Warranty, ₹24,000."""
        text = "Warranty ₹24,000"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.WARRANTY
        assert norm_name == "Warranty"

        cleaned = clean_component_text(text)
        assert cleaned == "Warranty"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(24000.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "Warranty"
        assert payload["normalized_label"] == "Warranty"
        assert payload["category"] in (ComponentCategory.WARRANTY, "warranty")
        assert payload["amount"] == 24000.0

    def test_temp_plus_hsrp_example(self):
        """'Temp + HSRP ₹2,250' -> Display: Temporary registration / HSRP, ₹2,250."""
        text = "Temp + HSRP ₹2,250"
        cat, norm_name, nature, opt, _ = classify_component_name(text)
        assert cat == ComponentCategory.HSRP
        assert norm_name == "Temporary registration / HSRP"

        cleaned = clean_component_text(text)
        assert cleaned == "Temp + HSRP"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(2250.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "Temp + HSRP"
        assert payload["normalized_label"] in ("HSRP", "Temporary registration / HSRP")
        assert payload["category"] in (ComponentCategory.HSRP, "hsrp")
        assert payload["amount"] == 2250.0


class TestStrictGuardrailAgainstInventingMeaning:
    """Do not infer a category when evidence is insufficient.

    If OCR says: "XYZ ₹5,000", display: XYZ, ₹5,000, Category: Unclear.
    Never invent meaning. Never use generic placeholders like "Financial Component 1".
    """

    def test_xyz_unclear_charge(self):
        text = "XYZ ₹5,000"
        cat, norm_name, nature, opt, exp = classify_component_name(text)
        assert cat == ComponentCategory.UNCLEAR
        assert norm_name == "XYZ"
        assert nature == ChargeNature.CHARGE
        assert opt == "unknown"

        cleaned = clean_component_text(text)
        assert cleaned == "XYZ"

        doc_id = uuid4()
        page_id = uuid4()
        line = _make_line(text, doc_id=doc_id, page_id=page_id)
        amt_field = _make_amount_field(5000.0, text, line.line_id, doc_id, page_id, line.bounding_box)

        comp = FinancialComponent(
            name=cleaned,
            amount=amt_field,
            evidence=text,
            source_ocr_line=str(line.line_id),
            bounding_box=line.bounding_box,
        )
        payload = comp.to_charge_payload()

        assert payload["raw_label"] == "XYZ"
        assert payload["normalized_label"] == "XYZ"
        assert payload["category"] in ("Unclear", "unclear", ComponentCategory.UNCLEAR)
        assert payload["amount"] == 5000.0
        assert payload["evidence"] == text

    @pytest.mark.parametrize(
        "unrecognized_text,expected_label",
        [
            ("ABC ₹1,200", "ABC"),
            ("FOOBAR ₹9,999", "FOOBAR"),
            ("UNKNOWN_CODE ₹450", "UNKNOWN_CODE"),
            ("SPECIAL_LEVY ₹3,500/-", "SPECIAL_LEVY"),
        ],
    )
    def test_arbitrary_unsupported_charges_fall_back_to_unclear(
        self, unrecognized_text: str, expected_label: str
    ):
        cat, norm_name, _, _, _ = classify_component_name(unrecognized_text)
        assert cat == ComponentCategory.UNCLEAR
        assert norm_name == expected_label

        cleaned = clean_component_text(unrecognized_text)
        assert cleaned == expected_label

    def test_no_generic_placeholder_strings_when_meaningful_evidence_present(self):
        """System must never emit 'Financial Component 1', 'Other charge', or 'Detected amount'."""
        generic_forbidden = [
            "financial component 1",
            "financial component 2",
            "other charge",
            "detected amount",
            "component 1",
        ]
        test_inputs = [
            "Ex-Showroom ₹11,49,900",
            "Insurance ₹34,500",
            "TCS ₹11,499",
            "R.C. ₹76,250",
            "Warranty ₹24,000",
            "Temp + HSRP ₹2,250",
            "Handling charges ₹8,500",
            "Accessories ₹12,000",
            "Road tax ₹85,000",
            "Dealer offer ₹15,000",
            "Discount ₹20,000",
        ]
        for inp in test_inputs:
            cat, norm_name, _, _, _ = classify_component_name(inp)
            assert cat != ComponentCategory.UNKNOWN
            assert cat != ComponentCategory.UNCLEAR
            assert norm_name.lower() not in generic_forbidden


class TestMultipleSpellingAndOcrVariants:
    """Comprehensive test across multiple spelling, abbreviation, and noisy OCR variants.

    Categories tested:
    1. Ex-showroom
    2. Insurance
    3. TCS
    4. Registration
    5. RC
    6. Warranty
    7. Accessories
    8. Handling
    9. Road tax
    10. HSRP
    11. Offers
    12. Discounts
    """

    @pytest.mark.parametrize(
        "variant",
        [
            "Ex showroom",
            "Ex-showroom",
            "Ex. Showroom",
            "ExShowroom",
            "Ex-Showroom Price",
            "Ex showroom price",
            "Ex-showroom cost",
            "Ex-shwroom",
            "Ex-shroom",
            "Vehicle Base Price",
            "Ex-Showroom ₹11,49,900",
            "Ex-Showroom: 11,49,900/-",
        ],
    )
    def test_ex_showroom_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.EX_SHOWROOM_PRICE
        assert norm == "Ex-showroom price"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "Insurance",
            "Ins.",
            "Ins",
            "Vehicle Insurance",
            "Motor Insurance",
            "Zero Dep Insurance",
            "Comprehensive Insurance",
            "1 Yr OD + 3 Yr TP",
            "Insuranse",
            "Insurace",
            "Insurance ₹34,500",
            "Insurance Premium",
        ],
    )
    def test_insurance_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.INSURANCE
        assert norm == "Insurance"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "TCS",
            "T.C.S.",
            "TCS @ 1%",
            "TCS 1%",
            "Tax Collected at Source",
            "T C S",
            "TCS ₹11,499",
            "T.C.S: 11,499",
        ],
    )
    def test_tcs_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.TCS
        assert norm == "TCS"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "Registration",
            "Registration Charges",
            "Regn.",
            "Regn",
            "Reg charges",
            "RTO Registration",
            "RTO Fee",
            "RTO charges",
            "Registration Fees",
        ],
    )
    def test_registration_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.REGISTRATION
        assert norm == "Registration"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "R.C.",
            "RC",
            "R.C",
            "RC Charges",
            "Smart Card RC",
            "RC Card",
            "RC Book",
            "R.C. ₹76,250",
            "Smart card fee",
        ],
    )
    def test_rc_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.RC
        assert norm == "Registration / R.C."
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant,expected_cat",
        [
            ("Warranty", ComponentCategory.WARRANTY),
            ("Warranty ₹24,000", ComponentCategory.WARRANTY),
            ("Standard Warranty", ComponentCategory.WARRANTY),
            ("Std Warranty", ComponentCategory.WARRANTY),
            ("Std. Warranty", ComponentCategory.WARRANTY),
            ("Factory Warranty", ComponentCategory.WARRANTY),
            ("Extended Warranty", ComponentCategory.EXTENDED_WARRANTY),
            ("Ext Warranty", ComponentCategory.EXTENDED_WARRANTY),
            ("Ext. Warranty", ComponentCategory.EXTENDED_WARRANTY),
            ("EW", ComponentCategory.EXTENDED_WARRANTY),
            ("E.W. Charges", ComponentCategory.EXTENDED_WARRANTY),
            ("Shield Warranty", ComponentCategory.EXTENDED_WARRANTY),
        ],
    )
    def test_warranty_variants(self, variant: str, expected_cat: ComponentCategory):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == expected_cat
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant,expected_cat",
        [
            ("Accessories", ComponentCategory.ACCESSORY),
            ("Accessory", ComponentCategory.ACCESSORY),
            ("Acc.", ComponentCategory.ACCESSORY),
            ("Accs", ComponentCategory.ACCESSORY),
            ("Accs.", ComponentCategory.ACCESSORY),
            ("Seat Cover", ComponentCategory.ACCESSORY),
            ("Floor Mats", ComponentCategory.ACCESSORY),
            ("Mud Flaps", ComponentCategory.ACCESSORY),
            ("Accessories Package", ComponentCategory.ACCESSORY_PACKAGE),
            ("Accessory Package", ComponentCategory.ACCESSORY_PACKAGE),
            ("Dealer Accessories", ComponentCategory.ACCESSORY_PACKAGE),
            ("Basic Accessories Kit", ComponentCategory.ACCESSORY_PACKAGE),
            ("Essential Kit", ComponentCategory.ACCESSORY_PACKAGE),
            ("Accessories Kit", ComponentCategory.ACCESSORY_PACKAGE),
        ],
    )
    def test_accessories_variants(self, variant: str, expected_cat: ComponentCategory):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == expected_cat
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "Handling",
            "Handling Charges",
            "Handling Fee",
            "Depot Charges",
            "Incidental Charges",
            "PDI Charges",
            "PDI",
            "P.D.I.",
            "Handling charges ₹8,500",
        ],
    )
    def test_handling_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.HANDLING_FEE
        assert norm == "Handling charges"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "Road Tax",
            "Road Tax ₹76,250",
            "Roadtax",
            "Rd Tax",
            "MV Tax",
            "M.V. Tax",
            "Motor Vehicle Tax",
            "One Time Tax",
            "Life Time Tax",
            "RTO Tax",
        ],
    )
    def test_road_tax_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.ROAD_TAX
        assert norm == "Road tax"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "HSRP",
            "H.S.R.P.",
            "Temp + HSRP",
            "Temp + HSRP ₹2,250",
            "Temp + MSRP",
            "Temporary + HSRP",
            "Temp HSRP",
            "Number Plate",
            "High Security Registration Plate",
            "MSRP/HSRP",
        ],
    )
    def test_hsrp_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.HSRP
        assert norm == "Temporary registration / HSRP"
        assert nature == ChargeNature.CHARGE

    @pytest.mark.parametrize(
        "variant",
        [
            "Offer",
            "Offers",
            "Dealer Offer",
            "Special Offer",
            "Consumer Offer",
            "Exchange Bonus",
            "Extra Offer",
            "Dealer offer ₹15,000",
        ],
    )
    def test_offers_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.OFFER
        assert norm == "Dealer offer"
        assert nature == ChargeNature.DEDUCTION

    @pytest.mark.parametrize(
        "variant",
        [
            "Discount",
            "Discounts",
            "Cash Discount",
            "Trade Discount",
            "Total Discount",
            "Rebate",
            "Concession",
            "Disc.",
            "Disc",
            "Discount ₹20,000",
        ],
    )
    def test_discounts_variants(self, variant: str):
        cat, norm, nature, _, _ = classify_component_name(variant)
        assert cat == ComponentCategory.DISCOUNT
        assert norm == "Discount"
        assert nature == ChargeNature.DEDUCTION


class TestOcrPreservationAndSpatialRelationships:
    """Verifies preservation of monetary amounts, decimals, ₹ symbol, line relationships, and bounding boxes."""

    def test_exact_numeric_and_decimal_preservation(self):
        svc = FinancialExtractionEngine()
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()

        ocr_lines = [
            _make_line("Vehicle Quotation - Premium Sedan", doc_id=doc_id, page_id=page_id),
            _make_line("Ex-Showroom: ₹11,49,900.50", doc_id=doc_id, page_id=page_id),
            _make_line("Insurance (Comprehensive): ₹34,500.00", doc_id=doc_id, page_id=page_id),
            _make_line("TCS @ 1%: ₹11,499.75", doc_id=doc_id, page_id=page_id),
            _make_line("R.C. & Smart Card: ₹76,250", doc_id=doc_id, page_id=page_id),
            _make_line("Temp + HSRP: ₹2,250.25", doc_id=doc_id, page_id=page_id),
            _make_line("Extended Warranty (5 Yr): ₹24,000.00", doc_id=doc_id, page_id=page_id),
            _make_line("Essential Accessories Kit: ₹15,500.00", doc_id=doc_id, page_id=page_id),
            _make_line("Dealer Special Offer: -₹15,000.00", doc_id=doc_id, page_id=page_id),
            _make_line("Total Quoted Price: ₹12,98,899.50", doc_id=doc_id, page_id=page_id),
        ]

        ocr_res = OcrResult(
            document_id=doc_id,
            engine_name="test_engine",
            pages=[
                OcrPage(
                    document_id=doc_id,
                    page_number=1,
                    page_id=page_id,
                    width=1200,
                    height=1600,
                    lines=ocr_lines,
                )
            ],
        )

        doc = svc.extract(
            document_id=doc_id,
            user_id=user_id,
            ocr_result=ocr_res,
            document_type_hint=DocumentClassification.QUOTATION,
        )

        # Verify cost breakdown extracted
        assert len(doc.cost_breakdown) >= 7

        # Check Ex-Showroom precision
        ex_show = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.EX_SHOWROOM_PRICE)
        assert float(ex_show.amount.normalized_value) == 1149900.50
        assert "₹" in ex_show.evidence
        assert ex_show.bounding_box is not None
        assert ex_show.source_ocr_line is not None

        # Check TCS decimal precision
        tcs = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.TCS)
        assert float(tcs.amount.normalized_value) == 11499.75

        # Check HSRP decimal precision
        hsrp = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.HSRP)
        assert float(hsrp.amount.normalized_value) == 2250.25

        # Verify to_charge_payload works for each
        for comp in doc.cost_breakdown:
            p = comp.to_charge_payload()
            assert p["amount"] > 0
            assert len(p["raw_label"]) > 0
            assert len(p["normalized_label"]) > 0
            assert p["confidence"] > 0
            assert len(p["evidence"]) > 0

    def test_handwritten_and_mixed_quotation_preservation(self):
        """Simulates messy handwritten / dealer photographed quotation lines."""
        svc = FinancialExtractionEngine()
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()

        ocr_lines = [
            _make_line("ESTIMATE / QUOTE", doc_id=doc_id, page_id=page_id),
            _make_line("Ex showroom Rs. 849000/-", doc_id=doc_id, page_id=page_id),
            _make_line("Ins 28500", doc_id=doc_id, page_id=page_id),
            _make_line("Regn 65000", doc_id=doc_id, page_id=page_id),
            _make_line("XYZ 5000", doc_id=doc_id, page_id=page_id),
            _make_line("Total 947500", doc_id=doc_id, page_id=page_id),
        ]

        ocr_res = OcrResult(
            document_id=doc_id,
            engine_name="test_engine",
            pages=[
                OcrPage(
                    document_id=doc_id,
                    page_number=1,
                    page_id=page_id,
                    width=1000,
                    height=1400,
                    lines=ocr_lines,
                )
            ],
        )

        doc = svc.extract(
            document_id=doc_id,
            user_id=user_id,
            ocr_result=ocr_res,
            document_type_hint=DocumentClassification.QUOTATION,
        )

        # XYZ should be extracted into cost breakdown as UNCLEAR
        xyz_comp = next((c for c in doc.cost_breakdown if c.raw_label == "XYZ"), None)
        assert xyz_comp is not None
        assert xyz_comp.category == ComponentCategory.UNCLEAR
        assert float(xyz_comp.amount.normalized_value) == 5000.0

        p = xyz_comp.to_charge_payload()
        assert p["raw_label"] == "XYZ"
        assert p["normalized_label"] == "XYZ"
        assert p["category"] in ("Unclear", "unclear", ComponentCategory.UNCLEAR)
        assert p["amount"] == 5000.0
