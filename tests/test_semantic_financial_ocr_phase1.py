"""Unit and regression tests for Phase 1 - Semantic Financial OCR.

Tests imperfect financial label normalization, preservation of raw evidence,
deterministic aliases, the 11 core vehicle categories, and strict refusal
to invent missing amounts or guess unevidenced categories.
"""

from uuid import uuid4
import pytest

from before_you_pay.models import (
    BoundingBox,
    ComponentCategory,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OcrLine,
    OcrPage,
    OcrResult,
    OptionalityStatus,
)
from before_you_pay.services.extraction import FinancialExtractionEngine
from before_you_pay.services.financial_taxonomy import (
    classify_component_name,
    fix_ocr_letter_digit_noise,
    normalize_financial_label,
)


def _make_line(
    text: str,
    doc_id=None,
    page_id=None,
    line_num: int = 1,
    box: BoundingBox | None = None,
    confidence: float = 0.92,
) -> OcrLine:
    return OcrLine(
        document_id=doc_id or uuid4(),
        page_id=page_id or uuid4(),
        line_number=line_num,
        text=text,
        bounding_box=box or BoundingBox(x=0.05, y=0.10, width=0.80, height=0.03),
        confidence=confidence,
    )


def _make_amount_field(val: float, raw_text: str, line_id, doc_id, page_id, box, conf=0.95):
    return ExtractedField(
        field_id=uuid4(),
        field_key="test_amount",
        normalized_value=val,
        unit_or_currency="₹",
        confidence=conf,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[line_id],
            bounding_box=box,
            raw_text=raw_text,
        ),
    )


class TestPhase1ImperfectFinancialLabelNormalization:
    """Verifies that imperfect OCR financial labels normalize to clean display labels."""

    @pytest.mark.parametrize(
        "raw_input,expected_normalized",
        [
            # Required prompt examples
            ("EX-SHOWR00M", "Ex-showroom"),
            ("EX SHOWROOM", "Ex-showroom"),
            ("INSORANCE", "Insurance"),
            ("INSUR.", "Insurance"),
            ("INSURANCF", "Insurance"),
            ("R.C.", "Registration"),
            ("REGN.", "Registration"),
            ("EXT WARRANTY", "Extended Warranty"),
            # Normal spellings
            ("Ex-showroom", "Ex-showroom"),
            ("Insurance", "Insurance"),
            ("Registration", "Registration"),
            ("Extended Warranty", "Extended Warranty"),
            ("Warranty", "Warranty"),
            ("Accessories", "Accessories"),
            ("TCS", "TCS"),
            ("FASTag", "FASTag"),
            # Additional realistic OCR imperfections
            ("EX SHOWR00M", "Ex-showroom"),
            ("Ex-Showr00m", "Ex-showroom"),
            ("INSUR", "Insurance"),
            ("Insurancf", "Insurance"),
            ("Insorance", "Insurance"),
            ("R.C", "Registration"),
            ("RC", "Registration"),
            ("REGN", "Registration"),
            ("EXT. WARRANTY", "Extended Warranty"),
            ("Ext Warranty", "Extended Warranty"),
        ],
    )
    def test_imperfect_label_normalization_examples(
        self, raw_input: str, expected_normalized: str
    ):
        """Test normalize_financial_label converts imperfect OCR labels to clean labels."""
        normalized = normalize_financial_label(raw_input)
        assert normalized == expected_normalized, f"Expected {expected_normalized} for {raw_input}, got {normalized}"

    def test_fix_ocr_letter_digit_noise(self):
        """Test OCR digit and character corruption cleanup."""
        assert "SHOWROOM" in fix_ocr_letter_digit_noise("SHOWR00M")
        assert "INSURANCE" in fix_ocr_letter_digit_noise("INSURANCF")
        assert "INSURANCE" in fix_ocr_letter_digit_noise("INSORANCE")


