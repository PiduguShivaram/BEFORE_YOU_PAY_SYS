import asyncio
from uuid import uuid4

from before_you_pay.models import AnalysisState
from before_you_pay.services.pipeline import PipelineService


async def main():
    pipeline = PipelineService()
    user_id = uuid4()

    # Case A: Good OCR + Financial Document
    invoice_payload = (
        b"ACME CORP INVOICE\n"
        b"Invoice #9988 Date: 2024-05-10\n"
        b"Line 1: Server Maintenance 10 hrs @ $50.00 = $500.00\n"
        b"Subtotal: $500.00\n"
        b"Sales Tax: $50.00\n"
        b"Total Amount Due: $550.00\n"
    )
    res_a = await pipeline.run_full_pipeline(uuid4(), user_id, invoice_payload, "text/plain")
    print("Case A State:", res_a.analysis_state)
    assert res_a.analysis_state == AnalysisState.FINANCIAL_DATA_FOUND

    # Case B: Good OCR + Non-Financial Document
    letter_payload = (
        b"Dear Members of the Committee,\n"
        b"We are writing to express our sincere appreciation for the recent community workshop.\n"
        b"The presentations delivered on sustainable urban development were insightful and engaging.\n"
        b"We look forward to continuing our collaboration in future educational seminars.\n"
        b"Sincerely,\n"
        b"The Advisory Council\n"
    )
    res_b = await pipeline.run_full_pipeline(uuid4(), user_id, letter_payload, "text/plain")
    print("Case B State:", res_b.analysis_state)
    print("Case B Headline:", res_b.summary.headline)
    assert res_b.analysis_state == AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR

    # Case C: Garbage OCR
    garbage_payload = b"OTA C\n0dAe A 0 000\n0d/q/ex S0 00b\nPosted in r/CarsIndia reddit\n"
    res_c = await pipeline.run_full_pipeline(uuid4(), user_id, garbage_payload, "text/plain")
    print("Case C State:", res_c.analysis_state)
    assert res_c.analysis_state == AnalysisState.OCR_UNRELIABLE

    # Case D: Empty OCR (white space only)
    empty_payload = b"   \n   \n   \n"
    res_d = await pipeline.run_full_pipeline(uuid4(), user_id, empty_payload, "text/plain")
    print("Case D State:", res_d.analysis_state)
    assert res_d.analysis_state == AnalysisState.DOCUMENT_UNREADABLE

    print("\nAll pipeline states verified successfully!")


asyncio.run(main())
