"""Unit tests verifying data-provenance chains and anti-orphan constraints."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from before_you_pay.models import (
    BoundingBox,
    ClaimType,
    FieldProvenance,
    ReasoningClaim,
    StructuredFinancialDocument,
    ValidationCheck,
)


class TestDataProvenanceChain:
    """Verifies that every entity is strictly traceable back to physical OCR lines and pages."""

    def test_full_provenance_traceability(
        self,
        sample_document_id: UUID,
        sample_page_id: UUID,
        sample_line_id: UUID,
        sample_bounding_box: BoundingBox,
        sample_extracted_document: StructuredFinancialDocument,
        sample_reasoning_claim: ReasoningClaim,
        sample_validation_check: ValidationCheck,
    ) -> None:
        """Trace from high-level reasoning claim and validation check down to document page."""
        # 1. Validation check links to extracted field
        assert (
            sample_extracted_document.total_amount.field_id
            in sample_validation_check.input_field_ids
        )

        # 2. Reasoning claim links to extracted field
        assert (
            sample_extracted_document.total_amount.field_id
            in sample_reasoning_claim.field_references
        )

        # 3. Extracted field links to FieldProvenance
        field_prov = sample_extracted_document.total_amount.provenance
        assert field_prov.document_id == sample_document_id
        assert field_prov.page_id == sample_page_id
        assert sample_line_id in field_prov.ocr_line_ids

        # 4. Provenance includes spatial bounding box
        assert field_prov.bounding_box is not None
        assert field_prov.bounding_box.x == sample_bounding_box.x
        assert field_prov.raw_text == "$150.00"

    def test_orphan_reasoning_claim_rejected(self) -> None:
        """A reasoning claim with no supporting evidence must fail validation."""
        with pytest.raises(ValidationError, match="ReasoningClaim cannot be an orphan"):
            ReasoningClaim(
                claim_id=uuid4(),
                type=ClaimType.POTENTIAL_ISSUE,
                title="Unsubstantiated finding",
                description="This claim has zero backing references.",
                field_references=[],
                rag_evidence_references=[],
                okf_rule_references=[],
                validation_references=[],
                confidence=0.5,
            )

    def test_orphan_field_provenance_rejected(
        self, sample_document_id: UUID, sample_page_id: UUID
    ) -> None:
        """FieldProvenance with empty ocr_line_ids must fail validation."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                document_id=sample_document_id,
                page_id=sample_page_id,
                ocr_line_ids=[],  # min_length=1 required
                raw_text="Test",
            )

    def test_empty_raw_text_rejected(
        self,
        sample_document_id: UUID,
        sample_page_id: UUID,
        sample_line_id: UUID,
    ) -> None:
        """FieldProvenance with empty raw_text must fail validation."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                document_id=sample_document_id,
                page_id=sample_page_id,
                ocr_line_ids=[sample_line_id],
                raw_text="",  # min_length=1 required
            )
