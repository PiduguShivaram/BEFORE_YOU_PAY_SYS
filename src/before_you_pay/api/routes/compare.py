"""Multi-document quotation comparison route (Phase 1A)."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from before_you_pay.api.deps import get_multi_quote_comparison_service, get_pipeline_service
from before_you_pay.models import DocumentClassification, StructuredFinancialDocument
from before_you_pay.models.multi_quote_comparison import MultiQuoteComparisonResult
from before_you_pay.services.multi_quote_comparison import MultiQuoteComparisonService
from before_you_pay.services.pipeline import PipelineService

router = APIRouter(tags=["Multi-Quote Comparison"])


@router.post(
    "/compare-quotes",
    response_model=MultiQuoteComparisonResult,
    summary="N-way multi-quotation comparison (2 to 5 quotations)",
    description=(
        "Simultaneously processes and aligns 2 to 5 quotations/bills, computing component deltas, "
        "identifying inclusions/exclusions, and generating neutral vendor negotiation questions."
    ),
)
async def compare_quotes(
    files: list[UploadFile] = File(..., description="2 to 5 quotation documents (images or PDFs)"),
    user_id: UUID = Form(..., description="Tenant user ID"),
    pipeline: PipelineService = Depends(get_pipeline_service),
    comparison_service: MultiQuoteComparisonService = Depends(get_multi_quote_comparison_service),
) -> MultiQuoteComparisonResult:
    """Execute N-way multi-quote comparison across 2 to 5 files."""
    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 quotation documents are required for comparison.",
        )
    if len(files) > 5:
        raise HTTPException(
            status_code=400,
            detail="A maximum of 5 quotation documents can be compared simultaneously.",
        )

    # Process each document through Precondition -> OCR -> Extraction
    extracted_docs: list[StructuredFinancialDocument] = []

    for f in files:
        doc_uuid = uuid4()
        content = await f.read()
        mime = f.content_type or "application/octet-stream"

        # Validate precondition
        pipeline.precondition.validate_file(content, mime, user_id)

        # OCR
        ocr_res = await pipeline.ocr_engine.process_document(doc_uuid, content, mime)

        # Extract structured document
        extraction_res = pipeline.extraction_engine.extract(
            document_id=doc_uuid,
            user_id=user_id,
            ocr_result=ocr_res,
            document_type_hint=DocumentClassification.QUOTATION,
        )
        if isinstance(extraction_res, tuple):
            extracted_doc, _ = extraction_res
        else:
            extracted_doc = extraction_res

        extracted_docs.append(extracted_doc)

    # Perform deterministic multi-quote alignment and comparison
    return comparison_service.compare(documents=extracted_docs, user_id=user_id)
