"""Tests for Phase 1D: Strict Local/Offline OCR Gate."""

import io
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from before_you_pay.config import Settings
from before_you_pay.models import OcrResult
from before_you_pay.services.ocr import SpatialOcrEngine


class TestPhase1DOfflineOcr:
    """Unit and regression tests for strict local/offline OCR execution."""

    def test_settings_offline_only_default_and_override(self, monkeypatch):
        # Default is False
        settings = Settings()
        assert settings.offline_only is False

        # Override via environment variable
        monkeypatch.setenv("OFFLINE_ONLY", "true")
        settings_offline = Settings()
        assert settings_offline.offline_only is True

    @pytest.mark.anyio
    async def test_offline_only_flag_bypasses_vision_ocr_on_engine(self):
        engine = SpatialOcrEngine(offline_only=True)
        assert engine.is_offline_only is True

        # Create a sample test image in memory
        img = Image.new("RGB", (300, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        # Mock _vision_ocr_pass to ensure it is NEVER called
        with patch.object(engine, "_vision_ocr_pass", new_callable=AsyncMock) as mock_vision:
            result = await engine.process_document(
                document_id=uuid4(),
                file_bytes=img_bytes,
                mime_type="image/png",
            )
            assert isinstance(result, OcrResult)
            # Ensure cloud vision was not called
            mock_vision.assert_not_called()
            # Ensure engine_name is not gemini_vision_ocr
            assert result.engine_name != "gemini_vision_ocr"

    @pytest.mark.anyio
    async def test_offline_only_text_and_pdf_processing(self):
        engine = SpatialOcrEngine(offline_only=True)
        doc_id = uuid4()

        # Plain text stream in offline mode
        text_bytes = (
            b"Quotation\nBase Price: Rs. 10,00,000\nRoad Tax: Rs. 80,000\nTotal: Rs. 10,80,000"
        )
        result = await engine.process_document(
            document_id=doc_id,
            file_bytes=text_bytes,
            mime_type="text/plain",
        )
        assert isinstance(result, OcrResult)
        assert result.engine_name == "text_stream_ocr"
        assert len(result.pages[0].lines) >= 3
        assert result.engine_name != "gemini_vision_ocr"

    @pytest.mark.anyio
    async def test_recovery_passes_skip_pass4_in_offline_mode(self):
        engine = SpatialOcrEngine(offline_only=True)
        doc_id = uuid4()

        # Small image triggering degraded quality
        img = Image.new("RGB", (100, 50), color=(200, 200, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        with patch.object(engine, "_vision_ocr_pass", new_callable=AsyncMock) as mock_vision:
            result = await engine.process_document(
                document_id=doc_id,
                file_bytes=img_bytes,
                mime_type="image/png",
            )
            mock_vision.assert_not_called()
            assert result.engine_name != "gemini_vision_ocr"
