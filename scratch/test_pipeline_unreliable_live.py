import asyncio
from uuid import uuid4

from before_you_pay.models import AnalysisState, DocumentClassification
from before_you_pay.services.pipeline import PipelineService


async def main():
    pipeline = PipelineService()
    doc_id = uuid4()
    user_id = uuid4()

    # Garbage OCR content
    garbage_payload = b"OTA C\n0dAe A 0 000\n0d/q/ex S0 00b\nPosted in r/CarsIndia reddit\n"

    res = await pipeline.run_full_pipeline(
        document_id=doc_id,
        user_id=user_id,
        file_bytes=garbage_payload,
        mime_type="text/plain",
        document_type_hint=DocumentClassification.OTHER,
    )

    print("=== Full Pipeline Result on Garbage Text ===")
    print("Headline:", res.summary.headline)
    print("Overall Status:", res.summary.overall_status)
    print("Analysis State:", res.analysis_state)
    print("OCR Quality Status:", res.ocr_quality.status if res.ocr_quality else None)
    print("Flags:", len(res.flags))
    for f in res.flags:
        print(f"  Flag: [{f.severity}] {f.label}: {f.message}")

    assert res.analysis_state == AnalysisState.OCR_UNRELIABLE, (
        f"Expected OCR_UNRELIABLE, got {res.analysis_state}"
    )
    assert "No Financial Data" not in res.summary.headline, (
        "Must NOT claim No Financial Data Detected"
    )
    print("\nVerified: Garbage text never produces 'No Financial Data Detected'!")


asyncio.run(main())
