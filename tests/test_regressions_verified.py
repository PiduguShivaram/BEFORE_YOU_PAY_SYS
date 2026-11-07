"""Regression test suite for verified defect fixes:
1. Issue A: Line-item tax 0.00 not corrupting unit rate / unit price.
2. Issue B: OCR hallucination on noise image properly classified as UNRELIABLE.
"""

import io
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw

from before_you_pay.models import (
    AnalysisState,
    BoundingBox,
    CoordinateUnit,
    DocumentClassification,
    OcrLine,
    OcrPage,
    OCRQualityStatus,
    OcrResult,
)
from before_you_pay.services.llm_extraction import HybridLlmExtractionEngine
from before_you_pay.services.ocr_quality import OCRQualityEvaluator
from before_you_pay.services.pipeline import PipelineService


def test_line_item_tax_zero_does_not_overwrite_rate():
    """Verify that a 0.00 tax column in an item row does not overwrite non-zero unit rate."""
    doc_id = uuid4()
    page_id = uuid4()
    bbox = BoundingBox(
        x=0.05,
        y=0.5,
        width=0.9,
        height=0.02,
        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
    )

    header_line = OcrLine(
        line_id=uuid4(),
        page_id=page_id,
        document_id=doc_id,
        line_number=1,
        text="Item Description HSN/SAC Qty MRP Rate Discount Tax Total",
        confidence=0.95,
        bounding_box=bbox,
    )

    ocr_line = OcrLine(
        line_id=uuid4(),
        page_id=page_id,
        document_id=doc_id,
        line_number=2,
        text="Boat Rockers 510 682145 1 ₹2,499 ₹ 500 0.00 ₹ 1,499",
        confidence=0.92,
        bounding_box=bbox,
    )

    total_line = OcrLine(
        line_id=uuid4(),
        page_id=page_id,
        document_id=doc_id,
        line_number=3,
        text="Total ₹ 1,499",
        confidence=0.95,
        bounding_box=bbox,
    )

    ocr_result = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=1000,
                height=1400,
                lines=[header_line, ocr_line, total_line],
            )
        ],
        engine_name="test",
    )

    extractor = HybridLlmExtractionEngine()
    # Test deterministic fallback extraction directly
    doc = extractor.fallback_engine.extract(
        document_id=doc_id,
        user_id=uuid4(),
        ocr_result=ocr_result,
        document_type_hint=DocumentClassification.BILL,
    )

    assert len(doc.line_items) == 1
    item = doc.line_items[0]
    assert "Boat Rockers" in item.description.normalized_value
    assert item.unit_price is not None
    assert float(item.unit_price.normalized_value) > 0.0
    assert float(item.unit_price.normalized_value) in (500.0, 1999.0)
    assert float(item.total_price.normalized_value) == 1499.0


def test_noise_without_financial_anchors_evaluated_unreliable():
    """Verify that random punctuation/noise text without financial anchors evaluates to UNRELIABLE."""
    evaluator = OCRQualityEvaluator()
    doc_id = uuid4()
    page_id = uuid4()
    bbox = BoundingBox(
        x=0.1,
        y=0.1,
        width=0.8,
        height=0.05,
        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
    )

    noise_lines = [
        OcrLine(
            line_id=uuid4(),
            page_id=page_id,
            document_id=doc_id,
            line_number=1,
            text="~~~ !!! ??? ........ HI 222",
            confidence=0.45,
            bounding_box=bbox,
        )
    ]
    ocr_result = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=600,
                height=400,
                lines=noise_lines,
            )
        ],
        engine_name="test",
    )

    quality = evaluator.evaluate(ocr_result)
    assert quality.status == OCRQualityStatus.UNRELIABLE
    assert quality.score <= 0.30


@pytest.mark.anyio
async def test_noise_image_pipeline_results_in_unreliable_or_unreadable():
    """Verify end-to-end pipeline on noise image terminates in OCR_UNRELIABLE or DOCUMENT_UNREADABLE."""
    pipeline = PipelineService()
    doc_id = uuid4()
    user_id = uuid4()

    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "~~~ !!! ???", fill=(130, 130, 130))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    res = await pipeline.run_full_pipeline(
        document_id=doc_id,
        user_id=user_id,
        file_bytes=img_bytes,
        mime_type="image/png",
        document_type_hint=DocumentClassification.OTHER,
    )

    assert res.analysis_state in (
        AnalysisState.OCR_UNRELIABLE,
        AnalysisState.DOCUMENT_UNREADABLE,
    )
