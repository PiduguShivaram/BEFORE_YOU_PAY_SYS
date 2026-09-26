"""Unit tests verifying domain model validation, strict boundaries, and serialization."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from before_you_pay.models import (
    BoundingBox,
    ClaimType,
    CoordinateUnit,
    DecisionFlag,
    DecisionStatus,
    DocumentMetadata,
    FinalDecisionSupportResult,
    OcrLine,
    ReasoningClaim,
    ResultSummary,
    StandardError,
    ValidationCheck,
    ValidationSeverity,
)


class TestBoundingBoxValidation:
    """Test suite for BoundingBox spatial invariants."""

    def test_valid_bounding_box(self) -> None:
        box = BoundingBox(x=0.0, y=0.0, width=1.0, height=1.0)
        assert box.x == 0.0
        assert box.y == 0.0
        assert box.width == 1.0
        assert box.height == 1.0
        assert box.coordinate_unit == CoordinateUnit.NORMALIZED_PERCENTAGE

    def test_negative_coordinates_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x=-0.1, y=0.2, width=0.5, height=0.2)

        with pytest.raises(ValidationError):
            BoundingBox(x=0.1, y=-0.05, width=0.5, height=0.2)

    def test_zero_or_negative_dimensions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x=0.1, y=0.2, width=0.0, height=0.2)

        with pytest.raises(ValidationError):
            BoundingBox(x=0.1, y=0.2, width=0.5, height=-0.1)

    def test_coordinates_exceeding_unity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x=1.1, y=0.2, width=0.5, height=0.2)

    def test_box_overflowing_page_boundary_rejected(self) -> None:
        # x + width > 1.0
        with pytest.raises(ValidationError, match="Bounding box exceeds horizontal boundary"):
            BoundingBox(x=0.8, y=0.1, width=0.3, height=0.2)

        # y + height > 1.0
        with pytest.raises(ValidationError, match="Bounding box exceeds vertical boundary"):
            BoundingBox(x=0.1, y=0.85, width=0.2, height=0.2)


class TestConfidenceValidation:
    """Test suite for confidence score validation (0.0 to 1.0)."""

    def test_confidence_out_of_bounds_rejected(self, sample_bounding_box: BoundingBox) -> None:
        doc_id = uuid4()
        page_id = uuid4()
        # OCR Line confidence > 1.0
        with pytest.raises(ValidationError):
            OcrLine(
                document_id=doc_id,
                page_id=page_id,
                line_number=1,
                text="Word",
                bounding_box=sample_bounding_box,
                confidence=1.05,
            )

        # OCR Line confidence < 0.0
        with pytest.raises(ValidationError):
            OcrLine(
                document_id=doc_id,
                page_id=page_id,
                line_number=1,
                text="Word",
                bounding_box=sample_bounding_box,
                confidence=-0.01,
            )


class TestDocumentMetadataValidation:
    """Test suite for DocumentMetadata validation."""

    def test_valid_document_metadata(self, sample_document_metadata: DocumentMetadata) -> None:
        assert isinstance(sample_document_metadata.document_id, UUID)
        assert sample_document_metadata.total_pages == 2
        assert len(sample_document_metadata.sha256_hash) == 64

    def test_invalid_sha256_length_rejected(self, sample_user_id: UUID) -> None:
        with pytest.raises(ValidationError):
            DocumentMetadata(
                document_id=uuid4(),
                user_id=sample_user_id,
                file_name="invoice.pdf",
                mime_type="application/pdf",
                sha256_hash="tooshort",
                total_pages=1,
                file_size_bytes=100,
            )

    def test_invalid_sha256_non_hex_rejected(self, sample_user_id: UUID) -> None:
        with pytest.raises(
            ValidationError, match="sha256_hash must be a valid 64-character hexadecimal string"
        ):
            DocumentMetadata(
                document_id=uuid4(),
                user_id=sample_user_id,
                file_name="invoice.pdf",
                mime_type="application/pdf",
                sha256_hash="g" * 64,  # 'g' is not a hex character
                total_pages=1,
                file_size_bytes=100,
            )

    def test_invalid_enum_classification_rejected(self, sample_user_id: UUID) -> None:
        with pytest.raises(ValidationError):
            DocumentMetadata(
                document_id=uuid4(),
                user_id=sample_user_id,
                file_name="invoice.pdf",
                mime_type="application/pdf",
                sha256_hash="a" * 64,
                total_pages=1,
                file_size_bytes=100,
                document_classification="INVALID_CLASSIFICATION",  # type: ignore[arg-type]
            )

    def test_zero_pages_rejected(self, sample_user_id: UUID) -> None:
        with pytest.raises(ValidationError):
            DocumentMetadata(
                document_id=uuid4(),
                user_id=sample_user_id,
                file_name="invoice.pdf",
                mime_type="application/pdf",
                sha256_hash="a" * 64,
                total_pages=0,
                file_size_bytes=100,
            )


class TestUUIDValidation:
    """Test suite verifying UUID fields reject invalid strings."""

    def test_invalid_uuid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StandardError(
                code="ERR",
                message="Msg",
                correlation_id="not-a-valid-uuid",  # type: ignore[arg-type]
            )


class TestReasoningToneAndLanguageGuardrails:
    """Test suite ensuring reasoning claims reject prohibited non-objective assertions."""

    def test_disallowed_accusatory_terms_rejected(self) -> None:
        # Test "scam" rejection
        with pytest.raises(
            ValidationError, match="ReasoningClaim contains prohibited language 'scam'"
        ):
            ReasoningClaim(
                claim_id=uuid4(),
                type=ClaimType.POTENTIAL_ISSUE,
                title="Potential scam detected",
                description="This invoice looks suspicious.",
                field_references=[uuid4()],
                confidence=0.9,
            )

        # Test "fraud" rejection
        with pytest.raises(
            ValidationError, match="ReasoningClaim contains prohibited language 'fraud'"
        ):
            ReasoningClaim(
                claim_id=uuid4(),
                type=ClaimType.POTENTIAL_ISSUE,
                title="Suspicious activity",
                description="This constitutes clear billing fraud.",
                field_references=[uuid4()],
                confidence=0.9,
            )

        # Test "illegal" rejection
        with pytest.raises(
            ValidationError, match="ReasoningClaim contains prohibited language 'illegal'"
        ):
            ReasoningClaim(
                claim_id=uuid4(),
                type=ClaimType.TERM_REQUIRING_ATTENTION,
                title="Clause warning",
                description="This penalty fee is illegal under local law.",
                okf_rule_references=["OKF-01"],
                confidence=0.9,
            )

        # Test "definitely buy" rejection
        with pytest.raises(
            ValidationError, match="ReasoningClaim contains prohibited language 'definitely buy'"
        ):
            ReasoningClaim(
                claim_id=uuid4(),
                type=ClaimType.TERM_REQUIRING_ATTENTION,
                title="Recommendation",
                description="You should definitely buy this package immediately.",
                field_references=[uuid4()],
                confidence=0.9,
            )


class TestModelSerializationRoundtrip:
    """Test suite ensuring lossless JSON serialization and deserialization."""

    def test_final_result_roundtrip(
        self,
        sample_document_id: UUID,
        sample_user_id: UUID,
        sample_reasoning_claim: ReasoningClaim,
        sample_validation_check: ValidationCheck,
        sample_bounding_box: BoundingBox,
    ) -> None:
        summary = ResultSummary(
            headline="Review recommended: 1 overlap identified.",
            overall_status=DecisionStatus.REQUIRES_ATTENTION,
            total_flags=1,
            requires_human_verification=True,
        )
        flag = DecisionFlag(
            flag_id=uuid4(),
            claim_type=ClaimType.POTENTIAL_OVERLAP,
            label="Potential Overlap",
            message="Quoted price differs from prior agreement.",
            severity=ValidationSeverity.WARNING,
            associated_claim_id=sample_reasoning_claim.claim_id,
            field_ids=sample_reasoning_claim.field_references,
            bounding_boxes=[sample_bounding_box],
        )
        result = FinalDecisionSupportResult(
            result_id=uuid4(),
            document_id=sample_document_id,
            user_id=sample_user_id,
            summary=summary,
            flags=[flag],
            reasoning_claims=[sample_reasoning_claim],
            validation_checks=[sample_validation_check],
        )

        json_str = result.model_dump_json()
        assert isinstance(json_str, str)

        restored = FinalDecisionSupportResult.model_validate_json(json_str)
        assert restored.result_id == result.result_id
        assert restored.document_id == result.document_id
        assert restored.user_id == result.user_id
        assert len(restored.flags) == 1
        assert restored.flags[0].label == "Potential Overlap"
        assert restored.flags[0].bounding_boxes[0].x == 0.1