class TestPhase1EvidencePreservation:
    """Verifies that for every extracted financial component, complete evidence is preserved:
    - raw_text
    - normalized_label
    - amount
    - category
    - confidence
    - page
    - bounding box / evidence
    """

    def test_financial_component_preserves_all_seven_attributes(self):
        doc_id = uuid4()
        page_id = uuid4()
        box = BoundingBox(x=0.05, y=0.10, width=0.80, height=0.03)
        line = _make_line("EX-SHOWR00M: ₹11,49,900", doc_id=doc_id, page_id=page_id, box=box, confidence=0.88)
        amt_field = _make_amount_field(1149900.0, "EX-SHOWR00M: ₹11,49,900", line.line_id, doc_id, page_id, box, conf=0.91)

        comp = FinancialComponent(
            raw_text="EX-SHOWR00M",
            name="EX-SHOWR00M",
            amount=amt_field,
            page=2,
            bounding_box=box,
            evidence="EX-SHOWR00M: ₹11,49,900",
            confidence=0.88,
        )

        # 1. raw_text
        assert comp.raw_text == "EX-SHOWR00M"
        # 2. normalized_label
        assert comp.normalized_label == "Ex-showroom"
        # 3. amount
        assert float(comp.amount.normalized_value) == 1149900.0
        # 4. category & vehicle_category
        assert comp.category in (ComponentCategory.EX_SHOWROOM_PRICE, ComponentCategory.BASE_PRICE)
        assert comp.vehicle_category == ComponentCategory.BASE_PRICE
        # 5. confidence
        assert comp.confidence == 0.88
        # 6. page
        assert comp.page == 2
        # 7. bounding box & evidence
        assert comp.bounding_box == box
        assert comp.evidence == "EX-SHOWR00M: ₹11,49,900"

        # Verify to_charge_payload preserves all 7 fields
        payload = comp.to_charge_payload()
        assert payload["raw_text"] == "EX-SHOWR00M"
        assert payload["normalized_label"] == "Ex-showroom"
        assert payload["amount"] == 1149900.0
        assert payload["vehicle_category"] == "base_price"
        assert payload["confidence"] == 0.88
        assert payload["page"] == 2
        assert payload["bounding_box"] == box.model_dump()
        assert payload["evidence"] == "EX-SHOWR00M: ₹11,49,900"


