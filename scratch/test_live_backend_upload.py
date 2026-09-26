from uuid import uuid4

import httpx

garbage_content = b"""OTA C
0dAe A 0 000
0d/q/ex S0 00b
Posted in r/CarsIndia reddit
"""

user_id = str(uuid4())

files = {"file": ("problematic_scan.txt", garbage_content, "text/plain")}
data = {"user_id": user_id, "document_classification": "other"}

resp = httpx.post("http://127.0.0.1:8000/api/v1/analyze", files=files, data=data, timeout=30.0)
print("HTTP Status:", resp.status_code)
json_data = resp.json()
print("Headline:", json_data.get("summary", {}).get("headline"))
print("Overall Status:", json_data.get("summary", {}).get("overall_status"))
print("Analysis State:", json_data.get("analysis_state"))
print("OCR Quality:", json_data.get("ocr_quality"))
print("Total Flags:", len(json_data.get("flags", [])))
for f in json_data.get("flags", []):
    print(f"  Flag: [{f.get('severity')}] {f.get('label')}: {f.get('message')}")

assert json_data.get("analysis_state") == "OCR_UNRELIABLE"
assert "No Financial Data" not in json_data.get("summary", {}).get("headline", "")
print("\nLIVE BACKEND VERIFICATION SUCCESSFUL: OCR_UNRELIABLE state correctly emitted!")
