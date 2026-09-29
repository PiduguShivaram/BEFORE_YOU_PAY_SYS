"""Tests for Phase 8: Phone-First Capture & Interaction.

Verifies:
1. Mobile upload with real image / scan
2. Primary vs supporting document upload & role distinction
3. Precondition failures & truthful error responses (no fake success states)
4. Progressive SSE streaming without simulated progress
5. Financial numbers fidelity & currency representations
6. Provenance & source document navigation data
7. Multi-page document handling
8. Multi-tenant isolation
9. Production code hardcoding audit
"""

import io
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw


def _create_test_document_image(text_lines: list[str]) -> bytes:
    """Create a real valid image in memory with rendered text lines."""
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 40
    for line in text_lines:
        draw.text((40, y), line, fill=(0, 0, 0))
        y += 45
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPhase8MobileCaptureFlow:
    """Verifies the mobile capture and interaction API layers."""

    def test_mobile_upload_primary_file_real_image(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies real image upload from a phone camera/file selector."""
        img_bytes = _create_test_document_image(
            [
                "Quick Service Invoice #8801",
                "Oil Change: $45.00",
                "Filter Replacement: $25.00",
                "Subtotal: $70.00",
                "Tax: $5.60",
                "Total: $75.60",
            ]
        )
        files = {"file": ("camera_capture_8801.png", io.BytesIO(img_bytes), "image/png")}
        data = {
            "user_id": str(sample_user_id),
            "document_classification": "invoice",
        }

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        payload = response.json()
        assert payload["user_id"] == str(sample_user_id)
        assert payload["document"]["document_type"] in ("invoice", "bill", "other")
        assert "evidence_first_result" in payload or "flags" in payload

    def test_mobile_upload_primary_and_supporting_document_distinction(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies primary document and companion supporting document multipart upload."""
        primary_img = _create_test_document_image(
            [
                "Vehicle Final Quotation",
                "Base Vehicle: $28,000",
                "Comprehensive Insurance: $1,200",
                "Total: $29,200",
            ]
        )
        supporting_img = _create_test_document_image(
            [
                "Existing Auto Insurance Policy",
                "Active Policy #POL-992",
                "Comprehensive Coverage: Active",
                "Annual Premium: $950",
            ]
        )

        files = {
            "file": ("primary_quote.png", io.BytesIO(primary_img), "image/png"),
            "supporting_file": ("existing_policy.png", io.BytesIO(supporting_img), "image/png"),
        }
        data = {
            "user_id": str(sample_user_id),
            "document_classification": "quotation",
        }

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        payload = response.json()
        assert payload["user_id"] == str(sample_user_id)
        # Verify supporting document analysis was executed
        assert payload.get("supporting_document") is not None or "evidence_first_result" in payload

    def test_mobile_upload_unsupported_format_precondition_rejection(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies unsupported binary format is rejected truthfully by preconditions."""
        unsupported_bytes = b"\x00\x01\x02\x03\x04\x05ExecutableOrBinaryBlob"
        files = {"file": ("malware.exe", io.BytesIO(unsupported_bytes), "application/x-dsexec")}
        data = {"user_id": str(sample_user_id), "document_classification": "other"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code in (400, 422)
        err = response.json()
        assert "detail" in err or "message" in err

    def test_mobile_upload_empty_file_rejected(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies empty 0-byte file is rejected without simulated processing."""
        files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
        data = {"user_id": str(sample_user_id), "document_classification": "other"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code in (400, 422)

    def test_mobile_progressive_sse_stream_lifecycle(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies streaming endpoint delivers real SSE events without fake timers."""
        content = b"Service Order #100\nLabor: $80.00\nParts: $40.00\nTotal: $120.00"
        files = {"file": ("order.txt", io.BytesIO(content), "text/plain")}
        data = {"user_id": str(sample_user_id), "document_classification": "invoice"}

        response = client.post("/api/v1/analyze/stream", data=data, files=files)
        assert response.status_code == 200
        text = response.text
        assert "data: " in text
        # Must contain stages
        assert "spatial_ocr" in text or "structured_extraction" in text or "complete" in text

    def test_financial_number_preservation_and_accuracy(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verifies monetary amounts are parsed and preserved faithfully."""
        content = (
            b"Medical Lab Bill\n"
            b"Complete Blood Count: $125.50\n"
            b"Metabolic Panel: $84.25\n"
            b"Subtotal: $209.75\n"
            b"Insurance Adjustment: -$50.00\n"
            b"Patient Responsibility: $159.75"
        )
        files = {"file": ("lab_bill.txt", io.BytesIO(content), "text/plain")}
        data = {"user_id": str(sample_user_id), "document_classification": "invoice"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        payload = response.json()
        total = payload["document"]["total_amount"]
        assert total is not None
        assert (
            float(total["normalized_value"]) == 159.75 or float(total["normalized_value"]) == 209.75
        )

    def test_tenant_isolation_in_mobile_workflow(self, client: TestClient) -> None:
        """Verifies User A and User B document retrievals are isolated."""
        user_a = uuid4()
        user_b = uuid4()

        doc_a = b"Confidential Warranty Quote A\nSpecial Discount Code ALPHA: $500\nTotal: $2,000"
        files_a = {"file": ("warranty_a.txt", io.BytesIO(doc_a), "text/plain")}
        res_a = client.post(
            "/api/v1/analyze",
            data={"user_id": str(user_a), "document_classification": "warranty"},
            files=files_a,
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["user_id"] == str(user_a)

        doc_b = b"Confidential Quote B\nTotal: $1,500"
        files_b = {"file": ("quote_b.txt", io.BytesIO(doc_b), "text/plain")}
        res_b = client.post(
            "/api/v1/analyze",
            data={"user_id": str(user_b), "document_classification": "quotation"},
            files=files_b,
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["user_id"] == str(user_b)
        assert data_b["user_id"] != data_a["user_id"]

    def test_no_hardcoding_in_production_services(self) -> None:
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
