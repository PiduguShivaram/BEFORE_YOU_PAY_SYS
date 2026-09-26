# Fix analyze.py
with open("src/before_you_pay/api/routes/analyze.py", encoding="utf-8") as f:
    text = f.read()

prefix = (
    'import asyncio\n\n"""End-to-end document analysis endpoint for mobile-first client."""\n\n'
)
if text.startswith(prefix):
    rest = text[len(prefix) :]
    text = (
        '"""End-to-end document analysis endpoint for mobile-first client."""\n\nimport asyncio\n'
        + rest
    )
    with open("src/before_you_pay/api/routes/analyze.py", "w", encoding="utf-8") as f:
        f.write(text)

# Fix extraction.py
with open("src/before_you_pay/services/extraction.py", encoding="utf-8") as f:
    text = f.read()

prefix = 'from before_you_pay.core.errors import ContractViolationException\n\n"""Structured financial extraction engine parsing OCR lines into normalized fields."""\n\n'
if text.startswith(prefix):
    rest = text[len(prefix) :]
    text = (
        '"""Structured financial extraction engine parsing OCR lines into normalized fields."""\n\nfrom before_you_pay.core.errors import ContractViolationException\n'
        + rest
    )
    with open("src/before_you_pay/services/extraction.py", "w", encoding="utf-8") as f:
        f.write(text)

print("Headers fixed!")
