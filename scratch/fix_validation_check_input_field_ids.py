with open("src/before_you_pay/services/pipeline.py", encoding="utf-8") as f:
    text = f.read()

target = """                        ValidationCheck(
                            validation_id=uuid4(),
                            check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                            status=ValidationStatus.PASS,
                            severity=ValidationSeverity.INFO,
                            message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
                        )"""

replacement = """                        ValidationCheck(
                            validation_id=uuid4(),
                            check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                            status=ValidationStatus.PASS,
                            input_field_ids=[extracted_doc.total_amount.field_id],
                            severity=ValidationSeverity.INFO,
                            message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
                        )"""

text = text.replace(target, replacement)

with open("src/before_you_pay/services/pipeline.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Added input_field_ids to ValidationCheck in pipeline.py")
