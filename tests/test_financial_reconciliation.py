"""Comprehensive financial reconciliation and regression tests covering Tests 1 to 10."""

from uuid import uuid4

from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    DecisionStatus,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OcrLine,
    OcrPage,
    OcrResult,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.extraction import FinancialExtractionEngine, detect_currency
from before_you_pay.services.result import ResultAggregatorService
from before_you_pay.services.validation import DeterministicValidationEngine


def make_prov(raw_text: str = "test") -> FieldProvenance:
    return FieldProvenance(
        document_id=uuid4(),
        page_id=uuid4(),
        ocr_line_ids=[uuid4()],
        bounding_box=BoundingBox(
            x=0.1,
            y=0.1,
            width=0.8,
            height=0.05,
            coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
        ),
        raw_text=raw_text,
    )


def make_field(
    key: str, val: float | str, curr: str | None = None, raw: str = ""
) -> ExtractedField:
    return ExtractedField(
        field_id=uuid4(),
        field_key=key,
        normalized_value=val,
        unit_or_currency=curr,
        confidence=0.98,
        provenance=make_prov(raw or str(val)),
    )


def make_item(
    desc: str,
    total: float,
    curr: str | None = None,
    mrp: float | None = None,
    disc: float | None = None,
) -> LineItem:
    return LineItem(
        item_id=uuid4(),
        description=make_field("item_desc", desc, raw=desc),
        total_price=make_field("item_total", total, curr, raw=str(total)),
        mrp=make_field("item_mrp", mrp, curr, raw=str(mrp)) if mrp is not None else None,
        discount=make_field("item_disc", disc, curr, raw=str(disc)) if disc is not None else None,
    )


