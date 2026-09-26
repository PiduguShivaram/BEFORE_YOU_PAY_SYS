with open("tests/test_audit_fixes.py", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    "        engine = SpatialOcrEngine()\n        doc_id = uuid4()", "        doc_id = uuid4()"
)

with open("tests/test_audit_fixes.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Cleaned up unused engine variable")
