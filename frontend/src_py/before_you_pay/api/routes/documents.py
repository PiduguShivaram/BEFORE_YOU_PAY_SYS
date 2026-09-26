"""Historical user documents management for RAG context."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from before_you_pay.api.deps import get_pipeline_service
from before_you_pay.models import DocumentClassification, RagEvidenceChunk
from before_you_pay.services.pipeline import PipelineService

router = APIRouter(prefix="/documents", tags=["Documents"])


class StoreHistoricalDocumentRequest(BaseModel):
    """Request payload to index a user's past invoice, warranty, or contract."""

    user_id: UUID = Field(..., description="Owner user ID")
    document_id: UUID = Field(default_factory=uuid4, description="Historical document ID")
    document_type: DocumentClassification = Field(default=DocumentClassification.CONTRACT)
    page_number: int = Field(default=1, ge=1)
    text_content: str = Field(
        ..., min_length=5, description="Text content to index for RAG comparison"
    )


class StoreHistoricalDocumentResponse(BaseModel):
    """Confirmation of indexed historical document chunk."""

    status: str = "indexed"
    user_id: UUID
    document_id: UUID
    chunks_indexed: int


@router.post(
    "",
    response_model=StoreHistoricalDocumentResponse,
    summary="Index historical user document for RAG comparison",
    description="Saves a past warranty, agreement, or receipt into the user's isolated document store.",
)
async def store_user_document(
    request: StoreHistoricalDocumentRequest,
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> StoreHistoricalDocumentResponse:
    """Index past document chunk under user's tenant account."""
    chunk = RagEvidenceChunk(
        evidence_id=uuid4(),
        user_id=request.user_id,
        source_document_id=request.document_id,
        source_document_type=request.document_type,
        page_number=request.page_number,
        source_text=request.text_content,
        similarity_score=1.0,
    )
    count = await pipeline.rag_service.index_document_chunks(
        user_id=request.user_id,
        document_id=request.document_id,
        chunks=[chunk],
    )
    return StoreHistoricalDocumentResponse(
        user_id=request.user_id,
        document_id=request.document_id,
        chunks_indexed=count,
    )
