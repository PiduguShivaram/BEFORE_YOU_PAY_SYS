with open("src/before_you_pay/services/ocr.py", encoding="utf-8") as f:
    text = f.read()

target = """        # 2. Text payload fallback (for UTF-8 text streams or plain text test uploads)
        if not lines:"""

replacement = """        # 2. Text payload fallback (for UTF-8 text streams or plain text test uploads, NOT binary images)
        is_binary_image = file_bytes.startswith((b"\\x89PNG", b"\\xff\\xd8\\xff", b"GIF", b"RIFF", b"%PDF", b"BM"))
        if not lines and not is_binary_image:"""

assert target in text, "target not found in ocr.py"
text = text.replace(target, replacement)

with open("src/before_you_pay/services/ocr.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated ocr.py to protect against decoding binary image chunks as text")
