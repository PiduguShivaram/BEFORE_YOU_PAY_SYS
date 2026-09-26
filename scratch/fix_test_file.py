with open("tests/test_ocr_quality_and_states.py", encoding="utf-8") as f:
    text = f.read()

# Fix test_i FieldProvenance
text = text.replace("ocr_line_id=uuid4()", "ocr_line_ids=[uuid4()]")

with open("tests/test_ocr_quality_and_states.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Fixed test_ocr_quality_and_states.py")
