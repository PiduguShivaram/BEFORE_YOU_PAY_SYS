"""Comprehensive tests for pipeline services and domain engines."""

from uuid import UUID, uuid4

import pytest

from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    ClaimType,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OkfCategory,
    OkfQuery,
    OkfRuleEvidence,
    RagEvidenceChunk,
    RagQuery,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services import (
    DeterministicValidationEngine,
    FinancialExtractionEngine,
    OkfCatalogService,
    PipelineService,
    PreconditionChecker,
    SemanticReasoningEngine,
    SpatialOcrEngine,
    SqliteRagService,
)


class TestPreconditionChecker:
    """Tests for file validation and precondition checks."""

    def test_empty_file_rejected(self, sample_user_id: UUID) -> None:
        checker = PreconditionChecker()
        with pytest.raises(ContractViolationException, match="Uploaded file is empty"):
            checker.validate_file(b"", "application/pdf", sample_user_id)

    def test_unsupported_mime_rejected(self, sample_user_id: UUID) -> None:
        checker = PreconditionChecker()
        with pytest.raises(ContractViolationException, match="Unsupported document MIME type"):
            checker.validate_file(b"content", "application/zip", sample_user_id)

    def test_valid_pdf_precondition(self, sample_user_id: UUID) -> None:
        checker = PreconditionChecker()
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        res = checker.validate_file(pdf_bytes, "application/pdf", sample_user_id)
        assert res.is_readable is True
        assert len(res.sha256_hash) == 64


