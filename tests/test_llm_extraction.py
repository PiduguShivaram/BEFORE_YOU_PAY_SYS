"""Unit tests for HybridLlmExtractionEngine with Groq failover pool."""

from uuid import uuid4

import pytest

from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    OcrLine,
    OcrPage,
    OcrResult,
)
from before_you_pay.services.llm_extraction import HybridLlmExtractionEngine
from before_you_pay.services.llm_pool import GroqKeyManager


def make_dummy_ocr(text_lines: list[str]) -> OcrResult:
    doc_id = uuid4()
    page_id = uuid4()
    lines = []
    for i, t in enumerate(text_lines):
        lines.append(
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=i + 1,
                text=t,
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.05 * (i + 1),
                    width=0.8,
                    height=0.03,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.98,
            )
        )
    page = OcrPage(
        page_id=page_id, document_id=doc_id, page_number=1, width=1000, height=1400, lines=lines
    )
    return OcrResult(document_id=doc_id, pages=[page], engine_name="mock_ocr")


def test_hybrid_extraction_with_real_groq():
    """Verify live extraction with real Groq failover keys."""
    key_mgr = GroqKeyManager()
    if key_mgr.key_count == 0:
        pytest.skip("No Groq keys configured.")

    engine = HybridLlmExtractionEngine(key_manager=key_mgr)
    ocr = make_dummy_ocr(
        [
            "Apex Cloud Services Inc.",
            "Invoice #9921",
            "Date: 2024-11-01",
            "Server Hosting Dedicated 1x $450.00",
            "Database Backup Addon 1x $50.00",
            "Subtotal: $500.00",
            "Tax (10%): $50.00",
            "Total: $550.00",
            "Auto-renews annually unless cancelled 30 days prior.",
        ]
    )

    user_id = uuid4()
    doc, provider = engine.extract(ocr.document_id, user_id, ocr)

    assert "GEMINI" in provider or "GROQ" in provider or "FALLBACK" in provider
    assert doc.vendor_name is not None
    assert "Apex Cloud" in str(doc.vendor_name.normalized_value)
    assert len(doc.line_items) >= 2
    assert doc.total_amount is not None
    assert (
        float(doc.total_amount.normalized_value) == 550.0
        or float(doc.total_amount.normalized_value) == 500.0
    )


def test_hybrid_extraction_falls_back_when_offline():
    """Verify graceful degradation to regex extractor when pool has no keys."""
    empty_pool = GroqKeyManager(api_keys=[], model="test")
    engine = HybridLlmExtractionEngine(key_manager=empty_pool)

    ocr = make_dummy_ocr(
        [
            "Invoice #101",
            "Acme Corp",
            "Web Development $1000.00",
            "Total: $1000.00",
        ]
    )
    doc, provider = engine.extract(ocr.document_id, uuid4(), ocr)
    assert provider == "FALLBACK_DETERMINISTIC_REGEX"
    assert doc.vendor_name is not None
