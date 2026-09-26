import httpx

path = r"C:\Users\shiva\Downloads\WhatsApp Image 2026-09-24 at 1.11.24 PM.jpeg"
with open(path, "rb") as f:
    files = {"file": ("quote.jpg", f, "image/jpeg")}
    data_form = {
        "user_id": "12345678-1234-5678-1234-567812345678",
        "document_classification": "quotation",
    }
    resp = httpx.post("http://127.0.0.1:8000/api/v1/analyze", files=files, data=data_form, timeout=90.0)

print("HTTP Status:", resp.status_code)
data = resp.json()

q = data.get("ocr_quality", {})
print("OCR Quality Status:", q.get("status"))
print("OCR Quality Score:", q.get("score"))
print("OCR Quality Reasons:", q.get("reasons"))

ocr_lines = data.get("ocr_lines", [])
print(f"Total OCR Lines: {len(ocr_lines)}")
for l in ocr_lines[:3]:
    print(f"  Line {l.get('line_number')}: '{l.get('text')}' | conf={l.get('confidence')}")

doc = data.get("document", {})
print("Doc Type:", doc.get("document_type"))
print("Subtotal:", doc.get("subtotal", {}).get("normalized_value"))
print("Discount:", doc.get("discount_amount", {}).get("normalized_value"))
print("Total:", doc.get("total_amount", {}).get("normalized_value"))

breakdown = doc.get("cost_breakdown", [])
print(f"Cost Breakdown ({len(breakdown)} components):")
for c in breakdown:
    nature = c.get("charge_nature", "").upper()
    name = c.get("name", "")
    cat = c.get("category", "")
    amt = c.get("amount", {}).get("normalized_value")
    print(f"  - [{nature}] {name} ({cat}): {amt}")

print("\nValidation Checks:")
for chk in data.get("validation_checks", []):
    code = chk.get("check_code", "")
    if "QUOTATION" in code or "TOTAL" in code or "SUM" in code:
        status = chk.get("status", "")
        msg = chk.get("message", "").replace("\u20b9", "INR ")
        print(f"  [{status}] {code}: {msg}")

summary = data.get("summary", {})
print("\nSummary Headline:", summary.get("headline"))
print("Summary Status:", summary.get("overall_status"))

flags = data.get("flags", [])
print(f"\nDecision Flags ({len(flags)}):")
for f in flags:
    sev = f.get("severity")
    lbl = f.get("label")
    msg = f.get("message", "").replace("\u20b9", "INR ")
    print(f"  [{sev}] {lbl}: {msg}")
