with open("frontend/src/app/page.tsx", encoding="utf-8") as f:
    page_code = f.read()

target = """              <DocumentViewer
                documentText={
                  result?.raw_ocr_lines && result.raw_ocr_lines.length > 0
                    ? result.raw_ocr_lines.join("\\n")
                    : documentText
                }
                selectedFlag={selectedFlag}
                imagePreviewUrl={imagePreviewUrl}
              />"""

replacement = """              <DocumentViewer
                documentText={
                  result?.raw_ocr_lines && result.raw_ocr_lines.length > 0
                    ? result.raw_ocr_lines.join("\\n")
                    : documentText
                }
                ocrLines={result?.ocr_lines}
                selectedFlag={selectedFlag}
                imagePreviewUrl={imagePreviewUrl}
              />"""

assert target in page_code, "target not found in page.tsx"
page_code = page_code.replace(target, replacement)

with open("frontend/src/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(page_code)
print("Updated frontend/src/app/page.tsx successfully")