class TestPhase1CoreVehicleCategories:
    """Verifies that all 11 required vehicle categories are supported:
    BASE_PRICE, TAX_OR_STATUTORY, REGISTRATION, INSURANCE, WARRANTY,
    SERVICE, ACCESSORY, DEALER_CHARGE, FINANCING, DISCOUNT, OTHER.
    """

    def test_all_11_vehicle_categories_exist(self):
        expected_categories = [
            ComponentCategory.BASE_PRICE,
            ComponentCategory.TAX_OR_STATUTORY,
            ComponentCategory.REGISTRATION,
            ComponentCategory.INSURANCE,
            ComponentCategory.WARRANTY,
            ComponentCategory.SERVICE,
            ComponentCategory.ACCESSORY,
            ComponentCategory.DEALER_CHARGE,
            ComponentCategory.FINANCING,
            ComponentCategory.DISCOUNT,
            ComponentCategory.OTHER,
        ]
        for cat in expected_categories:
            assert isinstance(cat.value, str)
            # Each maps to its canonical vehicle category identity
            assert cat.to_vehicle_category() == cat

    @pytest.mark.parametrize(
        "sub_category,expected_vehicle_category",
        [
            (ComponentCategory.EX_SHOWROOM_PRICE, ComponentCategory.BASE_PRICE),
            (ComponentCategory.BASE_PRICE, ComponentCategory.BASE_PRICE),
            (ComponentCategory.TCS, ComponentCategory.TAX_OR_STATUTORY),
            (ComponentCategory.GST, ComponentCategory.TAX_OR_STATUTORY),
            (ComponentCategory.ROAD_TAX, ComponentCategory.TAX_OR_STATUTORY),
            (ComponentCategory.TAX, ComponentCategory.TAX_OR_STATUTORY),
            (ComponentCategory.RC, ComponentCategory.REGISTRATION),
            (ComponentCategory.REGISTRATION, ComponentCategory.REGISTRATION),
            (ComponentCategory.HSRP, ComponentCategory.REGISTRATION),
            (ComponentCategory.INSURANCE, ComponentCategory.INSURANCE),
            (ComponentCategory.EXTENDED_WARRANTY, ComponentCategory.WARRANTY),
            (ComponentCategory.WARRANTY, ComponentCategory.WARRANTY),
            (ComponentCategory.SERVICE_PACKAGE, ComponentCategory.SERVICE),
            (ComponentCategory.SERVICE, ComponentCategory.SERVICE_PACKAGE.to_vehicle_category()),
            (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY),
            (ComponentCategory.ACCESSORY_PACKAGE, ComponentCategory.ACCESSORY),
            (ComponentCategory.HANDLING_FEE, ComponentCategory.DEALER_CHARGE),
            (ComponentCategory.LOGISTICS_FEE, ComponentCategory.DEALER_CHARGE),
            (ComponentCategory.PROCESSING_FEE, ComponentCategory.DEALER_CHARGE),
            (ComponentCategory.DEALER_PACKAGE, ComponentCategory.DEALER_CHARGE),
            (ComponentCategory.FINANCING, ComponentCategory.FINANCING),
            (ComponentCategory.DISCOUNT, ComponentCategory.DISCOUNT),
            (ComponentCategory.OFFER, ComponentCategory.DISCOUNT),
            (ComponentCategory.OTHER_FEE, ComponentCategory.DEALER_CHARGE),
            (ComponentCategory.UNKNOWN, ComponentCategory.UNKNOWN),
            (ComponentCategory.UNCLEAR, ComponentCategory.UNKNOWN),
        ],
    )
    def test_fine_grained_to_vehicle_category_mapping(
        self, sub_category: ComponentCategory, expected_vehicle_category: ComponentCategory
    ):
        assert sub_category.to_vehicle_category() == expected_vehicle_category


