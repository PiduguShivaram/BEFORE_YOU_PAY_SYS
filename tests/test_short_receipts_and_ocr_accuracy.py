"""Comprehensive tests for OCR quality on short receipts, micro-slips, noise detection, and zero-fake-data integrity."""

from uuid import uuid4

import pytest

from before_you_pay.models.analysis import OCRQualityStatus
from before_you_pay.models.document import BoundingBox, OcrLine, OcrPage, OcrResult
from before_you_pay.services.llm_extraction import HybridLlmExtractionEngine
from before_you_pay.services.ocr import SpatialOcrEngine
from before_you_pay.services.ocr_quality import OCRQualityEvaluator


@pytest.fixture
def evaluator() -> OCRQualityEvaluator:
    return OCRQualityEvaluator()


def _make_ocr_result(text: str) -> OcrResult:
    doc_id = uuid4()
    page_id = uuid4()
    lines = []
    for idx, raw_line in enumerate(text.strip().splitlines(), 1):
        lines.append(
            OcrLine(
                line_id=uuid4(),
                document_id=doc_id,
                page_id=page_id,
                line_number=idx,
                text=raw_line,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=float(idx) * 0.05,
                    width=0.80,
                    height=0.04,
                ),
                confidence=0.95,
            )
        )
    page = OcrPage(
        page_id=page_id,
        document_id=doc_id,
        page_number=1,
        width=800,
        height=600,
        dpi=300,
        lines=lines,
    )
    return OcrResult(
        document_id=doc_id,
        pages=[page],
        engine_name="test_engine",
        engine_version="1.0",
    )


class TestShortReceiptsAndOcrAccuracy:
    def test_short_receipt_total_50_not_falsely_rejected(
        self, evaluator: OCRQualityEvaluator
    ) -> None:
        """Micro-receipt 'Total: ₹50' has explicit financial anchors and must NOT be marked UNRELIABLE."""
        res = _make_ocr_result("Total: ₹50")
        quality = evaluator.evaluate(res)
        assert quality.status != OCRQualityStatus.UNRELIABLE
        assert quality.score >= 0.70

    def test_short_receipt_parking_fee_not_falsely_rejected(
        self, evaluator: OCRQualityEvaluator
    ) -> None:
        """Parking ticket 'Parking Fee Rs 50' must be evaluated as readable financial text."""
        res = _make_ocr_result("Parking Fee Rs 50")
        quality = evaluator.evaluate(res)
        assert quality.status in (OCRQualityStatus.GOOD, OCRQualityStatus.MODERATE)

    def test_short_receipt_toll_not_falsely_rejected(self, evaluator: OCRQualityEvaluator) -> None:
        """Toll slip 'Toll ₹65' must be accepted."""
        res = _make_ocr_result("Toll ₹65")
        quality = evaluator.evaluate(res)
        assert quality.status != OCRQualityStatus.UNRELIABLE

    def test_short_receipt_fuel_not_falsely_rejected(self, evaluator: OCRQualityEvaluator) -> None:
        """Fuel slip 'Fuel 500.00' must be accepted."""
        res = _make_ocr_result("Fuel 500.00")
        quality = evaluator.evaluate(res)
        assert quality.status != OCRQualityStatus.UNRELIABLE

    def test_pure_noise_rejected_as_unreliable(self, evaluator: OCRQualityEvaluator) -> None:
        """Punctuation noise '~~~ !!! ???' must be marked UNRELIABLE."""
        res = _make_ocr_result("~~~ !!! ???")
        quality = evaluator.evaluate(res)
        assert quality.status == OCRQualityStatus.UNRELIABLE
        assert quality.score <= 0.30

    def test_sparse_non_financial_noise_rejected(self, evaluator: OCRQualityEvaluator) -> None:
        """Short non-financial snippet without anchors or currency must be UNRELIABLE."""
        res = _make_ocr_result("just hello")
        quality = evaluator.evaluate(res)
        assert quality.status == OCRQualityStatus.UNRELIABLE

    def test_meaningful_financial_content_lines_accepts_small_charges(self) -> None:
        """SpatialOcrEngine._has_meaningful_financial_content_lines accepts single/double digit charges."""
        doc_id = uuid4()
        line = OcrLine(
            line_id=uuid4(),
            document_id=doc_id,
            page_id=uuid4(),
            line_number=1,
            text="Toll: ₹65",
            bounding_box=BoundingBox(x=0.0, y=0.0, width=0.5, height=0.05),
            confidence=0.95,
        )
        assert SpatialOcrEngine._has_meaningful_financial_content_lines([line]) is True

    def test_missing_unit_price_is_none_not_zero(self) -> None:
        """When an invoice does not state a unit price, unit_price field must be None, never ₹0."""
        service = HybridLlmExtractionEngine()
        doc_id = uuid4()
        ocr_result = _make_ocr_result("Service Fee: 500.00\nTotal: 500.00")

        # Mock parsed json simulating LLM output where unit_price was not printed on document
        parsed_llm = {
            "document_type": "invoice",
            "invoice_number": "INV-100",
            "currency": "INR",
            "line_items": [
                {
                    "description": "Consulting Advisory Session",
                    "quantity": 1,
                    "unit_price": None,  # Omitted on document
                    "total_price": 500.0,
                    "mrp": None,
                    "discount": None,
                }
            ],
            "cost_breakdown": [],
            "stated_total": 500.0,
        }

        user_id = uuid4()
        extracted = service._build_extracted_document_from_json(
            document_id=doc_id,
            user_id=user_id,
            ocr_result=ocr_result,
            parsed=parsed_llm,
        )

        assert len(extracted.line_items) == 1
        item = extracted.line_items[0]
        assert item.total_price.normalized_value == 500.0
        # Zero fake data policy: missing unit price must be None, NOT 0.0
        assert item.unit_price is None
