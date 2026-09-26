# 1. Fix analyze.py docstring / import ordering
with open("src/before_you_pay/api/routes/analyze.py", encoding="utf-8") as f:
    text = f.read()
if text.startswith('import asyncio\n"""'):
    text = text.replace(
        'import asyncio\n"""End-to-end document analysis endpoint for mobile-first client."""\n',
        '"""End-to-end document analysis endpoint for mobile-first client."""\n\nimport asyncio\n',
    )
    with open("src/before_you_pay/api/routes/analyze.py", "w", encoding="utf-8") as f:
        f.write(text)

# 2. Fix extraction.py docstring / import ordering
with open("src/before_you_pay/services/extraction.py", encoding="utf-8") as f:
    text = f.read()
if text.startswith('import re\n"""'):
    text = text.replace(
        'import re\n"""Structured financial extraction engine parsing OCR lines into normalized fields."""\n',
        '"""Structured financial extraction engine parsing OCR lines into normalized fields."""\n\nimport re\n',
    )
    with open("src/before_you_pay/services/extraction.py", "w", encoding="utf-8") as f:
        f.write(text)

# 3. Fix ambiguous variable `l` in ocr_quality.py
with open("src/before_you_pay/services/ocr_quality.py", encoding="utf-8") as f:
    text = f.read()
text = text.replace('" ".join(l.text for l in all_lines)', '" ".join(ln.text for ln in all_lines)')
with open("src/before_you_pay/services/ocr_quality.py", "w", encoding="utf-8") as f:
    f.write(text)

# 4. Fix ambiguous variable `l` in result.py
with open("src/before_you_pay/services/result.py", encoding="utf-8") as f:
    text = f.read()
text = text.replace(
    "all_lines = [l for p in ocr_result.pages for l in p.lines]",
    "all_lines = [ln for p in ocr_result.pages for ln in p.lines]",
)
text = text.replace(
    "raw_lines = [l.text for l in all_lines]", "raw_lines = [ln.text for ln in all_lines]"
)
with open("src/before_you_pay/services/result.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Applied ruff cleanups")
