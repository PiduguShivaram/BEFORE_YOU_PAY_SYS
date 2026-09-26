"""Unit and integration tests for date extraction, normalization, and OCR grounding."""

from uuid import uuid4

import pytest

from before_you_pay.core.dates import (
    fallback_extract_date,
    normalize_date_to_iso,
    verify_date_grounding,
)
from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    ExtractedField,
    FieldProvenance,
    OcrLine,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.validation import DeterministicValidationEngine


def make_ocr_line(text: str, line_no: int) -> OcrLine:
    doc_id = uuid4()
    page_id = uuid4()
    return OcrLine(
        line_id=uuid4(),
        page_id=page_id,
        document_id=doc_id,
        line_number=line_no,
        text=text,
        bounding_box=BoundingBox(
            x=0.1,
            y=min(0.02 * line_no, 0.9),
            width=0.8,
            height=0.01,
            coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
        ),
        confidence=0.98,
    )


class TestDateNormalization:
    """Test suite for normalize_date_to_iso."""

    def test_iso_dates_preserved(self):
        assert normalize_date_to_iso("2020-06-11") == "2020-06-11"
        assert normalize_date_to_iso("2020-07-11") == "2020-07-11"
        assert normalize_date_to_iso("2024/12/31") == "2024-12-31"

    def test_dmy_dates_normalized(self):
        assert normalize_date_to_iso("11-06-2020", default_dmy=True) == "2020-06-11"
        assert normalize_date_to_iso("11-07-2020", default_dmy=True) == "2020-07-11"
        assert normalize_date_to_iso("11/06/2020", default_dmy=True) == "2020-06-11"
        assert normalize_date_to_iso("25/12/2021", default_dmy=False) == "2021-12-25"

    def test_named_months(self):
        assert normalize_date_to_iso("11 June 2020") == "2020-06-11"
        assert normalize_date_to_iso("11-Jul-2020") == "2020-07-11"
        assert normalize_date_to_iso("July 11, 2020") == "2020-07-11"

    def test_invalid_dates_return_none(self):
        assert normalize_date_to_iso(None) is None
        assert normalize_date_to_iso("") is None
        assert normalize_date_to_iso("UNKNOWN") is None
        assert normalize_date_to_iso("31-02-2020") is None  # Feb 31 does not exist
        assert normalize_date_to_iso("random text 12345") is None


class TestDateGroundingAndProvenance:
    """Test suite for OCR grounding verification."""

    @pytest.fixture
    def zetran_ocr_lines(self) -> list[OcrLine]:
        return [
            make_ocr_line("SAMPLE BILL", 1),
            make_ocr_line("Zetran Technologies Pvt., Ltd.", 2),
            make_ocr_line("Bill Number : BIL-00160", 4),
            make_ocr_line("Bill Date : 11-06-2020", 6),
            make_ocr_line("Phone: 76543210 wwwZettan", 7),
            make_ocr_line("Due Date : 11-07-2020", 8),
            make_ocr_line("PO No. : PO-0147", 9),
            make_ocr_line("TOTAL AMOUNT 29996.0", 34),
        ]

    def test_zetran_bill_date_grounding(self, zetran_ocr_lines):
        iso_val, line = verify_date_grounding(
            "2020-06-11", zetran_ocr_lines, field_type="issued_date"
        )
        assert iso_val == "2020-06-11"
        assert line is not None
        assert line.line_number == 6
        assert "Bill Date" in line.text

    def test_zetran_due_date_grounding(self, zetran_ocr_lines):
        iso_val, line = verify_date_grounding("2020-07-11", zetran_ocr_lines, field_type="due_date")
        assert iso_val == "2020-07-11"
        assert line is not None
        assert line.line_number == 8
        assert "Due Date" in line.text

    def test_reject_hallucinated_year(self, zetran_ocr_lines):
        # 2028 is not anywhere in the OCR lines
        iso_val, line = verify_date_grounding("2028-07-11", zetran_ocr_lines, field_type="due_date")
        assert iso_val is None
        assert line is None

    def test_fallback_extracts_from_ocr_when_llm_hallucinates(self, zetran_ocr_lines):
        # If LLM produces hallucinated 2028, grounding rejects it
        bad_val, bad_line = verify_date_grounding(
            "2028-07-11", zetran_ocr_lines, field_type="due_date"
        )
        assert bad_val is None

        # Fallback recovers genuine date directly from OCR evidence
        fb_due, fb_line = fallback_extract_date(zetran_ocr_lines, field_type="due_date")
        assert fb_due == "2020-07-11"
        assert fb_line.line_number == 8


class TestDateSequenceValidationCheck:
    """Test suite for DATE_SEQUENCE_CHECK in DeterministicValidationEngine."""

    def test_valid_date_sequence_passes(self):
        doc_id = uuid4()
        user_id = uuid4()
        engine = DeterministicValidationEngine()

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            issued_date=ExtractedField(
                field_key="issued_date",
                normalized_value="2020-06-11",
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="Bill Date : 11-06-2020",
                ),
            ),
            due_date=ExtractedField(
                field_key="due_date",
                normalized_value="2020-07-11",
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="Due Date : 11-07-2020",
                ),
            ),
            total_amount=ExtractedField(
                field_key="total_amount",
                normalized_value=29996.0,
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="29996.0",
                ),
            ),
        )

        check = engine.check_date_consistency(doc)
        assert check.status == ValidationStatus.PASS
        assert check.check_code == "DATE_SEQUENCE_CHECK"
        assert check.calculated_value == "2020-07-11"
        assert check.expected_value == ">= 2020-06-11"
        assert check.severity == ValidationSeverity.INFO

    def test_inverted_date_sequence_fails(self):
        doc_id = uuid4()
        user_id = uuid4()
        engine = DeterministicValidationEngine()

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            issued_date=ExtractedField(
                field_key="issued_date",
                normalized_value="2020-07-11",
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="2020-07-11",
                ),
            ),
            due_date=ExtractedField(
                field_key="due_date",
                normalized_value="2020-06-11",
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="2020-06-11",
                ),
            ),
            total_amount=ExtractedField(
                field_key="total_amount",
                normalized_value=100.0,
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="100.0",
                ),
            ),
        )

        check = engine.check_date_consistency(doc)
        assert check.status == ValidationStatus.FAIL
        assert check.calculated_value == "2020-06-11"
        assert check.severity == ValidationSeverity.WARNING

    def test_missing_date_is_inconclusive(self):
        doc_id = uuid4()
        user_id = uuid4()
        engine = DeterministicValidationEngine()

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            issued_date=ExtractedField(
                field_key="issued_date",
                normalized_value="2020-06-11",
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="2020-06-11",
                ),
            ),
            due_date=None,
            total_amount=ExtractedField(
                field_key="total_amount",
                normalized_value=100.0,
                confidence=0.98,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    raw_text="100.0",
                ),
            ),
        )

        check = engine.check_date_consistency(doc)
        assert check.status == ValidationStatus.INCONCLUSIVE
        assert check.calculated_value is None
