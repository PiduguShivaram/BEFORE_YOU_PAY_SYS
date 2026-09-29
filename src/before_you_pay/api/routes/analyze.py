"""End-to-end document analysis endpoint for mobile-first client."""

import asyncio
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from before_you_pay.api.deps import get_pipeline_service
from before_you_pay.models import DocumentClassification, FinalDecisionSupportResult
from before_you_pay.services.pipeline import PipelineService

router = APIRouter(tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=FinalDecisionSupportResult,
    summary="End-to-end document scan analysis",
    description="Full 7-stage execution: Precondition -> OCR -> Extract -> RAG -> OKF -> Reason -> Validate -> Result.",
)
async def analyze_document(
    file: UploadFile = File(..., description="Document scan image or PDF"),
    supporting_file: UploadFile | None = File(
        default=None,
        description="Optional supporting document scan image or PDF (warranty, insurance, past quote)",
    ),
    user_id: UUID = Form(..., description="Tenant user ID"),
    document_classification: DocumentClassification = Form(
        default=DocumentClassification.OTHER,
        description="Optional document type hint",
    ),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> FinalDecisionSupportResult:
    """Execute full 7-stage analysis pipeline on uploaded file."""
    doc_uuid = uuid4()
    content = await file.read()
    mime = file.content_type or "application/octet-stream"

    supporting_content = await supporting_file.read() if supporting_file else None
    supporting_mime = (
        (supporting_file.content_type or "application/octet-stream") if supporting_file else None
    )

    return await pipeline.run_full_pipeline(
        document_id=doc_uuid,
        user_id=user_id,
        file_bytes=content,
        mime_type=mime,
        document_type_hint=document_classification,
        supporting_file_bytes=supporting_content,
        supporting_mime_type=supporting_mime,
    )


@router.post(
    "/analyze/stream",
    summary="Progressive SSE streaming document scan analysis",
    description="Real-time Server-Sent Events updating frontend progress stage-by-stage.",
)
async def analyze_document_stream(
    file: UploadFile = File(..., description="Document scan image or PDF"),
    supporting_file: UploadFile | None = File(
        default=None,
        description="Optional supporting document scan image or PDF (warranty, insurance, past quote)",
    ),
    user_id: UUID = Form(..., description="Tenant user ID"),
    document_classification: DocumentClassification = Form(
        default=DocumentClassification.OTHER,
        description="Optional document type hint",
    ),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> StreamingResponse:
    """Execute 7-stage pipeline streaming live SSE events to frontend."""
    doc_uuid = uuid4()
    content = await file.read()
    mime = file.content_type or "application/octet-stream"

    supporting_content = await supporting_file.read() if supporting_file else None
    supporting_mime = (
        (supporting_file.content_type or "application/octet-stream") if supporting_file else None
    )

    async def event_generator():
        try:
            async for step in pipeline.run_streaming_pipeline(
                document_id=doc_uuid,
                user_id=user_id,
                file_bytes=content,
                mime_type=mime,
                document_type_hint=document_classification,
                supporting_file_bytes=supporting_content,
                supporting_mime_type=supporting_mime,
            ):
                payload = json.dumps(step, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            return
        except Exception as exc:
            err_payload = json.dumps(
                {"stage": "error", "error": str(exc), "progress": 0}, ensure_ascii=False
            )
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
