import asyncio
from uuid import uuid4
from before_you_pay.services.pipeline import PipelineService

async def main():
    path = r"C:\Users\shiva\Downloads\WhatsApp Image 2026-09-24 at 1.11.24 PM.jpeg"
    with open(path, "rb") as f:
        data = f.read()

    pipeline = PipelineService()
    doc_id = uuid4()
    user_id = uuid4()
    res = await pipeline.run_full_pipeline(doc_id, user_id, data, "image/jpeg")

    print("\n--- RESULT SUMMARY ---")
    print(f"Headline: {res.summary.headline}")
    print(f"Overall Status: {res.summary.overall_status}")
    print(f"Analysis State: {res.analysis_state}")
    
    doc = res.document
    if doc:
        print("\n--- EXTRACTED DOCUMENT ---")
        print(f"Document Type: {doc.document_type}")
        print(f"Subtotal: {doc.subtotal.normalized_value if doc.subtotal else None}")
        print(f"Discount: {doc.discount_amount.normalized_value if doc.discount_amount else None}")
        print(f"Total: {doc.total_amount.normalized_value if doc.total_amount else None}")
        print(f"Cost Breakdown ({len(doc.cost_breakdown)} components):")
        for c in doc.cost_breakdown:
            print(f"  - [{c.charge_nature.value.upper()}] {c.name} ({c.category.value}): {c.amount.normalized_value}")
    
    print("\n--- VALIDATION CHECKS ---")
    for v in res.validation_checks:
        safe_msg = v.message.replace("₹", "INR ")
        print(f"[{v.status.value}] {v.check_code} | Msg: {safe_msg}")

    print("\n--- FLAGS ---")
    for f in res.flags:
        safe_flag = f.message.replace("₹", "INR ")
        print(f"[{f.severity.value}] {f.label}: {safe_flag}")

if __name__ == "__main__":
    asyncio.run(main())
