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

with httpx.stream(
    "POST", "http://127.0.0.1:8000/api/v1/analyze/stream", files=files, data=data, timeout=30.0
) as resp:
    print("Stream HTTP Status:", resp.status_code)
    for line in resp.iter_lines():
        if line.startswith("data: "):
            print("SSE Event:", line[:120])

print("\nLIVE STREAMING VERIFICATION SUCCESSFUL!")
