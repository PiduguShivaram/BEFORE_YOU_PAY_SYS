import os
from uuid import uuid4
import pytest
from before_you_pay.models import ValidationStatus
from before_you_pay.services.pipeline import PipelineService

@pytest.mark.anyio
async def test_zetran_bill_regression():
    """Mandatory end-to-end regression test for the Zetran bill."""
    fixture_path = os.path.join(os.path.dirname(__file__), "assets", "sample-bill-format-769x1024.png")
    assert os.path.exists(fixture_path), f"Fixture missing at {fixture_path}"

    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    pipeline = PipelineService()
    doc_id = uuid4()
    user_id = uuid4()

    result = await pipeline.run_full_pipeline(
        document_id=doc_id,
        user_id=user_id,
        file_bytes=file_bytes,
        mime_type="image/png",
    )

    # 1. OCR verification
    assert len(result.ocr_lines) > 20, f"Expected >20 OCR lines, got {len(result.ocr_lines)}"
    assert result.ocr_quality is not None
    assert result.ocr_quality.status.value != "unreliable"

    # 2. Document extraction
    doc = result.document
    assert doc is not None

    # Check grand total and line item sum
    assert doc.total_amount is not None
    assert float(doc.total_amount.normalized_value) == 29996.0

    # 3. Deterministic Validation checks
    checks_by_code = {c.check_code: c for c in result.validation_checks}

    # Grand total arithmetic consistency must PASS
    total_chk = checks_by_code.get("ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_chk is not None
    assert total_chk.status == ValidationStatus.PASS

    # Boat Rockers line item inconsistency must trigger FAIL
    boat_chk = checks_by_code.get("LINE_ITEM_EXTENSION_MATCH")
    assert boat_chk is not None
    assert boat_chk.status == ValidationStatus.FAIL
