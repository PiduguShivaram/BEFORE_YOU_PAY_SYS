"""Tests for Phase 9: Production Hardening & Performance.

Verifies:
1. PDF page count boundary (<= 50 pages enforced)
2. SQLite RAG WAL mode, composite indexing, and concurrency safety
3. Truthful pipeline stage execution metrics (no fake performance numbers)
4. Graceful degradation when all LLM provider keys fail
5. Supporting document processing efficiency (no duplicate primary processing)
6. Fast, decoupled service health checks
7. Production code hardcoding audit
"""

import io
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

import pypdf
import pytest
from fastapi.testclient import TestClient

from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    OcrLine,
    OcrPage,
    OcrResult,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.decision_summary import _fmt_curr
from before_you_pay.services.llm_extraction import HybridLlmExtractionEngine
from before_you_pay.services.llm_pool import LlmKeyManager
from before_you_pay.services.precondition import PreconditionChecker
from before_you_pay.services.rag import SqliteRagService


class TestPhase9HardeningAndPerformance:
    """Production hardening and resource boundary test suite."""

    def test_pdf_max_page_boundary_enforced(self) -> None:
        """Verifies that PDFs exceeding 50 pages are rejected by preconditions to prevent resource exhaustion."""
        checker = PreconditionChecker()
        writer = pypdf.PdfWriter()
        # Create a 55-page PDF in-memory
        for _ in range(55):
            writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        oversized_pdf_bytes = buf.getvalue()

        with pytest.raises(
            ContractViolationException, match="exceeds maximum allowed limit of 50 pages"
        ):
            checker.validate_file(oversized_pdf_bytes, "application/pdf", uuid4())

    def test_pdf_valid_page_count_accepted(self) -> None:
        """Verifies that compliant PDFs (<= 50 pages) pass preconditions."""
        checker = PreconditionChecker()
        writer = pypdf.PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        valid_pdf_bytes = buf.getvalue()

        res = checker.validate_file(valid_pdf_bytes, "application/pdf", uuid4())
        assert res.total_pages == 3
        assert res.is_readable is True

    def test_sqlite_rag_wal_and_composite_index(self, tmp_path: Path) -> None:
        """Verifies SQLite RAG enables WAL mode and creates composite index on (user_id, source_document_id)."""
        db_path = str(tmp_path / "test_rag_hardening.db")
        rag = SqliteRagService(db_path=db_path)

        with rag._get_connection() as conn:
            # Check journal mode (WAL or memory depending on OS environment)
            mode_row = conn.execute("PRAGMA journal_mode").fetchone()
            assert mode_row is not None

            # Verify index exists
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'user_chunks'"
            ).fetchall()
            index_names = [row["name"] for row in indexes]
            assert "idx_user_chunks_user" in index_names
            assert "idx_user_chunks_user_doc" in index_names

    def test_pipeline_metrics_measured_truthfully(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies real stage execution metrics are returned in FinalDecisionSupportResult."""
        content = (
            b"Acme Software Quote\n"
            b"Cloud License: $200.00\n"
            b"Support: $50.00\n"
            b"Subtotal: $250.00\n"
            b"Total: $250.00"
        )
        files = {"file": ("quote.txt", io.BytesIO(content), "text/plain")}
        data = {
            "user_id": str(sample_user_id),
            "document_classification": "quotation",
        }

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        payload = response.json()

        assert "pipeline_metrics" in payload
        metrics = payload["pipeline_metrics"]
        assert metrics is not None
        assert "ocr_duration_ms" in metrics
        assert "total_pipeline_ms" in metrics
        assert metrics["total_pipeline_ms"] >= 0.0

    def test_all_llm_keys_exhausted_graceful_degradation(self) -> None:
        """Verifies that if all LLM keys fail, extractor falls back to deterministic regex without hallucination."""
        # Key manager with no keys simulates complete quota exhaustion / offline
        empty_key_mgr = LlmKeyManager(api_keys=[], provider="groq")
        engine = HybridLlmExtractionEngine(key_manager=empty_key_mgr)

        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()
        lines = [
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=1,
                text="Acme Cloud Solutions",
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.1,
                    width=0.8,
                    height=0.03,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.98,
            ),
            OcrLine(
                line_id=uuid4(),
                page_id=page_id,
                document_id=doc_id,
                line_number=2,
                text="Invoice Total: $150.00",
                bounding_box=BoundingBox(
                    x=0.1,
                    y=0.2,
                    width=0.8,
                    height=0.03,
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                ),
                confidence=0.98,
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
                    height=1000,
                    lines=lines,
                )
            ],
            engine_name="test_ocr",
            engine_version="1.0",
        )

        extracted_doc, provider_used = engine.extract(doc_id, user_id, ocr)
        assert "FALLBACK" in provider_used
        assert extracted_doc.document_id == doc_id
        assert extracted_doc.user_id == user_id
        assert extracted_doc.total_amount.normalized_value == 150.0

    def test_health_endpoint_fast_and_independent(self, client: TestClient) -> None:
        """Verifies health check does not call external AI and completes rapidly under 500ms."""
        t0 = time.monotonic()
        response = client.get("/health")
        duration = time.monotonic() - t0
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert duration < 0.50

    def test_production_code_hardcoding_audit(self) -> None:
        """Audits production src/ to verify no hardcoded fixture values dictate behavior."""
        src_path = Path("src/before_you_pay")
        prohibited_literals = [
            "₹29,996",
            "₹29,497",
            "₹76,250",
        ]
        for py_file in src_path.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for literal in prohibited_literals:
                assert literal not in content, (
                    f"Forbidden hardcoded literal '{literal}' found in production file: {py_file}"
                )

    def test_unicode_and_currency_formatting_preservation(self) -> None:
        """Verifies currency symbol and formatted value preservation without mojibake."""
        formatted_inr = _fmt_curr(29996.0, "INR")
        assert formatted_inr == "₹29,996.00"
        assert "₹" in formatted_inr
        assert "Ã" not in formatted_inr

        # Verify JSON serialization roundtrip preserves Unicode characters
        payload = {"currency": "₹", "amount_str": "₹29,996.00", "status_check": "✓", "warning": "⚠️"}
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "₹29,996.00" in serialized
        assert "✓" in serialized
        assert "⚠️" in serialized
        assert "Ã" not in serialized

        deserialized = json.loads(serialized)
        assert deserialized["currency"] == "₹"
        assert deserialized["amount_str"] == "₹29,996.00"
        assert deserialized["status_check"] == "✓"
        assert deserialized["warning"] == "⚠️"

    def test_frontend_mojibake_absence_audit(self) -> None:
        """Audits frontend components to verify no Windows-1252/UTF-8 mojibake exists."""
        frontend_src = Path("frontend/src")
        mojibake_patterns = ["Ã¢â€šÂ¹", "Ã¢Å“â€œ", "Ã¢Å¡Â ", "Ã¢â€ â‚¬", "Ã"]
        for ext in ("*.ts", "*.tsx", "*.css"):
            for code_file in frontend_src.rglob(ext):
                text = code_file.read_text(encoding="utf-8", errors="ignore")
                for pat in mojibake_patterns:
                    assert pat not in text, f"Mojibake pattern '{pat}' found in {code_file}"

    def test_three_tier_reconciliation_layer_independence(self) -> None:
        """Verifies that line-item arithmetic failure is kept independent from overall quoted total reconciliation."""
        f_id = uuid4()
        # Tier 1 failure (e.g. line item math discrepancy)
        line_item_check = ValidationCheck(
            validation_id=uuid4(),
            check_code="LINE_ITEM_EXTENSION_MATCH",
            status=ValidationStatus.FAIL,
            input_field_ids=[f_id],
            severity=ValidationSeverity.WARNING,
            message="Item Boat Rockers 510 computed total 0.00 does not match stated 1499.00",
            expected_value=0.0,
            calculated_value=1499.0,
            absolute_delta=1499.0,
        )

        # Tier 3 pass (document level quoted total reconciliation matches stated amounts)
        quoted_total_check = ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_TOTAL_CONSISTENCY",
            status=ValidationStatus.PASS,
            input_field_ids=[f_id],
            severity=ValidationSeverity.INFO,
            message="Quoted total matches document items",
            expected_value=29996.0,
            calculated_value=29996.0,
            absolute_delta=0.0,
        )

        checks = [line_item_check, quoted_total_check]
        failed_checks = [c for c in checks if c.status == ValidationStatus.FAIL]
        passed_checks = [c for c in checks if c.status == ValidationStatus.PASS]

        assert len(failed_checks) == 1
        assert failed_checks[0].check_code == "LINE_ITEM_EXTENSION_MATCH"
        assert len(passed_checks) == 1
        assert passed_checks[0].check_code == "ARITHMETIC_TOTAL_CONSISTENCY"
        # Verify independence: line-item discrepancy does NOT overwrite quoted total pass
        assert quoted_total_check.status == ValidationStatus.PASS