def test_1_exact_sample_bill_reconciliation():
    """TEST 1: Exact sample bill:

    Items: 15999 + 11999 + 1499 = 29497
    Shipping: 499
    Total: 29996
    Expected: PASS, No Grand Total Mismatch.
    """
    items = [
        make_item("Samsung A30", 15999.0, "INR", mrp=17999.0, disc=1000.0),
        make_item("Samsung Buds", 11999.0, "INR", mrp=12999.0, disc=500.0),
        make_item("Boat Rockers 510", 1499.0, "INR", mrp=2499.0, disc=500.0),
    ]
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        document_type=DocumentClassification.BILL,
        currency="INR",
        line_items=items,
        subtotal=make_field("subtotal", 29497.0, "INR"),
        shipping_amount=make_field("shipping_amount", 499.0, "INR", raw="Shipping Details: ₹499"),
        discount_amount=make_field("discount_amount", 2000.0, "INR", raw="Discount = ₹2,000"),
        tax_amount=make_field("tax_amount", 0.0, "INR", raw="CGST = ₹0 SGST = ₹0"),
        amount_paid=make_field("amount_paid", 0.0, "INR", raw="Amount paid = ₹0"),
        balance_due=make_field("balance_due", 29996.0, "INR", raw="Balance Due = ₹29,996"),
        total_amount=make_field("total_amount", 29996.0, "INR", raw="TOTAL AMOUNT = ₹29,996"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.severity == ValidationSeverity.INFO
    assert "matches" in total_check.message.lower()

    # Verify result aggregator produces NO CRITICAL WARNING
    aggregator = ResultAggregatorService()
    result = aggregator.compile_result(doc.document_id, doc.user_id, doc, [], checks)

    assert result.summary.overall_status != DecisionStatus.CRITICAL_WARNING
    assert not any(f.label == "Grand Total Mismatch" for f in result.flags)


def test_2_shipping_with_different_amount():
    """TEST 2: Shipping with different amount: Items = 10000, Shipping = 500, Total = 10500 -> PASS."""
    items = [make_item("Services", 10000.0, "USD")]
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="USD",
        line_items=items,
        subtotal=make_field("subtotal", 10000.0, "USD"),
        shipping_amount=make_field("shipping_amount", 500.0, "USD"),
        total_amount=make_field("total_amount", 10500.0, "USD"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.calculated_value == 10500.0


def test_3_actual_mismatch():
    """TEST 3: Actual mismatch: Items = 10000, Shipping = 500, Total = 11000 -> MISMATCH."""
    items = [make_item("Services", 10000.0, "USD")]
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="USD",
        line_items=items,
        subtotal=make_field("subtotal", 10000.0, "USD"),
        shipping_amount=make_field("shipping_amount", 500.0, "USD"),
        total_amount=make_field("total_amount", 11000.0, "USD"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.FAIL
    assert total_check.severity == ValidationSeverity.CRITICAL
    assert total_check.absolute_delta == 500.0
    assert "Grand total mismatch" in total_check.message


def test_4_no_shipping_present_remains_null():
    """TEST 4: No shipping present: Items = 10000, Tax = 1800, Total = 11800 -> PASS.

    Shipping remains unknown/null, not fabricated as 0.
    """
    items = [make_item("Consulting", 10000.0, "INR")]
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="INR",
        line_items=items,
        subtotal=make_field("subtotal", 10000.0, "INR"),
        tax_amount=make_field("tax_amount", 1800.0, "INR"),
        shipping_amount=None,  # Unknown / not found
        total_amount=make_field("total_amount", 11800.0, "INR"),
    )

    assert doc.shipping_amount is None

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.calculated_value == 11800.0


def test_5_line_item_discounts_not_double_subtracted():
    """TEST 5: Line-item discounts already incorporated into final line amounts are not subtracted twice."""
    items = [
        make_item("Item A", 900.0, "INR", mrp=1000.0, disc=100.0),
        make_item("Item B", 1900.0, "INR", mrp=2000.0, disc=100.0),
    ]
    # Items sum to 2800. Document lists Discount = 200 (summary of line discounts).
    # Total = 2800.
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="INR",
        line_items=items,
        subtotal=make_field("subtotal", 2800.0, "INR"),
        discount_amount=make_field("discount_amount", 200.0, "INR"),
        total_amount=make_field("total_amount", 2800.0, "INR"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.calculated_value == 2800.0


def test_6_explicit_document_level_discount_applied_once():
    """TEST 6: Explicit document-level discount is applied exactly once."""
    items = [
        make_item("Item A", 1000.0, "USD"),
        make_item("Item B", 2000.0, "USD"),
    ]
    # Base is 3000. Promo coupon discount is 500. Total = 2500.
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="USD",
        line_items=items,
        subtotal=make_field("subtotal", 3000.0, "USD"),
        discount_amount=make_field("discount_amount", 500.0, "USD"),
        total_amount=make_field("total_amount", 2500.0, "USD"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.calculated_value == 2500.0


def test_7_currency_inr_preserved():
    """TEST 7: Input uses ₹ / INR. Expected output: ₹ / INR, never $."""
    text = "TOTAL AMOUNT = ₹29,996"
    curr = detect_currency(text)
    assert curr == "INR"

    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="INR",
        total_amount=make_field("total_amount", 29996.0, "INR", raw=text),
    )
    assert doc.currency == "INR"
    assert doc.currency != "USD"


def test_8_currency_usd_preserved():
    """TEST 8: Input uses $. Expected: USD."""
    text = "TOTAL AMOUNT = $550.00"
    curr = detect_currency(text)
    assert curr == "USD"

    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="USD",
        total_amount=make_field("total_amount", 550.0, "USD", raw=text),
    )
    assert doc.currency == "USD"


def test_9_amount_paid_and_balance_due():
    """TEST 9: Total = 10000, Paid = 3000, Balance = 7000. Expected: Balance due = 7000."""
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="INR",
        amount_paid=make_field("amount_paid", 3000.0, "INR"),
        balance_due=make_field("balance_due", 7000.0, "INR"),
        total_amount=make_field("total_amount", 10000.0, "INR"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    pay_check = next(c for c in checks if c.check_code == "PAYMENT_STATUS_RECONCILIATION")
    assert pay_check.status == ValidationStatus.PASS
    assert "7,000.00 remains payable" in pay_check.message


def test_10_shipping_tax_and_fees_reconciliation():
    """TEST 10: Shipping + tax + fees reconciliation across multiple charge types."""
    items = [make_item("Hardware", 5000.0, "INR")]
    fee1 = make_field("platform_fee", 150.0, "INR")
    fee2 = make_field("handling_fee", 50.0, "INR")

    # 5000 + 400 (shipping) + 900 (tax 18%) + 200 (fees) = 6500.
    doc = StructuredFinancialDocument(
        document_id=uuid4(),
        user_id=uuid4(),
        currency="INR",
        line_items=items,
        subtotal=make_field("subtotal", 5000.0, "INR"),
        shipping_amount=make_field("shipping_amount", 400.0, "INR"),
        tax_amount=make_field("tax_amount", 900.0, "INR"),
        fees=[fee1, fee2],
        total_amount=make_field("total_amount", 6500.0, "INR"),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)
    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.calculated_value == 6500.0


def test_sample_bill_end_to_end_extraction_and_reconciliation():
    """Test full OCR extraction and validation with the exact sample bill raw text."""
    sample_ocr_lines = [
        "Samsung A30 MRP = ₹17,999 Rate/Item = ₹16,999 Discount = ₹1,000 Final line amount = ₹15,999",
        "Samsung Buds MRP = ₹12,999 Rate/Item = ₹12,499 Discount = ₹500 Final line amount = ₹11,999",
        "Boat Rockers 510 MRP = ₹2,499 Rate/Item = ₹500 Discount = ₹500 Final line amount = ₹1,499",
        "Taxable Amount = ₹29,497",
        "CGST = ₹0",
        "SGST = ₹0",
        "Subtotal = ₹29,497",
        "Discount = ₹2,000",
        "Shipping Details = ₹499",
        "Amount paid = ₹0",
        "Balance Due = ₹29,996",
        "TOTAL AMOUNT = ₹29,996",
    ]

    doc_id = uuid4()
    page_id = uuid4()
    ocr_lines = []
    for idx, text in enumerate(sample_ocr_lines):
        ocr_lines.append(
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=idx + 1,
                text=text,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=0.05 * (idx + 1),
                    width=0.9,
                    height=0.04,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.99,
            )
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
                lines=ocr_lines,
            )
        ],
        engine_name="test_ocr",
    )

    user_id = uuid4()
    extractor = FinancialExtractionEngine()
    doc = extractor.extract(doc_id, user_id, ocr_result)

    # 1. Verify Extracted Currency
    assert doc.currency == "INR"

    # 2. Verify Line Items
    assert len(doc.line_items) == 3
    assert doc.line_items[0].description.normalized_value == "Samsung A30"
    assert doc.line_items[0].total_price.normalized_value == 15999.0
    assert doc.line_items[1].description.normalized_value == "Samsung Buds"
    assert doc.line_items[1].total_price.normalized_value == 11999.0
    assert doc.line_items[2].description.normalized_value == "Boat Rockers 510"
    assert doc.line_items[2].total_price.normalized_value == 1499.0

    # 3. Verify Subtotal, Shipping, Tax, Total, Paid, Balance Due
    assert doc.subtotal is not None
    assert doc.subtotal.normalized_value == 29497.0

    assert doc.shipping_amount is not None
    assert doc.shipping_amount.normalized_value == 499.0
    assert "499" in doc.shipping_amount.provenance.raw_text

    assert doc.total_amount.normalized_value == 29996.0

    assert doc.amount_paid is not None
    assert doc.amount_paid.normalized_value == 0.0

    assert doc.balance_due is not None
    assert doc.balance_due.normalized_value == 29996.0

    # 4. Verify Deterministic Validation
    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
    assert total_check.status == ValidationStatus.PASS
    assert total_check.severity == ValidationSeverity.INFO

    # 5. Verify Result Aggregator
    aggregator = ResultAggregatorService()
    final_res = aggregator.compile_result(doc_id, user_id, doc, [], checks)

    # NO FALSE Grand Total Mismatch
    assert not any(f.label == "Grand Total Mismatch" for f in final_res.flags)
    assert final_res.summary.overall_status != DecisionStatus.CRITICAL_WARNING
