import asyncio
from uuid import uuid4

from before_you_pay.models import DocumentClassification
from before_you_pay.services.pipeline import PipelineService


async def main():
    pipeline = PipelineService()
    user_id = uuid4()
    doc_id = uuid4()
    non_financial_text = (
        b"MEMORANDUM\n"
        b"To: All Staff Members\n"
        b"From: Operations Management Committee\n"
        b"Subject: Annual Office Community Clean-Up and Garden Renovation\n\n"
        b"We are pleased to invite everyone to participate in our annual office community\n"
        b"clean-up day this coming Friday afternoon. Refreshments will be provided in the\n"
        b"main courtyard. Please contact building reception if you require garden tools.\n"
        b"Thank you for your enthusiastic cooperation and ongoing dedication.\n"
    )

    res = await pipeline.run_full_pipeline(
        document_id=doc_id,
        user_id=user_id,
        file_bytes=non_financial_text,
        mime_type="text/plain",
        document_type_hint=DocumentClassification.OTHER,
    )
    print("State:", res.analysis_state)
    print("Headline:", res.summary.headline)
    print("Overall status:", res.summary.overall_status)
    print("Validation checks count:", len(res.validation_checks))
    for c in res.validation_checks:
        print(
            f"  Check: {c.check_code}, status={c.status}, severity={c.severity}, message={c.message}"
        )


asyncio.run(main())
