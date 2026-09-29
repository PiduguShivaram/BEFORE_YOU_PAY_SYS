"""Deterministic regression tests covering the 4 audit test failure root causes.

All tests in this module run offline with zero external network / API dependency.
"""

from uuid import uuid4

from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    DocumentClassification,
    OcrLine,
    OcrPage,
    OcrResult,
)
from before_you_pay.services.extraction import (
    FinancialExtractionEngine,
    is_inline_labeled_product_line,
    is_table_header_line,
)
from before_you_pay.services.financial_taxonomy import (
    ComponentCategory,
    classify_component_name,
)
from before_you_pay.services.validation import DeterministicValidationEngine


def make_ocr_line(doc_id, page_id, idx, text):
    return OcrLine(
        line_id=uuid4(),
        page_id=page_id,
        document_id=doc_id,
        line_number=idx,
        text=text,
        raw_text=text,
        bounding_box=BoundingBox(
            x=0.05,
            y=0.05 * idx,
            width=0.90,
            height=0.03,
            coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
        ),
        confidence=0.95,
    )


def test_regression_inline_labeled_product_line_not_discarded_as_summary():
    """Bug 1: Product row containing 'Discount' and 'Final line amount' must not be discarded.

    _is_metadata_line and summary-label filters must treat inline labeled rows as products.
    """
    line_text = "Pro Headphones Rate/Item: $100.00 Discount: 10% Final line amount: $90.00"
    assert is_inline_labeled_product_line(line_text) is True
    assert is_table_header_line(line_text) is False

    doc_id = uuid4()
    page_id = uuid4()
    lines = [
        make_ocr_line(doc_id, page_id, 1, "Acme Audio Store"),
        make_ocr_line(doc_id, page_id, 2, line_text),
        make_ocr_line(doc_id, page_id, 3, "Subtotal: $90.00"),
        make_ocr_line(doc_id, page_id, 4, "Total Amount: $90.00"),
    ]
    ocr_res = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=800,
                height=1000,
                lines=lines,
            )
        ],
        engine_name="test_engine",
    )

    extractor = FinancialExtractionEngine()
    doc = extractor.extract(doc_id, uuid4(), ocr_res)

    assert len(doc.line_items) == 1
    item = doc.line_items[0]
    assert "Pro Headphones" in item.description.normalized_value
    assert item.discount is not None
    assert float(item.discount.normalized_value) == 10.0
    assert float(item.total_price.normalized_value) == 90.0


def test_regression_sample_bill_three_items_extracted_and_reconciled():
    """Bug 2: 3 inline labeled items extracted without dropping due to 'Discount' in line."""
    doc_id = uuid4()
    page_id = uuid4()
    raw_lines = [
        "Samsung A30 MRP = ₹17,999 Rate/Item = ₹16,999 Discount = ₹1,000 Final line amount = ₹15,999",
        "Samsung Buds MRP = ₹12,999 Rate/Item = ₹12,499 Discount = ₹500 Final line amount = ₹11,999",
        "Boat Rockers 510 MRP = ₹2,499 Rate/Item = ₹500 Discount = ₹500 Final line amount = ₹1,499",
        "Taxable Amount = ₹29,497",
        "Subtotal = ₹29,497",
        "Discount = ₹2,000",
        "Shipping Details = ₹499",
        "Amount paid = ₹0",
        "Balance Due = ₹29,996",
        "TOTAL AMOUNT = ₹29,996",
    ]
    lines = [make_ocr_line(doc_id, page_id, i + 1, txt) for i, txt in enumerate(raw_lines)]
    ocr_res = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=800,
                height=1000,
                lines=lines,
            )
        ],
        engine_name="test_engine",
    )

    extractor = FinancialExtractionEngine()
    doc = extractor.extract(doc_id, uuid4(), ocr_res)

    assert doc.currency == "INR"
    assert len(doc.line_items) == 3
    descriptions = [li.description.normalized_value for li in doc.line_items]
    assert descriptions == ["Samsung A30", "Samsung Buds", "Boat Rockers 510"]

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    checks_by_code = {c.check_code: c for c in checks}
    assert checks_by_code["ARITHMETIC_LINE_ITEMS_SUM"].status.value == "PASS"


def test_regression_handwritten_quotation_classification_and_taxonomy():
    """Bug 3: Handwritten vehicle estimate with 'Exshorum' classified as QUOTATION not OTHER."""
    cat, norm_label, nature, opt, exp = classify_component_name("Exshorum = 1149900")
    assert cat == ComponentCategory.EX_SHOWROOM_PRICE
    assert norm_label == "Ex-showroom price"

    doc_id = uuid4()
    page_id = uuid4()
    raw_lines = [
        "Exshorum = 1149900",
        "TCS = 11499",
        "Insu. = 45000",
        "R.C. = 76250",
        "Extended warnty = 15750",
        "Temp+HSRP = 1000",
        "Offer = -50000",
        "Extra offer = -20000",
        "Total = 1228399",
    ]
    lines = [make_ocr_line(doc_id, page_id, i + 1, txt) for i, txt in enumerate(raw_lines)]
    ocr_res = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=800,
                height=1000,
                lines=lines,
            )
        ],
        engine_name="test_engine",
    )

    extractor = FinancialExtractionEngine()
    doc = extractor.extract(doc_id, uuid4(), ocr_res)

    assert doc.document_type == DocumentClassification.QUOTATION
    assert len(doc.cost_breakdown) >= 6
    assert float(doc.total_amount.normalized_value) > 1000000.0


def test_regression_mrp_preservation_and_no_hallucination():
    """Bug 4: Explicit MRP and rate columns are preserved with distinct values."""
    doc_id = uuid4()
    page_id = uuid4()
    raw_lines = [
        "Zetran Technologies Pvt., Ltd.",
        "Bill Date : 11-06-2020",
        "Due Date : 11-07-2020",
        "ITEMS HSN QTY MRP RATE/ITEM DISCOUNT TAX AMOUNT",
        "Samsung A30 MRP = ₹17,999 Rate/Item = ₹16,999 Discount = ₹1,000 Final line amount = ₹15,999",
        "Samsung Buds MRP = ₹12,999 Rate/Item = ₹12,499 Discount = ₹500 Final line amount = ₹11,999",
        "Boat Rockers 510 MRP = ₹2,499 Rate/Item = ₹500 Discount = ₹500 Final line amount = ₹1,499",
        "Subtotal = ₹29,497",
        "Discount = ₹2,000",
        "TOTAL AMOUNT = ₹29,996",
    ]
    lines = [make_ocr_line(doc_id, page_id, i + 1, txt) for i, txt in enumerate(raw_lines)]
    ocr_res = OcrResult(
        document_id=doc_id,
        pages=[
            OcrPage(
                page_id=page_id,
                document_id=doc_id,
                page_number=1,
                width=800,
                height=1000,
                lines=lines,
            )
        ],
        engine_name="test_engine",
    )

    extractor = FinancialExtractionEngine()
    doc = extractor.extract(doc_id, uuid4(), ocr_res)

    assert doc.vendor_name is not None
    assert doc.vendor_name.normalized_value == "Zetran Technologies Pvt., Ltd."
    items = {li.description.normalized_value: li for li in doc.line_items}
    a30 = items["Samsung A30"]
    assert a30.mrp is not None and float(a30.mrp.normalized_value) == 17999.0
    assert a30.unit_price is not None and float(a30.unit_price.normalized_value) == 16999.0
    assert a30.discount is not None and float(a30.discount.normalized_value) == 1000.0
    assert float(a30.total_price.normalized_value) == 15999.0
