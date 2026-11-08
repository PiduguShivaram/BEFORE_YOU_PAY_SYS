"""Dealer response and counter-offer parsing route (Phase 1B)."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from before_you_pay.api.deps import (
    get_dealer_response_parser_service,
    get_optional_authenticated_user_id,
    get_pipeline_service,
    verify_tenant_boundary,
)
from before_you_pay.models import DocumentClassification, StructuredFinancialDocument
from before_you_pay.models.dealer_response import DealerResponseAnalysisResult
from before_you_pay.services.dealer_response_parser import DealerResponseParserService
from before_you_pay.services.pipeline import PipelineService

router = APIRouter(tags=["Dealer Response Parser"])


@router.post(
    "/parse-dealer-response",
    response_model=DealerResponseAnalysisResult,
    summary="Parse and reconcile dealer negotiation text/counter-offer",
    description=(
        "Parses unstructured dealer communications (email/WhatsApp/chat), extracting agreed "
        "concessions, waived charges, discounts, and stated counter-offers, and reconciles them "
        "deterministically against the original quote."
    ),
)
async def parse_dealer_response(
    dealer_text: str = Form(
        ..., min_length=2, description="Dealer reply text or email/chat message"
    ),
    user_id: UUID = Form(..., description="Tenant user ID"),
    original_total: float | None = Form(default=None, description="Original quote total amount"),
    currency: str = Form(default="INR", description="Currency code"),
    quote_file: UploadFile | None = File(
        default=None,
        description="Optional original quote scan or PDF for itemized component context",
    ),
    authenticated_user_id: UUID | None = Depends(get_optional_authenticated_user_id),
    pipeline: PipelineService = Depends(get_pipeline_service),
    parser_service: DealerResponseParserService = Depends(get_dealer_response_parser_service),
) -> DealerResponseAnalysisResult:
    """Execute dealer response extraction and mathematical reconciliation."""
    effective_user_id = verify_tenant_boundary(authenticated_user_id, user_id)
    if not dealer_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Dealer response text cannot be blank.",
        )

    original_doc: StructuredFinancialDocument | None = None

    if quote_file:
        doc_uuid = uuid4()
        content = await quote_file.read()
        mime = quote_file.content_type or "application/octet-stream"

        pipeline.precondition.validate_file(content, mime, effective_user_id)
        ocr_res = await pipeline.ocr_engine.process_document(doc_uuid, content, mime)
        extraction_res = pipeline.extraction_engine.extract(
            document_id=doc_uuid,
            user_id=effective_user_id,
            ocr_result=ocr_res,
            document_type_hint=DocumentClassification.QUOTATION,
        )
        if isinstance(extraction_res, tuple):
            original_doc, _ = extraction_res
        else:
            original_doc = extraction_res

    return parser_service.parse(
        dealer_text=dealer_text,
        user_id=effective_user_id,
        original_document=original_doc,
        original_total=original_total,
        currency=currency,
    )
