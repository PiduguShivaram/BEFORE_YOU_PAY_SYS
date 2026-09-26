from uuid import uuid4

from before_you_pay.models import BoundingBox, CoordinateUnit, OcrLine, OcrPage, OcrResult
from before_you_pay.services.ocr_quality import OCRQualityEvaluator

doc_id = uuid4()
page_id = uuid4()


def make_page(lines_text):
    lines = []
    for idx, t in enumerate(lines_text, 1):
        lines.append(
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=idx,
                text=t,
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.1 * idx,
                    width=0.8,
                    height=0.05,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.95,
            )
        )
    return OcrPage(
        page_id=page_id, document_id=doc_id, page_number=1, width=1080, height=1920, lines=lines
    )


evaluator = OCRQualityEvaluator()

# Test 1: Problematic Garbage OCR
garbage_lines = ["OTA C", "0dAe A 0 000", "0d/q/ex S0 00b", "Posted in r/CarsIndia reddit"]
res1 = evaluator.evaluate(
    OcrResult(document_id=doc_id, pages=[make_page(garbage_lines)], engine_name="test")
)
print("=== Garbage OCR Quality ===")
print("Status:", res1.status)
print("Score:", res1.score)
print("Reasons:", res1.reasons)
print("Garbage ratio:", res1.garbage_token_ratio)

# Test 2: Clean Invoice OCR
good_lines = [
    "ZETRAN TECHNOLOGIES PVT LTD",
    "TAX INVOICE",
    "Invoice No: INV-2024-001 Date: 12/03/2024",
    "Item 1: Professional IT Consulting 10 hrs @ 500.00 = 5000.00",
    "Subtotal: 5000.00",
    "CGST 9%: 450.00",
    "SGST 9%: 450.00",
    "Total Payable: 5900.00",
    "Payment due within 15 days of invoice date.",
]
res2 = evaluator.evaluate(
    OcrResult(document_id=doc_id, pages=[make_page(good_lines)], engine_name="test")
)
print("\n=== Clean Invoice OCR Quality ===")
print("Status:", res2.status)
print("Score:", res2.score)
print("Reasons:", res2.reasons)
print("Garbage ratio:", res2.garbage_token_ratio)

assert res1.status == "UNRELIABLE", "Garbage OCR must be UNRELIABLE"
assert res2.status == "GOOD", "Clean invoice OCR must be GOOD"
print("\nAssertions passed successfully!")
