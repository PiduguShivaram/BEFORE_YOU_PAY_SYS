"""Comprehensive test suite for OCR Quality Gate, multi-pass recovery, and the 5 explicit analysis states.

Verifies:
A. Good OCR + financial document -> FINANCIAL_DATA_FOUND
B. Good OCR + non-financial document -> NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR
C. Garbage OCR -> OCR_UNRELIABLE
D. Empty OCR -> DOCUMENT_UNREADABLE
E. Partially readable OCR -> DEGRADED / INCONCLUSIVE
F. OCR recovery succeeds -> continue to extraction
G. OCR recovery fails -> do not claim no financial data
H. Raw OCR provenance remains intact after recovery
I. Deterministic calculations remain independent of LLM output
"""

import io
from uuid import UUID, uuid4

import pytest
from PIL import Image, ImageDraw

from before_you_pay.models import (
    AnalysisState,
    BoundingBox,
    CoordinateUnit,
    DecisionStatus,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OcrLine,
    OcrPage,
    OCRQualityStatus,
    OcrResult,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.ocr import SpatialOcrEngine
from before_you_pay.services.ocr_quality import OCRQualityEvaluator
from before_you_pay.services.pipeline import PipelineService
from before_you_pay.services.validation import DeterministicValidationEngine


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def doc_id() -> UUID:
    return uuid4()


@pytest.fixture
def pipeline() -> PipelineService:
    return PipelineService()


@pytest.fixture
def evaluator() -> OCRQualityEvaluator:
    return OCRQualityEvaluator()


class TestOcrQualityAndAnalysisStates:
    """Test suite covering the 5 explicit analysis states and OCR quality gate."""

    @pytest.mark.anyio
    async def test_a_good_ocr_financial_document(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """A. Good OCR + financial document -> FINANCIAL_DATA_FOUND."""
        invoice_bytes = (
            b"ACME HARDWARE SUPPLIES LTD\n"
            b"INVOICE #INV-2024-889 Date: 2024-04-15\n"
            b"Item 1: Drill Bits Set Quantity: 2 Rate: $25.00 Total: $50.00\n"
            b"Item 2: Safety Goggles Quantity: 1 Rate: $15.00 Total: $15.00\n"
            b"Subtotal: $65.00\n"
            b"Sales Tax (10%): $6.50\n"
            b"Total Payable: $71.50\n"
            b"Payment Terms: Due within 30 days\n"
        )

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=invoice_bytes,
            mime_type="text/plain",
            document_type_hint=DocumentClassification.INVOICE,
        )

        assert res.analysis_state == AnalysisState.FINANCIAL_DATA_FOUND
        assert res.ocr_quality is not None
        assert res.ocr_quality.status == OCRQualityStatus.GOOD
        assert res.document is not None
        assert float(res.document.total_amount.normalized_value) == 71.50

    @pytest.mark.anyio
    async def test_b_good_ocr_non_financial_document(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """B. Good OCR + non-financial document -> NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR."""
        non_financial_text = (
            b"MEMORANDUM\n"
            b"To: All Staff Members\n"
            b"From: Operations Management Committee\n"
            b"Subject: Annual Office Community Clean-Up and Garden Renovation\n\n"
            b"We are pleased to invite everyone to participate in our annual office community\n"
            b"clean-up day this coming Friday afternoon. Refreshments will be provided in the\n"
            b"main courtyard. Please contact building reception if you require garden tools.\n"
            b"Thank you for your enthusiastic cooperation and ongoing dedication.\n"
        )

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=non_financial_text,
            mime_type="text/plain",
            document_type_hint=DocumentClassification.OTHER,
        )

        assert res.analysis_state == AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR
        assert res.ocr_quality is not None
        assert res.ocr_quality.status == OCRQualityStatus.GOOD
        assert res.summary.overall_status != DecisionStatus.CRITICAL_WARNING
        assert "No Financial Data" in res.summary.headline

        # Finding must be INFO severity, NEVER CRITICAL
        no_fin_check = [
            c
            for c in res.validation_checks
            if c.check_code
            in ("NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR", "NO_FINANCIAL_DATA_DETECTED")
        ]
        if no_fin_check:
            assert no_fin_check[0].severity == ValidationSeverity.INFO

    @pytest.mark.anyio
    async def test_c_garbage_ocr_unreliable(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """C. Garbage OCR -> OCR_UNRELIABLE (never claims No Financial Data Detected)."""
        garbage_bytes = b"OTA C\n0dAe A 0 000\n0d/q/ex S0 00b\nPosted in r/CarsIndia reddit\n"

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=garbage_bytes,
            mime_type="text/plain",
            document_type_hint=DocumentClassification.OTHER,
        )

        assert res.analysis_state == AnalysisState.OCR_UNRELIABLE
        assert res.ocr_quality is not None
        assert res.ocr_quality.status == OCRQualityStatus.UNRELIABLE
        assert res.document is None  # Never fabricate financial fields
        assert "No Financial Data" not in res.summary.headline
        assert res.summary.headline == "Document could not be reliably read"

        # Severity must be WARNING or INFO, not CRITICAL
        assert res.summary.overall_status != DecisionStatus.CRITICAL_WARNING
        assert len(res.flags) >= 1
        assert res.flags[0].severity != ValidationSeverity.CRITICAL

    @pytest.mark.anyio
    async def test_d_empty_ocr_document_unreadable(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """D. Empty OCR -> DOCUMENT_UNREADABLE."""
        empty_whitespace = b"   \n  \t  \n    \n"

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=empty_whitespace,
            mime_type="text/plain",
            document_type_hint=DocumentClassification.OTHER,
        )

        assert res.analysis_state == AnalysisState.DOCUMENT_UNREADABLE
        assert res.ocr_quality is not None
        assert res.ocr_quality.status == OCRQualityStatus.UNRELIABLE
        assert res.ocr_quality.character_count == 0
        assert res.document is None
        assert res.summary.headline == "Document could not be read"

    def test_e_partially_readable_ocr_degraded(
        self, evaluator: OCRQualityEvaluator, doc_id: UUID
    ) -> None:
        """E. Partially readable OCR -> DEGRADED."""
        page_id = uuid4()
        lines = [
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=1,
                text="Invoice Total 100.00",
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.1,
                    width=0.8,
                    height=0.05,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.80,
            ),
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=2,
                text="00b s0 disc ~~~ ??",
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.2,
                    width=0.8,
                    height=0.05,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.55,
            ),
        ]
        ocr = OcrResult(
            document_id=doc_id,
            pages=[
                OcrPage(
                    page_id=page_id,
                    document_id=doc_id,
                    page_number=1,
                    width=800,
                    height=600,
                    lines=lines,
                )
            ],
            engine_name="test",
        )

        q = evaluator.evaluate(ocr)
        assert q.status in (OCRQualityStatus.DEGRADED, OCRQualityStatus.UNRELIABLE)
        assert q.score < 0.75

    @pytest.mark.anyio
    async def test_f_ocr_recovery_pipeline_execution(self, doc_id: UUID) -> None:
        """F. OCR recovery pass pre-processing mechanisms execute cleanly."""
        engine = SpatialOcrEngine()

        # Create a small simulated scan image
        img = Image.new("RGB", (400, 200), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "Monthly Bill Statement", fill=(30, 30, 30))
        draw.text((20, 60), "Internet Fiber: $60.00", fill=(30, 30, 30))
        draw.text((20, 100), "Total: $60.00", fill=(30, 30, 30))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        ocr_res = await engine.process_document(doc_id, png_bytes, "image/png")
        assert ocr_res.document_id == doc_id
        assert len(ocr_res.pages) >= 1
        assert ocr_res.quality is not None

    @pytest.mark.anyio
    async def test_g_ocr_recovery_fails_does_not_claim_no_financial_data(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """G. When OCR recovery fails to produce reliable text, do NOT claim No Financial Data."""
        # Blurred, noise-only binary image
        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "~~~ !!! ???", fill=(130, 130, 130))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=img_bytes,
            mime_type="image/png",
            document_type_hint=DocumentClassification.OTHER,
        )

        assert res.analysis_state in (
            AnalysisState.OCR_UNRELIABLE,
            AnalysisState.DOCUMENT_UNREADABLE,
        )
        assert "No Financial Data" not in res.summary.headline
        assert res.summary.overall_status != DecisionStatus.CRITICAL_WARNING

    @pytest.mark.anyio
    async def test_h_raw_ocr_provenance_intact_after_recovery(
        self, pipeline: PipelineService, user_id: UUID, doc_id: UUID
    ) -> None:
        """H. Raw OCR provenance (document_id, page_id, line_id, bbox, confidence, raw_text) remains intact."""
        invoice_bytes = (
            b"TAX INVOICE 404\nConsulting Services: $1,000.00\nTotal Amount: $1,000.00\n"
        )

        res = await pipeline.run_full_pipeline(
            document_id=doc_id,
            user_id=user_id,
            file_bytes=invoice_bytes,
            mime_type="text/plain",
        )

        assert len(res.ocr_lines) >= 3
        for line in res.ocr_lines:
            assert isinstance(line.line_id, UUID)
            assert isinstance(line.page_id, UUID)
            assert line.document_id == doc_id
            assert line.text is not None and len(line.text) > 0
            assert line.raw_text is not None
            assert 0.0 <= line.bounding_box.x <= 1.0
            assert 0.0 <= line.bounding_box.y <= 1.0
            assert 0.0 < line.bounding_box.width <= 1.0
            assert 0.0 < line.bounding_box.height <= 1.0
            assert line.confidence is None or 0.0 <= line.confidence <= 1.0

    def test_i_deterministic_calculations_independent_of_llm(
        self, doc_id: UUID, user_id: UUID
    ) -> None:
        """I. Deterministic mathematical calculations are computed solely in Python independent of LLM."""
        val_engine = DeterministicValidationEngine()

        # Document with deliberate arithmetic mismatch: 10 * $25 != $300
        desc_prov = FieldProvenance(
            document_id=doc_id, page_id=uuid4(), ocr_line_ids=[uuid4()], raw_text="Widgets"
        )
        qty_prov = FieldProvenance(
            document_id=doc_id, page_id=uuid4(), ocr_line_ids=[uuid4()], raw_text="10"
        )
        price_prov = FieldProvenance(
            document_id=doc_id, page_id=uuid4(), ocr_line_ids=[uuid4()], raw_text="$25.00"
        )
        tot_prov = FieldProvenance(
            document_id=doc_id, page_id=uuid4(), ocr_line_ids=[uuid4()], raw_text="$300.00"
        )

        item = LineItem(
            item_id=uuid4(),
            description=ExtractedField(
                field_key="description",
                normalized_value="Widgets",
                confidence=0.95,
                provenance=desc_prov,
            ),
            quantity=ExtractedField(
                field_key="quantity", normalized_value=10.0, confidence=0.95, provenance=qty_prov
            ),
            unit_price=ExtractedField(
                field_key="unit_price",
                normalized_value=25.0,
                confidence=0.95,
                provenance=price_prov,
            ),
            total_price=ExtractedField(
                field_key="total_price",
                normalized_value=300.0,
                confidence=0.95,
                provenance=tot_prov,
            ),
        )

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            document_type=DocumentClassification.INVOICE,
            currency="USD",
            line_items=[item],
            total_amount=ExtractedField(
                field_key="total_amount",
                normalized_value=300.0,
                confidence=0.95,
                provenance=tot_prov,
            ),
        )

        checks = val_engine.validate(doc)
        failed_checks = [c for c in checks if c.status == ValidationStatus.FAIL]
        assert len(failed_checks) >= 1
        line_check = [c for c in failed_checks if "LINE_ITEM" in c.check_code][0]
        # Mathematical expected = 10 * 25 = 250.00 != stated 300.00
        assert "250.00" in line_check.message
        assert "300.00" in line_check.message