class TestSpatialOcrEngine:
    """Tests for spatial OCR lines and bounding box geometry."""

    @pytest.mark.anyio
    async def test_process_text_stream(self, sample_document_id: UUID) -> None:
        engine = SpatialOcrEngine()
        payload = b"Invoice 1042\nCloud Hosting: $120.00\nTotal: $120.00"
        result = await engine.process_document(sample_document_id, payload, "image/jpeg")

        assert result.document_id == sample_document_id
        assert len(result.pages) >= 1
        page = result.pages[0]
        assert len(page.lines) >= 2
        assert page.lines[0].bounding_box.coordinate_unit == CoordinateUnit.NORMALIZED_PERCENTAGE
        assert page.lines[0].confidence is None or page.lines[0].confidence > 0.90

    @pytest.mark.anyio
    async def test_process_real_binary_image(self, sample_document_id: UUID) -> None:
        """Verify native OCR reads a real binary PNG image."""
        import io

        from PIL import Image, ImageDraw

        img = Image.new("RGB", (600, 300), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), "Electric Utility Bill", fill=(0, 0, 0))
        draw.text((30, 80), "Energy Consumption: $85.50", fill=(0, 0, 0))
        draw.text((30, 130), "Total Payable: $85.50", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        engine = SpatialOcrEngine()
        result = await engine.process_document(sample_document_id, png_bytes, "image/png")

        assert result.document_id == sample_document_id
        assert len(result.pages) == 1
        page = result.pages[0]
        assert len(page.lines) >= 1
        assert any(
            "electric" in line.text.lower()
            or "utility" in line.text.lower()
            or "bill" in line.text.lower()
            or "85" in line.text
            for line in page.lines
        )


class TestFinancialExtractionEngine:
    """Tests for structured financial entity extraction."""

    @pytest.mark.anyio
    async def test_extraction_with_line_items_and_totals(
        self,
        sample_document_id: UUID,
        sample_user_id: UUID,
    ) -> None:
        engine = SpatialOcrEngine()
        payload = (
            b"Acme Corp\n"
            b"Consulting Service: $100.00\n"
            b"Server Maintenance: $50.00\n"
            b"Subtotal: $150.00\n"
            b"Tax: $15.00\n"
            b"Total: $165.00"
        )
        ocr_result = await engine.process_document(sample_document_id, payload, "image/jpeg")

        extractor = FinancialExtractionEngine()
        doc = extractor.extract(sample_document_id, sample_user_id, ocr_result)

        assert doc.document_id == sample_document_id
        assert doc.user_id == sample_user_id
        assert float(doc.total_amount.normalized_value) == 165.00
        assert doc.subtotal is not None
        assert float(doc.subtotal.normalized_value) == 150.00
        assert doc.tax_amount is not None
        assert float(doc.tax_amount.normalized_value) == 15.00
        assert len(doc.line_items) >= 2


class TestDeterministicValidationEngine:
    """Tests for exact mathematical calculations without LLM."""

    def test_arithmetic_sum_matches(
        self, sample_extracted_document: StructuredFinancialDocument
    ) -> None:
        validator = DeterministicValidationEngine()
        check = validator.check_arithmetic_sums(sample_extracted_document)
        assert check.status == ValidationStatus.PASS
        assert check.absolute_delta == 0.0

    def test_arithmetic_sum_mismatch_fails(
        self,
        sample_document_id: UUID,
        sample_user_id: UUID,
        sample_page_id: UUID,
        sample_line_id: UUID,
    ) -> None:
        prov = FieldProvenance(
            document_id=sample_document_id,
            page_id=sample_page_id,
            ocr_line_ids=[sample_line_id],
            raw_text="err",
        )
        item = LineItem(
            description=ExtractedField(
                field_id=uuid4(),
                field_key="desc",
                normalized_value="Work",
                confidence=0.9,
                provenance=prov,
            ),
            total_price=ExtractedField(
                field_id=uuid4(),
                field_key="price",
                normalized_value=100.00,
                confidence=0.9,
                provenance=prov,
            ),
        )
        doc = StructuredFinancialDocument(
            document_id=sample_document_id,
            user_id=sample_user_id,
            line_items=[item],
            total_amount=ExtractedField(
                field_id=uuid4(),
                field_key="total",
                normalized_value=150.00,  # Stated total 150 != itemized 100
                confidence=0.9,
                provenance=prov,
            ),
        )

        validator = DeterministicValidationEngine()
        check = validator.check_arithmetic_sums(doc)
        assert check.status == ValidationStatus.FAIL
        assert check.absolute_delta == 50.00
        assert check.severity == ValidationSeverity.CRITICAL


class TestOkfCatalogService:
    """Tests for curated Open Knowledge Format rule catalog."""

    @pytest.mark.anyio
    async def test_query_okf_rules(self) -> None:
        catalog = OkfCatalogService(catalog_path="./data/okf")
        query = OkfQuery(
            document_type=DocumentClassification.SUBSCRIPTION,
            categories=[OkfCategory.VERIFICATION_RULE],
            concept_keywords=["tax", "sum"],
        )
        rules = await catalog.query_rules(query)
        assert len(rules) >= 1
        assert any("OKF" in r.rule_id for r in rules)

    @pytest.mark.anyio
    async def test_get_specific_okf_rule(self) -> None:
        catalog = OkfCatalogService(catalog_path="./data/okf")
        rule = await catalog.get_rule_by_id("OKF-VERIF-MATH-01")
        assert rule is not None
        assert rule.rule_name == "Line Item Sum Integrity"


class TestSqliteRagServiceTenantIsolation:
    """Tests for user document store and tenant isolation using SQLite."""

    @pytest.mark.anyio
    async def test_multi_tenant_isolation(self, tmp_path: pytest.TempPathFactory) -> None:
        db_path = str(tmp_path / "test_user_docs.db")  # type: ignore[operator]
        rag = SqliteRagService(db_path=db_path)
        user_a = uuid4()
        user_b = uuid4()
        doc_a = uuid4()
        doc_b = uuid4()

        chunk_a = RagEvidenceChunk(
            evidence_id=uuid4(),
            user_id=user_a,
            source_document_id=doc_a,
            source_document_type=DocumentClassification.CONTRACT,
            page_number=1,
            source_text="User A secret contract terms: $500 monthly fee",
            similarity_score=0.9,
        )
        chunk_b = RagEvidenceChunk(
            evidence_id=uuid4(),
            user_id=user_b,
            source_document_id=doc_b,
            source_document_type=DocumentClassification.CONTRACT,
            page_number=1,
            source_text="User B standard terms: $200 monthly fee",
            similarity_score=0.9,
        )

        await rag.index_document_chunks(user_a, doc_a, [chunk_a])
        await rag.index_document_chunks(user_b, doc_b, [chunk_b])

        # User A querying should NEVER retrieve User B's chunk
        query_a = RagQuery(
            user_id=user_a,
            current_document_id=uuid4(),
            query_text="monthly fee contract",
            min_similarity=0.1,
        )
        results_a = await rag.retrieve(query_a)
        assert all(res.user_id == user_a for res in results_a)
        assert not any(res.user_id == user_b for res in results_a)


class TestSemanticReasoningEngine:
    """Tests for reasoning claim generation and tone constraints."""

    @pytest.mark.anyio
    async def test_reasoning_detects_overlap_and_rules(
        self,
        sample_extracted_document: StructuredFinancialDocument,
        sample_rag_chunk: RagEvidenceChunk,
        sample_okf_rule: OkfRuleEvidence,
    ) -> None:
        engine = SemanticReasoningEngine()
        claims = await engine.generate_claims(
            document=sample_extracted_document,
            rag_evidence=[sample_rag_chunk],
            okf_evidence=[sample_okf_rule],
        )

        assert len(claims) >= 1
        for claim in claims:
            assert claim.type in {
                ClaimType.POTENTIAL_OVERLAP,
                ClaimType.POTENTIAL_ISSUE,
                ClaimType.REQUIRES_VERIFICATION,
                ClaimType.ADDITIONAL_CHARGE_DETECTED,
                ClaimType.TERM_REQUIRING_ATTENTION,
            }
            # Verify claim is not orphaned
            total_refs = (
                len(claim.field_references)
                + len(claim.rag_evidence_references)
                + len(claim.okf_rule_references)
                + len(claim.validation_references)
            )
            assert total_refs > 0


class TestPipelineServiceEndToEnd:
    """End-to-end integration test of complete 7-stage workflow."""

    @pytest.mark.anyio
    async def test_run_full_pipeline(self, sample_user_id: UUID) -> None:
        pipeline = PipelineService()
        doc_id = uuid4()
        file_bytes = (
            b"Monthly Cloud Subscription\nStorage add-on: $25.00\nSubtotal: $25.00\nTotal: $25.00"
        )
        result = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=sample_user_id,
            file_bytes=file_bytes,
            mime_type="text/plain",
            document_type_hint=DocumentClassification.SUBSCRIPTION,
        )

        assert result.document_id == doc_id
        assert result.user_id == sample_user_id
        assert result.summary.total_flags >= 0
        assert len(result.validation_checks) >= 1
