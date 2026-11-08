"""Historical user documents management for RAG context with verified tenant authorization."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from before_you_pay.api.deps import (
    get_authenticated_user_id,
    get_pipeline_service,
    verify_tenant_boundary,
)
from before_you_pay.models import DocumentClassification, RagEvidenceChunk
from before_you_pay.services.pipeline import PipelineService

router = APIRouter(prefix="/documents", tags=["Documents"])


class StoreHistoricalDocumentRequest(BaseModel):
    """Request payload to index a user's past invoice, warranty, or contract."""

    user_id: UUID = Field(..., description="Owner user ID (must match authenticated token)")
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


class DocumentSummaryResponse(BaseModel):
    """Summary metadata of an indexed tenant document."""

    document_id: UUID
    document_type: DocumentClassification
    chunk_count: int
    max_page: int


class DeleteDocumentResponse(BaseModel):
    """Confirmation of document deletion."""

    status: str = "deleted"
    document_id: UUID
    deleted_chunks: int


@router.post(
    "",
    response_model=StoreHistoricalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index historical user document for RAG comparison",
    description="Saves a past warranty, agreement, or receipt into the authenticated tenant's isolated store.",
)
async def store_user_document(
    request: StoreHistoricalDocumentRequest,
    authenticated_user_id: UUID = Depends(get_authenticated_user_id),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> StoreHistoricalDocumentResponse:
    """Index past document chunk under authenticated user's tenant account."""
    # Strict tenant boundary verification: prevent forged user_id in payload
    verify_tenant_boundary(authenticated_user_id, request.user_id)

    chunk = RagEvidenceChunk(
        evidence_id=uuid4(),
        user_id=authenticated_user_id,
        source_document_id=request.document_id,
        source_document_type=request.document_type,
        page_number=request.page_number,
        source_text=request.text_content,
        similarity_score=1.0,
    )
    count = await pipeline.rag_service.index_document_chunks(
        user_id=authenticated_user_id,
        document_id=request.document_id,
        chunks=[chunk],
    )
    return StoreHistoricalDocumentResponse(
        user_id=authenticated_user_id,
        document_id=request.document_id,
        chunks_indexed=count,
    )


@router.get(
    "",
    response_model=list[DocumentSummaryResponse],
    summary="List authenticated user's indexed documents",
    description="Lists all documents indexed under the authenticated tenant account.",
)
async def list_user_documents(
    authenticated_user_id: UUID = Depends(get_authenticated_user_id),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> list[DocumentSummaryResponse]:
    """List documents belonging strictly to the authenticated tenant."""
    docs = await pipeline.rag_service.list_user_documents(user_id=authenticated_user_id)
    return [
        DocumentSummaryResponse(
            document_id=d["document_id"],
            document_type=d["document_type"],
            chunk_count=d["chunk_count"],
            max_page=d["max_page"],
        )
        for d in docs
    ]


@router.get(
    "/{document_id}",
    response_model=list[RagEvidenceChunk],
    summary="Get user's historical document chunks",
    description="Retrieve indexed chunks for a document, strictly enforcing tenant authorization and IDOR protection.",
)
async def get_user_document(
    document_id: UUID,
    authenticated_user_id: UUID = Depends(get_authenticated_user_id),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> list[RagEvidenceChunk]:
    """Retrieve document chunks with strict ownership check without leaking existence across tenants."""
    chunks = await pipeline.rag_service.get_document_chunks(
        user_id=authenticated_user_id, document_id=document_id
    )
    if not chunks:
        # Return 404 to avoid leaking whether another tenant owns this document ID
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return chunks


@router.delete(
    "/{document_id}",
    response_model=DeleteDocumentResponse,
    summary="Delete an indexed document",
    description="Deletes all indexed chunks for a document owned by the authenticated tenant.",
)
async def delete_user_document(
    document_id: UUID,
    authenticated_user_id: UUID = Depends(get_authenticated_user_id),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> DeleteDocumentResponse:
    """Delete document chunks strictly owned by the authenticated tenant."""
    deleted_count = await pipeline.rag_service.delete_user_document(
        user_id=authenticated_user_id, document_id=document_id
    )
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DeleteDocumentResponse(
        status="deleted",
        document_id=document_id,
        deleted_chunks=deleted_count,
    )
