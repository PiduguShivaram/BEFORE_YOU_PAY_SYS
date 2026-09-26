"""Test fixtures and configuration for Before You Pay."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from before_you_pay.main import create_app
from before_you_pay.models import (
    BoundingBox,
    ClaimType,
    CoordinateUnit,
    DocumentClassification,
    DocumentMetadata,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OcrLine,
    OcrPage,
    OcrResult,
    OkfCategory,
    OkfRuleEvidence,
    RagEvidenceChunk,
    ReasoningClaim,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client for FastAPI application."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_user_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_document_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_page_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_line_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_bounding_box() -> BoundingBox:
    return BoundingBox(
        x=0.1,
        y=0.2,
        width=0.4,
        height=0.05,
        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
    )


@pytest.fixture
def sample_document_metadata(sample_document_id: UUID, sample_user_id: UUID) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=sample_document_id,
        user_id=sample_user_id,
        file_name="quotation_september.pdf",
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        total_pages=2,
        file_size_bytes=1048576,
        document_classification=DocumentClassification.QUOTATION,
    )


@pytest.fixture
def sample_ocr_result(
    sample_document_id: UUID,
    sample_page_id: UUID,
    sample_line_id: UUID,
    sample_bounding_box: BoundingBox,
) -> OcrResult:
    line = OcrLine(
        line_id=sample_line_id,
        page_id=sample_page_id,
        document_id=sample_document_id,
        line_number=1,
        text="Total: $150.00",
        bounding_box=sample_bounding_box,
        confidence=0.98,
    )
    page = OcrPage(
        page_id=sample_page_id,
        document_id=sample_document_id,
        page_number=1,
        width=1080,
        height=1920,
        dpi=300,
        lines=[line],
    )
    return OcrResult(
        document_id=sample_document_id,
        pages=[page],
        engine_name="mock_ocr_test",
        engine_version="1.0.0",
    )


@pytest.fixture
def sample_extracted_document(
    sample_document_id: UUID,
    sample_user_id: UUID,
    sample_page_id: UUID,
    sample_line_id: UUID,
    sample_bounding_box: BoundingBox,
) -> StructuredFinancialDocument:
    provenance = FieldProvenance(
        document_id=sample_document_id,
        page_id=sample_page_id,
        ocr_line_ids=[sample_line_id],
        bounding_box=sample_bounding_box,
        raw_text="$150.00",
    )
    total_field = ExtractedField(
        field_id=uuid4(),
        field_key="total_amount",
        normalized_value=150.00,
        unit_or_currency="USD",
        confidence=0.95,
        provenance=provenance,
    )
    desc_field = ExtractedField(
        field_id=uuid4(),
        field_key="item_description",
        normalized_value="Consulting Services",
        unit_or_currency=None,
        confidence=0.97,
        provenance=provenance,
    )
    item_total = ExtractedField(
        field_id=uuid4(),
        field_key="item_total",
        normalized_value=150.00,
        unit_or_currency="USD",
        confidence=0.95,
        provenance=provenance,
    )
    line_item = LineItem(
        description=desc_field,
        total_price=item_total,
    )
    return StructuredFinancialDocument(
        document_id=sample_document_id,
        user_id=sample_user_id,
        document_type=DocumentClassification.QUOTATION,
        line_items=[line_item],
        total_amount=total_field,
    )


@pytest.fixture
def sample_rag_chunk(sample_user_id: UUID) -> RagEvidenceChunk:
    return RagEvidenceChunk(
        evidence_id=uuid4(),
        user_id=sample_user_id,
        source_document_id=uuid4(),
        source_document_type=DocumentClassification.CONTRACT,
        page_number=1,
        source_text="Monthly retainer fee agreed at $120.00.",
        similarity_score=0.88,
    )


@pytest.fixture
def sample_okf_rule() -> OkfRuleEvidence:
    return OkfRuleEvidence(
        rule_id="OKF-RULE-FEE-01",
        rule_name="Unstated Ancillary Processing Fee",
        category=OkfCategory.VERIFICATION_RULE,
        summary="Commercial contracts must explicitly specify any recurring platform fees.",
        source_reference="Uniform Commercial Code (UCC) Standard Rules",
        version="1.0.0",
        guidance="Flag any undisclosed recurring surcharge not itemized in the base schedule.",
    )


@pytest.fixture
def sample_validation_check(
    sample_extracted_document: StructuredFinancialDocument,
) -> ValidationCheck:
    return ValidationCheck(
        validation_id=uuid4(),
        check_code="ARITHMETIC_TOTAL_SUM",
        status=ValidationStatus.PASS,
        input_field_ids=[sample_extracted_document.total_amount.field_id],
        expected_value=150.00,
        calculated_value=150.00,
        absolute_delta=0.0,
        severity=ValidationSeverity.INFO,
        message="Sum of line items matches total amount.",
    )


@pytest.fixture
def sample_reasoning_claim(
    sample_extracted_document: StructuredFinancialDocument,
    sample_rag_chunk: RagEvidenceChunk,
) -> ReasoningClaim:
    return ReasoningClaim(
        claim_id=uuid4(),
        type=ClaimType.POTENTIAL_OVERLAP,
        title="Potential overlap with prior agreement",
        description="The quoted price of $150 differs from the prior contract fee of $120.",
        field_references=[sample_extracted_document.total_amount.field_id],
        rag_evidence_references=[sample_rag_chunk.evidence_id],
        confidence=0.85,
    )
