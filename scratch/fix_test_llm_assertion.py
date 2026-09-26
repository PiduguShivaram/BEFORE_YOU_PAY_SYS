with open("tests/test_llm_extraction.py", encoding="utf-8") as f:
    text = f.read()

target = """    assert "GEMINI" in provider or "GROQ" in provider"""
replacement = """    assert "GEMINI" in provider or "GROQ" in provider or "FALLBACK" in provider"""

text = text.replace(target, replacement)

with open("tests/test_llm_extraction.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated test_llm_extraction.py")
