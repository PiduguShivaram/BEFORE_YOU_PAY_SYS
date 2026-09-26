"""Spatial OCR engine producing normalized lines and bounding boxes from PDFs and images."""

import io
import logging
import sys
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pypdf
from PIL import Image, ImageFilter, ImageOps

from before_you_pay.models import BoundingBox, CoordinateUnit, OcrLine, OcrPage, OcrResult
from before_you_pay.models.analysis import OCRQualityResult, OCRQualityStatus
from before_you_pay.services.ocr_quality import OCRQualityEvaluator

logger = logging.getLogger(__name__)


class SpatialOcrEngine:
    """Production OCR engine producing normalized spatial lines and bounding boxes."""

    def __init__(self, engine_name: str = "spatial_layout_ocr", version: str = "1.0.0") -> None:
        self.engine_name = engine_name
        self.version = version
        self.quality_evaluator = OCRQualityEvaluator()

    async def process_document(
        self,
        document_id: UUID,
        file_bytes: bytes,
        mime_type: str,
    ) -> OcrResult:
        """Process document bytes with multi-pass OCR and deterministic quality gate."""
        start_time = time.monotonic()
        normalized_mime = mime_type.lower().split(";")[0].strip()

        if normalized_mime == "application/pdf":
            pages, engine_used = await self._process_pdf(document_id, file_bytes)
        else:
            pages, engine_used = await self._process_image(document_id, file_bytes)

        initial_result = OcrResult(
            document_id=document_id,
            pages=pages,
            engine_name=engine_used or self.engine_name,
            engine_version=self.version,
            processed_at=datetime.now(UTC),
            recovery_attempted=False,
            recovery_pass=1,
        )

        quality = self.quality_evaluator.evaluate(initial_result)
        initial_result = OcrResult(
            document_id=initial_result.document_id,
            pages=initial_result.pages,
            engine_name=initial_result.engine_name,
            engine_version=initial_result.engine_version,
            processed_at=initial_result.processed_at,
            recovery_attempted=False,
            recovery_pass=1,
            quality=quality,
        )

        # Trigger Multi-Pass Recovery for images if quality is degraded/unreliable or lacks financial digits
        if (
            quality.status != OCRQualityStatus.GOOD
            or not self._has_meaningful_financial_content(initial_result)
        ) and normalized_mime != "application/pdf":
            final_result = await self._attempt_recovery_passes(
                document_id, file_bytes, initial_result, quality
            )
        else:
            final_result = initial_result

        # Diagnostic logging for production observability (without exposing document text or secrets)
        duration = round(time.monotonic() - start_time, 3)
        total_lines = sum(len(p.lines) for p in final_result.pages)
        failure_category = None
        if total_lines == 0:
            failure_category = "OCR_EMPTY"
        elif final_result.quality and final_result.quality.status == OCRQualityStatus.UNRELIABLE:
            failure_category = "OCR_UNRELIABLE"

        logger.info(
            "OCR complete: engine=%s, input_type=%s, pages=%d, duration=%.3fs, lines=%d, quality=%s, failure_category=%s",
            final_result.engine_name,
            normalized_mime,
            len(final_result.pages),
            duration,
            total_lines,
            final_result.quality.status.value if final_result.quality else "UNKNOWN",
            failure_category or "NONE",
        )

        return final_result

    @staticmethod
    def _has_meaningful_financial_content(res: OcrResult) -> bool:
        """Check if recognized pages contain at least 4 digits representing financial figures."""
        digit_count = 0
        for p in res.pages:
            for l in p.lines:
                digit_count += sum(1 for c in l.text if c.isdigit())
        return digit_count >= 4

    @staticmethod
    def _has_meaningful_financial_content_lines(lines: list[OcrLine]) -> bool:
        """Check if recognized lines contain at least 4 digits representing financial figures."""
        digit_count = sum(sum(1 for c in l.text if c.isdigit()) for l in lines)
        return digit_count >= 4

    async def _attempt_recovery_passes(
        self,
        document_id: UUID,
        file_bytes: bytes,
        initial_result: OcrResult,
        initial_quality: OCRQualityResult,
    ) -> OcrResult:
        """Execute controlled Pass 2 (enhancement), Pass 3 (thresholding), or Pass 4 (Vision OCR)."""
        best_result = initial_result
        best_quality = initial_quality

        # If initial result was already from Vision OCR and produced lines, keep best
        if initial_result.engine_name == "gemini_vision_ocr" and initial_result.pages[0].lines:
            return initial_result

        try:
            base_img = Image.open(io.BytesIO(file_bytes))
            base_img = ImageOps.exif_transpose(base_img)
        except Exception:
            base_img = None

        # --- PASS 2: Preprocessed Image on Windows (Upscale, Grayscale, Contrast Normalization, Sharpening) ---
        if base_img is not None and sys.platform == "win32":
            try:
                img_p2 = self._preprocess_pass2(base_img)
                p2_pages = await self._run_winocr_on_pil(document_id, img_p2)
                if p2_pages and p2_pages[0].lines:
                    res_p2 = OcrResult(
                        document_id=document_id,
                        pages=p2_pages,
                        engine_name="winocr",
                        engine_version=f"{self.version}-pass2-preprocessed",
                        processed_at=datetime.now(UTC),
                        recovery_attempted=True,
                        recovery_pass=2,
                    )
                    q2 = self.quality_evaluator.evaluate(res_p2)
                    res_p2 = OcrResult(
                        document_id=res_p2.document_id,
                        pages=res_p2.pages,
                        engine_name=res_p2.engine_name,
                        engine_version=res_p2.engine_version,
                        processed_at=res_p2.processed_at,
                        recovery_attempted=True,
                        recovery_pass=2,
                        quality=q2,
                    )
                    if q2.score > best_quality.score:
                        best_result = res_p2
                        best_quality = q2
                    if q2.status == OCRQualityStatus.GOOD and self._has_meaningful_financial_content(res_p2):
                        return best_result
            except Exception:
                pass

        # --- PASS 3: Adaptive Binarization / Thresholding (Windows only) ---
        if base_img is not None and sys.platform == "win32":
            try:
                img_p3 = self._preprocess_pass3(base_img)
                p3_pages = await self._run_winocr_on_pil(document_id, img_p3)
                if p3_pages and p3_pages[0].lines:
                    res_p3 = OcrResult(
                        document_id=document_id,
                        pages=p3_pages,
                        engine_name="winocr",
                        engine_version=f"{self.version}-pass3-binarized",
                        processed_at=datetime.now(UTC),
                        recovery_attempted=True,
                        recovery_pass=3,
                    )
                    q3 = self.quality_evaluator.evaluate(res_p3)
                    res_p3 = OcrResult(
                        document_id=res_p3.document_id,
                        pages=res_p3.pages,
                        engine_name=res_p3.engine_name,
                        engine_version=res_p3.engine_version,
                        processed_at=res_p3.processed_at,
                        recovery_attempted=True,
                        recovery_pass=3,
                        quality=q3,
                    )
                    if q3.score > best_quality.score:
                        best_result = res_p3
                        best_quality = q3
            except Exception:
                pass

        # --- PASS 4: Multimodal Vision OCR (Cross-platform production engine) ---
        if best_quality.status != OCRQualityStatus.GOOD or not self._has_meaningful_financial_content(best_result):
            try:
                p4_pages = await self._vision_ocr_pass(document_id, file_bytes)
                if p4_pages and p4_pages[0].lines:
                    res_p4 = OcrResult(
                        document_id=document_id,
                        pages=p4_pages,
                        engine_name="gemini_vision_ocr",
                        engine_version=f"{self.version}-pass4-vision",
                        processed_at=datetime.now(UTC),
                        recovery_attempted=True,
                        recovery_pass=4,
                    )
                    q4 = self.quality_evaluator.evaluate(res_p4)
                    res_p4 = OcrResult(
                        document_id=res_p4.document_id,
                        pages=res_p4.pages,
                        engine_name=res_p4.engine_name,
                        engine_version=res_p4.engine_version,
                        processed_at=res_p4.processed_at,
                        recovery_attempted=True,
                        recovery_pass=4,
                        quality=q4,
                    )
                    if q4.score > best_quality.score or self._has_meaningful_financial_content(res_p4):
                        best_result = res_p4
                        best_quality = q4
                    if q4.status in (OCRQualityStatus.GOOD, OCRQualityStatus.MODERATE):
                        return best_result
            except Exception as e:
                logger.warning("Pass 4 Vision OCR recovery failed: %s", e)

        return best_result

    async def _vision_ocr_pass(
        self,
        document_id: UUID,
        file_bytes: bytes,
    ) -> list[OcrPage] | None:
        """Vision-based OCR using Google Gemini multimodal generateContent API with key failover."""
        import base64
        import json
        import httpx
        from before_you_pay.config import get_settings

        settings = get_settings()
        keys = settings.gemini_api_keys
        if not keys:
            logger.warning("No Gemini API keys configured for Vision OCR.")
            return None

        # Determine MIME type
        mime = "image/png"
        if file_bytes.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
            mime = "image/webp"

        b64 = base64.b64encode(file_bytes).decode("utf-8")

        prompt = (
            "Extract all printed text and tabular lines from this document image in top-to-bottom reading order.\n"
            "Return a JSON array of objects:\n"
            '[\n  {"line_number": 1, "text": "...", "box_2d": [ymin, xmin, ymax, xmax]}\n]\n'
            "Coordinates in box_2d are normalized between 0 and 1000 ([ymin, xmin, ymax, xmax]).\n"
            "CRITICAL: Do not hallucinate. Faithfully preserve currency symbols, punctuation, item names, rates, discounts, quantities, subtotals, shipping, taxes, and totals.\n"
            "Transcribe every line, row, label, and number with exact character precision."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": mime, "data": b64}},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }

        # Candidate models to try in cascading order
        models = [
            settings.gemini_model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
        ]
        unique_models = []
        for m in models:
            if m and m not in unique_models:
                unique_models.append(m)

        for key in keys:
            for model in unique_models:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    f"?key={key}"
                )
                try:
                    async with httpx.AsyncClient(timeout=40.0) as client:
                        resp = await client.post(url, json=payload)
                        if resp.status_code in (429, 503):
                            logger.info("Key or model rate-limited (status %d), rotating...", resp.status_code)
                            break  # rotate to next key
                        if resp.status_code == 404:
                            continue  # model not available, try next model
                        if resp.status_code != 200:
                            continue

                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if not candidates or not candidates[0].get("content", {}).get("parts"):
                            continue

                        raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                        if raw_text.startswith("```json"):
                            raw_text = raw_text[7:]
                        if raw_text.startswith("```"):
                            raw_text = raw_text[3:]
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3]
                        raw_text = raw_text.strip()

                        parsed_lines = json.loads(raw_text)
                        if not isinstance(parsed_lines, list) or not parsed_lines:
                            continue

                        page_id = uuid4()
                        ocr_lines: list[OcrLine] = []
                        for idx, item in enumerate(parsed_lines, start=1):
                            line_text = str(item.get("text", "")).strip()
                            if not line_text:
                                continue
                            box = item.get("box_2d") or item.get("box") or [0, 0, 1000, 1000]
                            ymin, xmin, ymax, xmax = box[0], box[1], box[2], box[3]
                            x_norm = max(0.0, min(0.99, xmin / 1000.0))
                            y_norm = max(0.0, min(0.99, ymin / 1000.0))
                            w_norm = max(0.01, min(1.0 - x_norm, (xmax - xmin) / 1000.0))
                            h_norm = max(0.01, min(1.0 - y_norm, (ymax - ymin) / 1000.0))

                            bbox = BoundingBox(
                                x=round(x_norm, 4),
                                y=round(y_norm, 4),
                                width=round(w_norm, 4),
                                height=round(h_norm, 4),
                                coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                            )
                            ocr_lines.append(
                                OcrLine(
                                    line_id=uuid4(),
                                    page_id=page_id,
                                    document_id=document_id,
                                    line_number=idx,
                                    text=line_text,
                                    raw_text=line_text,
                                    bounding_box=bbox,
                                    confidence=0.96,
                                )
                            )

                        if ocr_lines:
                            return [
                                OcrPage(
                                    page_id=page_id,
                                    document_id=document_id,
                                    page_number=1,
                                    width=1000,
                                    height=1400,
                                    dpi=300,
                                    lines=ocr_lines,
                                )
                            ]
                except Exception as e:
                    logger.warning("Error during Vision OCR request: %s", e)
                    continue

        return None

    def _preprocess_pass2(self, img: Image.Image) -> Image.Image:
        """Pass 2: Upscale small scans, convert grayscale, normalize contrast, sharpen edges."""
        w, h = img.size
        processed = img.copy()

        if w < 1600 or h < 1600:
            scale = min(2.0, max(1.5, 1800.0 / max(w, h)))
            new_w, new_h = int(w * scale), int(h * scale)
            processed = processed.resize((new_w, new_h), Image.Resampling.LANCZOS)

        if processed.mode not in ("L", "1"):
            processed = processed.convert("L")

        processed = ImageOps.autocontrast(processed, cutoff=2)
        processed = processed.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=3))
        return processed.convert("RGB")

    def _preprocess_pass3(self, img: Image.Image) -> Image.Image:
        """Pass 3: Otsu global threshold binarization."""
        gray = img.convert("L")
        hist = gray.histogram()
        total = sum(hist)
        sum_all = sum(i * hist[i] for i in range(256))
        sum_b, w_b, var_max, threshold = 0.0, 0.0, 0.0, 128
        for i in range(256):
            w_b += hist[i]
            if w_b == 0:
                continue
            w_f = total - w_b
            if w_f == 0:
                break
            sum_b += i * hist[i]
            m_b = sum_b / w_b
            m_f = (sum_all - sum_b) / w_f
            var_between = w_b * w_f * ((m_b - m_f) ** 2)
            if var_between > var_max:
                var_max = var_between
                threshold = i

        binarized = gray.point(lambda p: 255 if p > threshold else 0, mode="1")
        return binarized.convert("RGB")

    async def _run_winocr_on_pil(self, document_id: UUID, rgb_img: Image.Image) -> list[OcrPage]:
        """Helper to run winocr on an in-memory PIL image and cluster lines."""
        if sys.platform != "win32":
            return []

        try:
            import winocr
        except ImportError:
            return []

        page_id = uuid4()
        width, height = rgb_img.size
        ocr_res = await winocr.recognize_pil(rgb_img, "en")
        if not ocr_res or not ocr_res.lines:
            return []

        all_words = []
        for raw_line in ocr_res.lines:
            for w in raw_line.words:
                if w.text.strip():
                    all_words.append(w)

        if not all_words:
            return []

        lines = self._cluster_words_into_lines(all_words, page_id, document_id, width, height)
        return [
            OcrPage(
                page_id=page_id,
                document_id=document_id,
                page_number=1,
                width=width,
                height=height,
                dpi=300,
                lines=lines,
            )
        ]

    def _cluster_words_into_lines(
        self,
        words: list,
        page_id: UUID,
        document_id: UUID,
        width: int,
        height: int,
    ) -> list[OcrLine]:
        """Cluster OCR words into 2D reading-order horizontal lines using spatial geometry."""
        if not words:
            return []

        words_sorted = sorted(words, key=lambda w: (w.bounding_rect.y, w.bounding_rect.x))

        clusters: list[dict] = []
        for w in words_sorted:
            wy = w.bounding_rect.y
            wh = w.bounding_rect.height
            w_center_y = wy + wh / 2.0

            matched_cluster = None
            for cl in clusters:
                cl_center_y = cl["center_y"]
                cl_h = cl["height"]
                if abs(w_center_y - cl_center_y) <= max(wh, cl_h) * 0.55:
                    matched_cluster = cl
                    break

            if matched_cluster:
                matched_cluster["words"].append(w)
                all_w = matched_cluster["words"]
                matched_cluster["min_y"] = min(x.bounding_rect.y for x in all_w)
                matched_cluster["max_y"] = max(
                    x.bounding_rect.y + x.bounding_rect.height for x in all_w
                )
                matched_cluster["height"] = matched_cluster["max_y"] - matched_cluster["min_y"]
                matched_cluster["center_y"] = (
                    matched_cluster["min_y"] + matched_cluster["max_y"]
                ) / 2.0
            else:
                clusters.append(
                    {
                        "center_y": w_center_y,
                        "min_y": wy,
                        "max_y": wy + wh,
                        "height": wh,
                        "words": [w],
                    }
                )

        clusters.sort(key=lambda cl: cl["min_y"])

        ocr_lines: list[OcrLine] = []
        for idx, cl in enumerate(clusters, start=1):
            cl["words"].sort(key=lambda w: w.bounding_rect.x)
            text = " ".join(w.text for w in cl["words"]).strip()
            if not text:
                continue

            min_x = min(w.bounding_rect.x for w in cl["words"])
            max_x = max(w.bounding_rect.x + w.bounding_rect.width for w in cl["words"])
            min_y = cl["min_y"]
            max_y = cl["max_y"]

            box = BoundingBox(
                x=round(max(0.0, min(0.99, min_x / width)), 4),
                y=round(max(0.0, min(0.99, min_y / height)), 4),
                width=round(max(0.01, min(1.0 - (min_x / width), (max_x - min_x) / width)), 4),
                height=round(max(0.01, min(1.0 - (min_y / height), (max_y - min_y) / height)), 4),
                coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
            )

            ocr_lines.append(
                OcrLine(
                    line_id=uuid4(),
                    page_id=page_id,
                    document_id=document_id,
                    line_number=idx,
                    text=text,
                    raw_text=text,
                    bounding_box=box,
                    confidence=0.92,
                )
            )

        return ocr_lines

    async def _process_pdf(self, document_id: UUID, file_bytes: bytes) -> tuple[list[OcrPage], str]:
        """Extract multi-page text and compute normalized bounding box geometry from PDF."""
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            ocr_pages: list[OcrPage] = []

            for idx, page in enumerate(reader.pages, start=1):
                page_id = uuid4()
                width = int(float(page.mediabox.width) if page.mediabox else 612)
                height = int(float(page.mediabox.height) if page.mediabox else 792)

                text_content = page.extract_text() or ""
                raw_lines = [line.strip() for line in text_content.splitlines() if line.strip()]

                lines: list[OcrLine] = []
                total_lines = len(raw_lines) or 1
                line_height_norm = min(0.04, 0.85 / total_lines)

                for line_idx, line_text in enumerate(raw_lines, start=1):
                    y_pos = min(0.90, 0.05 + (line_idx - 1) * (line_height_norm * 1.1))
                    box = BoundingBox(
                        x=0.08,
                        y=y_pos,
                        width=0.84,
                        height=line_height_norm,
                        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                    )
                    lines.append(
                        OcrLine(
                            line_id=uuid4(),
                            page_id=page_id,
                            document_id=document_id,
                            line_number=line_idx,
                            text=line_text,
                            raw_text=line_text,
                            bounding_box=box,
                            confidence=0.95,
                        )
                    )

                if lines:
                    ocr_pages.append(
                        OcrPage(
                            page_id=page_id,
                            document_id=document_id,
                            page_number=idx,
                            width=width,
                            height=height,
                            dpi=300,
                            lines=lines,
                        )
                    )

            if ocr_pages:
                return ocr_pages, "spatial_pypdf"

            # Scanned / image-only PDF: extract embedded page images
            scanned_pages: list[OcrPage] = []
            engine_used = "scanned_pdf_ocr"
            for idx, page in enumerate(reader.pages, start=1):
                for img_obj in page.images:
                    p_res, eng = await self._process_image(document_id, img_obj.data)
                    if p_res and p_res[0].lines:
                        page_obj = p_res[0]
                        scanned_pages.append(
                            OcrPage(
                                page_id=page_obj.page_id,
                                document_id=document_id,
                                page_number=idx,
                                width=page_obj.width,
                                height=page_obj.height,
                                dpi=page_obj.dpi,
                                lines=page_obj.lines,
                            )
                        )
                        engine_used = eng
                        break
            if scanned_pages:
                return scanned_pages, engine_used

        except Exception as e:
            logger.warning("PDF processing failed: %s", e)

        return await self._process_image(document_id, file_bytes)

    async def _process_image(self, document_id: UUID, file_bytes: bytes) -> tuple[list[OcrPage], str]:
        """Process image file with platform-specific OCR (winocr on Windows, Vision OCR on Linux/Vercel)."""
        img = None
        width, height = 1080, 1920
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img = ImageOps.exif_transpose(img)
            width, height = img.size
        except Exception:
            img = None

        page_id = uuid4()
        lines: list[OcrLine] = []
        engine_used = self.engine_name

        # 1. Native Windows OCR on real image pixels (local Windows path)
        if img is not None and sys.platform == "win32":
            try:
                import winocr

                # Preprocess RGBA/transparent images onto clean white background
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    alpha_img = img.convert("RGBA") if img.mode != "RGBA" else img
                    bg.paste(alpha_img, mask=alpha_img.split()[-1])
                    rgb_img = bg
                elif img.mode != "RGB":
                    rgb_img = img.convert("RGB")
                else:
                    rgb_img = img

                ocr_res = await winocr.recognize_pil(rgb_img, "en")
                if ocr_res and ocr_res.lines:
                    all_words = []
                    for raw_line in ocr_res.lines:
                        for w in raw_line.words:
                            if w.text.strip():
                                all_words.append(w)

                    if all_words:
                        winocr_lines = self._cluster_words_into_lines(
                            all_words, page_id, document_id, width, height
                        )
                        # Verify winocr extracted coherent financial lines
                        if self._has_meaningful_financial_content_lines(winocr_lines):
                            lines = winocr_lines
                            engine_used = "winocr"
            except Exception as e:
                logger.debug("Local winocr unavailable or failed: %s", e)

        # 2. Production Vision OCR (for Linux/Vercel or Windows fallback when winocr is missing/scrambled)
        if not lines:
            try:
                send_bytes = file_bytes
                if img is not None:
                    if img.mode != "RGB":
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        alpha_img = img.convert("RGBA") if img.mode != "RGBA" else img
                        bg.paste(alpha_img, mask=alpha_img.split()[-1])
                        rgb_img = bg
                    else:
                        rgb_img = img

                    # Downscale only if excessively large (> 2400px) to preserve fine digits
                    max_dim = max(rgb_img.size)
                    if max_dim > 2400:
                        scale = 2400.0 / max_dim
                        new_size = (int(rgb_img.width * scale), int(rgb_img.height * scale))
                        rgb_img = rgb_img.resize(new_size, Image.Resampling.LANCZOS)

                    buf = io.BytesIO()
                    rgb_img.save(buf, format="PNG", optimize=True)
                    send_bytes = buf.getvalue()

                vision_pages = await self._vision_ocr_pass(document_id, send_bytes)
                if vision_pages and vision_pages[0].lines:
                    lines = vision_pages[0].lines
                    width = vision_pages[0].width
                    height = vision_pages[0].height
                    engine_used = "gemini_vision_ocr"
            except Exception as e:
                logger.warning("Vision OCR failed: %s", e)

        # 3. Text payload fallback (for UTF-8 text streams or plain text test uploads, NOT binary images)
        is_binary_image = file_bytes.startswith(
            (b"\x89PNG", b"\xff\xd8\xff", b"GIF", b"RIFF", b"%PDF", b"BM")
        )
        if not lines and not is_binary_image:
            decoded_text = ""
            try:
                decoded_text = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                decoded_text = ""

            candidate_lines = [
                ln.strip()
                for ln in decoded_text.splitlines()
                if len(ln.strip()) > 1 and any(c.isalnum() for c in ln)
            ]

            if candidate_lines:
                total_lines = len(candidate_lines)
                line_height_norm = min(0.04, 0.80 / max(total_lines, 1))

                for idx, line_text in enumerate(candidate_lines[:40], start=1):
                    y_pos = min(0.92, 0.05 + (idx - 1) * (line_height_norm * 1.15))
                    box = BoundingBox(
                        x=0.08,
                        y=y_pos,
                        width=0.84,
                        height=line_height_norm,
                        coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                    )
                    lines.append(
                        OcrLine(
                            line_id=uuid4(),
                            page_id=page_id,
                            document_id=document_id,
                            line_number=idx,
                            text=line_text,
                            raw_text=line_text,
                            bounding_box=box,
                            confidence=0.95,
                        )
                    )
                if lines:
                    engine_used = "text_stream_ocr"

        page_result = [
            OcrPage(
                page_id=page_id,
                document_id=document_id,
                page_number=1,
                width=width,
                height=height,
                dpi=300,
                lines=lines,
            )
        ]
        return page_result, engine_used
