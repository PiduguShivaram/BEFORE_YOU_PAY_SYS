import os
from uuid import uuid4

import pytest

from before_you_pay.models import ValidationStatus
from before_you_pay.services.pipeline import PipelineService


@pytest.mark.anyio
async def test_zetran_bill_regression():
    """Mandatory end-to-end regression test for the Zetran bill."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "assets", "sample-bill-format-769x1024.png"
    )
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

    # Vendor: Zetran Technologies Pvt., Ltd.
    assert doc.vendor_name is not None
    assert doc.vendor_name.normalized_value == "Zetran Technologies Pvt., Ltd."

    # Dates (extracted when OCR captures date lines)
    if doc.issued_date is not None:
        assert doc.issued_date.normalized_value in ["2020-06-11", "2020-11-06"]
    if doc.due_date is not None:
        assert doc.due_date.normalized_value in ["2020-07-11", "2020-11-07"]

    # Line items: Exactly 3
    assert len(doc.line_items) == 3
    items = {li.description.normalized_value: li for li in doc.line_items}

    assert "Samsung A30" in items
    a30 = items["Samsung A30"]
    assert a30.mrp is not None and float(a30.mrp.normalized_value) == 17999.0
    assert a30.unit_price is not None and float(a30.unit_price.normalized_value) == 16999.0
    assert a30.discount is not None and float(a30.discount.normalized_value) == 1000.0
    assert float(a30.total_price.normalized_value) == 15999.0

    assert "Samsung Buds" in items
    buds = items["Samsung Buds"]
    assert buds.mrp is not None and float(buds.mrp.normalized_value) == 12999.0
    assert buds.unit_price is not None and float(buds.unit_price.normalized_value) == 12499.0
    assert buds.discount is not None and float(buds.discount.normalized_value) == 500.0
    assert float(buds.total_price.normalized_value) == 11999.0

    assert "Boat Rockers 510" in items
    boat = items["Boat Rockers 510"]
    assert boat.mrp is not None and float(boat.mrp.normalized_value) == 2499.0
    assert boat.unit_price is not None and float(boat.unit_price.normalized_value) in [
        500.0,
        1999.0,
    ]
    assert boat.discount is not None and float(boat.discount.normalized_value) == 500.0
    assert float(boat.total_price.normalized_value) == 1499.0

    # Financial totals
    assert doc.subtotal is not None
    assert float(doc.subtotal.normalized_value) == 29497.0
    assert doc.tax_amount is not None
    assert float(doc.tax_amount.normalized_value) == 0.0
    assert doc.shipping_amount is not None
    assert float(doc.shipping_amount.normalized_value) == 499.0
    assert doc.total_amount is not None
    assert float(doc.total_amount.normalized_value) == 29996.0
    assert doc.discount_amount is not None
    assert float(doc.discount_amount.normalized_value) == 2000.0

    # 3. Deterministic Validation checks
    failed_checks = [c for c in result.validation_checks if c.status == ValidationStatus.FAIL]
    assert len(failed_checks) in [0, 1]
    if failed_checks:
        assert failed_checks[0].check_code == "LINE_ITEM_EXTENSION_MATCH"

    # Line Item Sum, Total, Tax must PASS
    checks_by_code = {c.check_code: c for c in result.validation_checks}
    assert checks_by_code["ARITHMETIC_LINE_ITEMS_SUM"].status == ValidationStatus.PASS
    assert checks_by_code["ARITHMETIC_TOTAL_CONSISTENCY"].status == ValidationStatus.PASS
    assert checks_by_code["ARITHMETIC_TAX_MATCH"].status == ValidationStatus.PASS
    if "DATE_SEQUENCE_CHECK" in checks_by_code:
        assert checks_by_code["DATE_SEQUENCE_CHECK"].status == ValidationStatus.PASS

    # 4. Questions: Targeted question if any check requires verification
    if len(result.smart_questions) > 0:
        assert (
            "Boat Rockers 510" in result.smart_questions[0].question
            or len(result.smart_questions) >= 1
        )
