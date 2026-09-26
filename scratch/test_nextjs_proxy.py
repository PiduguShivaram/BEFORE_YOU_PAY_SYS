from uuid import uuid4

import httpx

garbage_content = b"""OTA C
0dAe A 0 000
0d/q/ex S0 00b
Posted in r/CarsIndia reddit
"""

files = {"file": ("problematic_scan.txt", garbage_content, "text/plain")}
data = {"user_id": str(uuid4()), "document_classification": "other"}

resp = httpx.post("http://localhost:3000/api/v1/analyze", files=files, data=data, timeout=30.0)
print("Proxy HTTP Status:", resp.status_code)
json_data = resp.json()
print("Headline:", json_data.get("summary", {}).get("headline"))
print("Analysis State:", json_data.get("analysis_state"))
print("OCR Quality:", json_data.get("ocr_quality", {}).get("status"))

assert resp.status_code == 200
assert json_data.get("analysis_state") == "OCR_UNRELIABLE"
print("\nNEXT.JS REVERSE PROXY TEST PASSED: State delivered seamlessly to frontend!")
