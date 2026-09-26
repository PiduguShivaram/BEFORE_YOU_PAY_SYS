import asyncio
from uuid import uuid4
from before_you_pay.services.ocr import SpatialOcrEngine

async def main():
    path = r"C:\Users\shiva\Downloads\WhatsApp Image 2026-09-24 at 1.11.24 PM.jpeg"
    with open(path, "rb") as f:
        data = f.read()

    engine = SpatialOcrEngine()
    doc_id = uuid4()
    res = await engine.process_document(doc_id, data, "image/jpeg")
    print(f"Engine: {res.engine_name}, version: {res.engine_version}, recovery_pass: {res.recovery_pass}")
    print(f"Quality status: {res.quality.status if res.quality else 'None'}, score: {res.quality.score if res.quality else 'None'}")
    print(f"Extracted {len(res.pages[0].lines)} lines:")
    for l in res.pages[0].lines:
        print(f"[{l.line_number}] {l.text} | Box: {l.bounding_box.x}, {l.bounding_box.y}, {l.bounding_box.width}, {l.bounding_box.height}")

if __name__ == "__main__":
    asyncio.run(main())