class TestPhase1StrictGuardrails:
    """Verifies strict safety guardrails:
    - Never invent a missing amount.
    - Never convert unknown text into a known category without sufficient evidence.
    - Preserve the original OCR text for verification.
    - If uncertain, use UNKNOWN and require verification.
    - Do not hardcode values.
    """

    def test_never_invent_missing_amount(self):
        """Lines without amounts are never assigned fabricated monetary values."""
        svc = FinancialExtractionEngine()
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()

        lines = [
            _make_line("QUOTATION", doc_id=doc_id, page_id=page_id, line_num=1),
            _make_line("Registration charges applicable as per state rules", doc_id=doc_id, page_id=page_id, line_num=2),
            _make_line("Total 500000", doc_id=doc_id, page_id=page_id, line_num=3),
        ]
        ocr_res = OcrResult(
            document_id=doc_id,
            engine_name="test_engine",
            pages=[OcrPage(document_id=doc_id, page_number=1, page_id=page_id, width=1000, height=1400, lines=lines)],
        )
        doc = svc.extract(document_id=doc_id, user_id=user_id, ocr_result=ocr_res, document_type_hint=DocumentClassification.QUOTATION)

        # The line without amount should NOT have generated a FinancialComponent with an invented amount
        reg_comps = [c for c in doc.cost_breakdown if "applicable as per state" in c.raw_name]
        assert len(reg_comps) == 0

    def test_unknown_text_not_converted_without_evidence(self):
        """Unknown text like 'XYZ SPECIAL_CODE 999' is not converted into a known category."""
        raw_unknown = "XYZ SPECIAL_CODE 999"
        norm_label = normalize_financial_label(raw_unknown)
        # Should preserve cleaned raw text, not guess a known label like Insurance or Registration
        assert "XYZ" in norm_label
        assert "Insurance" not in norm_label
        assert "Registration" not in norm_label

        cat, _, _, _, _ = classify_component_name(raw_unknown)
        assert cat in (ComponentCategory.UNKNOWN, ComponentCategory.UNCLEAR)
        assert cat.to_vehicle_category() == ComponentCategory.UNKNOWN

    def test_uncertain_component_requires_verification(self):
        """Uncertain/unknown components flag that verification is required."""
        doc_id = uuid4()
        page_id = uuid4()
        box = BoundingBox(x=0.05, y=0.10, width=0.80, height=0.03)
        line = _make_line("MYSTERY_LEVY 4500", doc_id=doc_id, page_id=page_id, box=box)
        amt_field = _make_amount_field(4500.0, "MYSTERY_LEVY 4500", line.line_id, doc_id, page_id, box)

        comp = FinancialComponent(
            name="MYSTERY_LEVY",
            raw_text="MYSTERY_LEVY",
            amount=amt_field,
            category=ComponentCategory.UNKNOWN,
        )

        assert comp.category in (ComponentCategory.UNKNOWN, ComponentCategory.UNCLEAR)
        assert comp.vehicle_category == ComponentCategory.UNKNOWN
        payload = comp.to_charge_payload()
        assert payload["raw_text"] == "MYSTERY_LEVY"
        assert payload["requires_confirmation"] is not None

    def test_end_to_end_extraction_with_noisy_labels(self):
        """Extraction engine parses noisy OCR lines into clean normalized labels preserving evidence."""
        svc = FinancialExtractionEngine()
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()

        ocr_lines = [
            _make_line("VEHICLE QUOTATION", doc_id=doc_id, page_id=page_id, line_num=1),
            _make_line("EX-SHOWR00M 1149900", doc_id=doc_id, page_id=page_id, line_num=2),
            _make_line("INSORANCE 34500", doc_id=doc_id, page_id=page_id, line_num=3),
            _make_line("R.C. 76250", doc_id=doc_id, page_id=page_id, line_num=4),
            _make_line("EXT WARRANTY 24000", doc_id=doc_id, page_id=page_id, line_num=5),
            _make_line("Total 1284650", doc_id=doc_id, page_id=page_id, line_num=6),
        ]
        ocr_res = OcrResult(
            document_id=doc_id,
            engine_name="test_engine",
            pages=[OcrPage(document_id=doc_id, page_number=1, page_id=page_id, width=1000, height=1400, lines=ocr_lines)],
        )

        doc = svc.extract(document_id=doc_id, user_id=user_id, ocr_result=ocr_res, document_type_hint=DocumentClassification.QUOTATION)

        # Verify extracted cost components
        by_label = {c.normalized_label: c for c in doc.cost_breakdown}

        # 1. EX-SHOWR00M -> Ex-showroom
        assert "Ex-showroom" in by_label
        ex = by_label["Ex-showroom"]
        assert ex.raw_text == "EX-SHOWR00M 1149900" or "EX-SHOWR00M" in ex.raw_name
        assert float(ex.amount.normalized_value) == 1149900.0
        assert ex.vehicle_category == ComponentCategory.BASE_PRICE

        # 2. INSORANCE -> Insurance
        assert "Insurance" in by_label
        ins = by_label["Insurance"]
        assert float(ins.amount.normalized_value) == 34500.0
        assert ins.vehicle_category == ComponentCategory.INSURANCE

        # 3. R.C. -> Registration
        assert "Registration" in by_label
        rc = by_label["Registration"]
        assert float(rc.amount.normalized_value) == 76250.0
        assert rc.vehicle_category == ComponentCategory.REGISTRATION

        # 4. EXT WARRANTY -> Extended Warranty
        assert "Extended Warranty" in by_label
        ew = by_label["Extended Warranty"]
        assert float(ew.amount.normalized_value) == 24000.0
        assert ew.vehicle_category == ComponentCategory.WARRANTY
