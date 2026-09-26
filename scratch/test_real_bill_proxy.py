from uuid import uuid4

import httpx

with open("scratch/sample_bill.txt", "rb") as f:
    bill_bytes = f.read()

files = {"file": ("sample_bill.txt", bill_bytes, "text/plain")}
data = {"user_id": str(uuid4()), "document_classification": "bill"}

resp = httpx.post("http://localhost:3000/api/v1/analyze", files=files, data=data, timeout=90.0)
print("Bill Proxy HTTP Status:", resp.status_code)
json_data = resp.json()
print("Headline:", json_data.get("summary", {}).get("headline"))
print("Overall Status:", json_data.get("summary", {}).get("overall_status"))
print("Analysis State:", json_data.get("analysis_state"))
print("OCR Quality:", json_data.get("ocr_quality", {}).get("status"))
print(
    "Total Amount:", json_data.get("document", {}).get("total_amount", {}).get("normalized_value")
)
print("Line items count:", len(json_data.get("document", {}).get("line_items", [])))

assert resp.status_code == 200
assert json_data.get("analysis_state") == "FINANCIAL_DATA_FOUND"
assert json_data.get("document", {}).get("total_amount", {}).get("normalized_value") == 1499.0
print("\nREAL BILL VERIFICATION SUCCESSFUL: FINANCIAL_DATA_FOUND state correctly processed!")
