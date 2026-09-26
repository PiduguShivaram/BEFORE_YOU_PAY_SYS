with open("src/before_you_pay/services/pipeline.py", encoding="utf-8") as f:
    text = f.read()

target = """                all_lines = [line for p in ocr_result.pages for line in p.lines]
                p_id = ocr_result.pages[0].page_id if ocr_result.pages else uuid4()
                zero_prov = FieldProvenance(document_id=document_id, page_id=p_id, ocr_line_ids=[], raw_text="")"""

replacement = """                all_lines = [line for p in ocr_result.pages for line in p.lines]
                p_id = ocr_result.pages[0].page_id if ocr_result.pages else uuid4()
                first_line = all_lines[0] if all_lines else None
                first_line_id = first_line.line_id if first_line else uuid4()
                first_text = first_line.text if first_line else "Non-financial"
                zero_prov = FieldProvenance(document_id=document_id, page_id=p_id, ocr_line_ids=[first_line_id], raw_text=first_text)"""

assert target in text, "target not found"
text = text.replace(target, replacement)

with open("src/before_you_pay/services/pipeline.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Fixed zero_prov in pipeline.py")
