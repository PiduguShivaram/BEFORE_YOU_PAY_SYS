import base64
import json
import httpx
from before_you_pay.config import get_settings

settings = get_settings()
key = settings.gemini_api_key_primary
model = settings.gemini_model

path = r"C:\Users\shiva\Downloads\WhatsApp Image 2026-09-24 at 1.11.24 PM.jpeg"
with open(path, "rb") as f:
    img_bytes = f.read()

b64 = base64.b64encode(img_bytes).decode("utf-8")
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

prompt = """Transcribe every handwritten line from this document into a JSON array of objects:
[
  {"line_number": 1, "text": "...", "box_2d": [ymin, xmin, ymax, xmax]}
]
box_2d coordinates should be normalized from 0 to 1000 (standard Gemini bounding box).
Include all items, vehicle model, ex-showroom, taxes, insurance, registration, warranty, temp/hsrp, subtotal, offers, and final total."""

payload = {
    "contents": [{"parts": [{"inlineData": {"mimeType": "image/jpeg", "data": b64}}, {"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json"},
}

resp = httpx.post(url, json=payload, timeout=30.0)
print("HTTP status:", resp.status_code)
data = resp.json()
text_part = data["candidates"][0]["content"]["parts"][0]["text"]
lines = json.loads(text_part)
print(f"Extracted {len(lines)} lines:")
for l in lines:
    print(l)
