"""Integration tests verifying active API endpoints: /health, /analyze, and /documents."""

import io
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Verifies service health checks."""

    def test_root_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app_name"] == "Before You Pay"
        assert "version" in data
        assert "timestamp" in data

    def test_prefixed_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestDocumentUploadAndAnalyze:
    """Verifies the core mobile endpoints: /analyze and /documents."""

    def test_post_analyze_multipart_upload(self, client: TestClient, sample_user_id: UUID) -> None:
        """Test full 7-stage end-to-end execution on /analyze endpoint."""
        file_content = (
            b"Acme Tech Quote\n"
            b"Monthly Retainer: $100.00\n"
            b"Subtotal: $100.00\n"
            b"Tax: $10.00\n"
            b"Total: $110.00"
        )
        files = {"file": ("quote.txt", io.BytesIO(file_content), "text/plain")}
        data = {"user_id": str(sample_user_id), "document_classification": "quotation"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["user_id"] == str(sample_user_id)
        assert "summary" in res_data
        assert "summary" in res_data
        assert "flags" in res_data
        assert "validation_checks" in res_data

    def test_post_analyze_real_image_upload(self, client: TestClient, sample_user_id: UUID) -> None:
        """Test full 7-stage end-to-end execution on /analyze endpoint with real PNG image."""
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (600, 300), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), "Acme Medical Invoice #501", fill=(0, 0, 0))
        draw.text((30, 80), "Consultation Fee: $150.00", fill=(0, 0, 0))
        draw.text((30, 130), "Total: $150.00", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        files = {"file": ("bill.png", io.BytesIO(png_bytes), "image/png")}
        data = {"user_id": str(sample_user_id), "document_classification": "bill"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["user_id"] == str(sample_user_id)
        assert "summary" in res_data
        assert "flags" in res_data
        assert "validation_checks" in res_data

    def test_post_documents_indexes_past_record(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Test saving a past agreement or warranty into user's RAG index."""
        payload = {
            "user_id": str(sample_user_id),
            "document_id": str(uuid4()),
            "document_type": "contract",
            "page_number": 1,
            "text_content": "Agreement: Monthly Cloud Hosting agreed at $80.00 through 2026.",
        }
        response = client.post("/api/v1/documents", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexed"
        assert data["chunks_indexed"] == 1
        assert data["user_id"] == str(sample_user_id)

    def test_analyze_blurry_empty_file_rejected(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Test that empty file is rejected with 422."""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        data = {"user_id": str(sample_user_id)}
        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "CONTRACT_VIOLATION"

    def test_invalid_user_uuid_rejected(self, client: TestClient) -> None:
        """Test that invalid user UUID is rejected."""
        files = {"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")}
        data = {"user_id": "not-a-uuid"}
        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 422

    def test_post_analyze_stream_progressive_events(
        self, client: TestClient, sample_user_id: UUID
    ) -> None:
        """Verify real-time progressive SSE updates from /analyze/stream."""
        file_content = (
            b"Cloudflare Retainer Agreement\n"
            b"Pro Security Package 1x $250.00\n"
            b"Subtotal: $250.00\n"
            b"Tax: $25.00\n"
            b"Total: $275.00"
        )
        files = {"file": ("agreement.txt", io.BytesIO(file_content), "text/plain")}
        data = {"user_id": str(sample_user_id), "document_classification": "contract"}

        response = client.post("/api/v1/analyze/stream", data=data, files=files)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = [line for line in response.text.split("\n") if line.startswith("data: ")]
        assert len(events) >= 5
        stages_observed = [e for e in events if "stage" in e]
        assert any("precondition" in s for s in stages_observed)
        assert any("complete" in s for s in stages_observed)

    def test_real_uploaded_asset_e2e_api(self, client: TestClient, sample_user_id: UUID) -> None:
        """Verify actual uploaded binary file through real /analyze API endpoint into canonical response."""
        import os

        asset_path = os.path.join(
            os.path.dirname(__file__), "assets", "sample-bill-format-769x1024.png"
        )
        if not os.path.exists(asset_path):
            return

        with open(asset_path, "rb") as f:
            file_bytes = f.read()

        files = {"file": ("sample-bill.png", io.BytesIO(file_bytes), "image/png")}
        data = {"user_id": str(sample_user_id), "document_classification": "bill"}

        response = client.post("/api/v1/analyze", data=data, files=files)
        assert response.status_code == 200
        res = response.json()
        assert res["document_id"] is not None
        assert res["document"] is not None
        assert (
            res["document"]["vendor_name"]["normalized_value"] == "Zetran Technologies Pvt., Ltd."
        )
        assert float(res["document"]["total_amount"]["normalized_value"]) == 29996.0
        assert len(res["document"]["line_items"]) == 3
        assert len(res["validation_checks"]) >= 5
