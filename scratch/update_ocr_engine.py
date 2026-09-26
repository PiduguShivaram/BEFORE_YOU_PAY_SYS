# Updates to src/before_you_pay/services/ocr.py
with open("src/before_you_pay/services/ocr.py", encoding="utf-8") as f:
    ocr_code = f.read()

# 1. Update imports
target_imports = """import pypdf
from PIL import Image"""

replacement_imports = """import pypdf
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from before_you_pay.models.analysis import OCRQualityResult, OCRQualityStatus
from before_you_pay.services.ocr_quality import OCRQualityEvaluator"""

assert target_imports in ocr_code, "target_imports not found"
ocr_code = ocr_code.replace(target_imports, replacement_imports)

# 2. Update __init__
target_init = """    def __init__(self, engine_name: str = "spatial_layout_ocr", version: str = "1.0.0") -> None:
        self.engine_name = engine_name
        self.version = version"""

replacement_init = """    def __init__(self, engine_name: str = "spatial_layout_ocr", version: str = "1.0.0") -> None:
        self.engine_name = engine_name
        self.version = version
        self.quality_evaluator = OCRQualityEvaluator()"""

assert target_init in ocr_code, "target_init not found"
ocr_code = ocr_code.replace(target_init, replacement_init)

# 3. Update process_document to run multi-pass recovery & quality gate
target_process = """    async def process_document(
        self,
        document_id: UUID,
        file_bytes: bytes,
        mime_type: str,
    ) -> OcrResult:
        \"\"\"Process document bytes and return structured OcrResult.\"\"\"
        normalized_mime = mime_type.lower().split(";")[0].strip()

        if normalized_mime == "application/pdf":
            pages = await self._process_pdf(document_id, file_bytes)
        else:
            pages = await self._process_image(document_id, file_bytes)

        return OcrResult(
            document_id=document_id,
            pages=pages,
            engine_name=self.engine_name,
            engine_version=self.version,
            processed_at=datetime.now(UTC),
        )"""

replacement_process = """    async def process_document(
        self,
        document_id: UUID,
        file_bytes: bytes,
        mime_type: str,
    ) -> OcrResult:
        \"\"\"Process document bytes with multi-pass OCR and deterministic quality gate.\"\"\"
        normalized_mime = mime_type.lower().split(";")[0].strip()

        if normalized_mime == "application/pdf":
            pages = await self._process_pdf(document_id, file_bytes)
        else:
            pages = await self._process_image(document_id, file_bytes)

        initial_result = OcrResult(
            document_id=document_id,
            pages=pages,
            engine_name=self.engine_name,
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

        # Trigger Multi-Pass Recovery for images if quality is degraded or unreliable
        if quality.status != OCRQualityStatus.GOOD and normalized_mime != "application/pdf":
            recovered = await self._attempt_recovery_passes(document_id, file_bytes, initial_result, quality)
            return recovered

        return initial_result

    async def _attempt_recovery_passes(
        self,
        document_id: UUID,
        file_bytes: bytes,
        initial_result: OcrResult,
        initial_quality: OCRQualityResult,
    ) -> OcrResult:
        \"\"\"Execute controlled Pass 2 (contrast/upscaling/sharpening) and Pass 3 (adaptive thresholding).\"\"\"
        try:
            base_img = Image.open(io.BytesIO(file_bytes))
        except Exception:
            return initial_result

        best_result = initial_result
        best_quality = initial_quality

        # --- PASS 2: Preprocessed Image (Upscale, Grayscale, Contrast Normalization, Sharpening) ---
        try:
            img_p2 = self._preprocess_pass2(base_img)
            p2_pages = await self._run_winocr_on_pil(document_id, img_p2)
            if p2_pages and p2_pages[0].lines:
                res_p2 = OcrResult(
                    document_id=document_id,
                    pages=p2_pages,
                    engine_name=self.engine_name,
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
                if q2.status == OCRQualityStatus.GOOD:
                    return best_result
        except Exception:
            pass

        # --- PASS 3: Adaptive Binarization / Thresholding ---
        try:
            img_p3 = self._preprocess_pass3(base_img)
            p3_pages = await self._run_winocr_on_pil(document_id, img_p3)
            if p3_pages and p3_pages[0].lines:
                res_p3 = OcrResult(
                    document_id=document_id,
                    pages=p3_pages,
                    engine_name=self.engine_name,
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

        return best_result

    def _preprocess_pass2(self, img: Image.Image) -> Image.Image:
        \"\"\"Pass 2: Upscale small scans, convert grayscale, normalize contrast, sharpen edges.\"\"\"
        w, h = img.size
        processed = img.copy()

        # Preserve spatial geometry while increasing resolution if small
        if w < 1600 or h < 1600:
            scale = min(2.0, max(1.5, 1800.0 / max(w, h)))
            new_w, new_h = int(w * scale), int(h * scale)
            processed = processed.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Grayscale
        if processed.mode not in ("L", "1"):
            processed = processed.convert("L")

        # Contrast normalization
        processed = ImageOps.autocontrast(processed, cutoff=2)

        # Unsharp mask filter
        processed = processed.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=3))
        return processed.convert("RGB")

    def _preprocess_pass3(self, img: Image.Image) -> Image.Image:
        \"\"\"Pass 3: Otsu global threshold binarization.\"\"\"
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
        \"\"\"Helper to run winocr on an in-memory PIL image and cluster lines.\"\"\"
        import winocr
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
        ]"""

assert target_process in ocr_code, "target_process not found"
ocr_code = ocr_code.replace(target_process, replacement_process)

# 4. Make sure OcrLine constructor sets raw_text=text
ocr_code = ocr_code.replace(
    """                    text=text,
                    bounding_box=box,""",
    """                    text=text,
                    raw_text=text,
                    bounding_box=box,""",
)

ocr_code = ocr_code.replace(
    """                            text=line_text,
                            bounding_box=box,""",
    """                            text=line_text,
                            raw_text=line_text,
                            bounding_box=box,""",
)

# 5. In _process_image: instead of raising ContractViolationException on empty lines, return an empty page if nothing recognized
target_rejection = """        if not lines:
            raise ContractViolationException(
                "No readable text lines found in document. Please upload a clear photo, scanned document, or searchable PDF.",
                details={"document_id": str(document_id)},
            )

        avg_confidence = sum(line.confidence for line in lines) / len(lines)
        if avg_confidence < 0.40 or all(len(line.text.strip()) < 2 for line in lines):
            raise ContractViolationException(
                "Document text could not be reliably recognized (confidence too low). Please upload a clearer scan or photo.",
                details={"document_id": str(document_id), "average_confidence": round(avg_confidence, 2)},
            )"""

replacement_rejection = """        if not lines:
            # Return empty page so pipeline Quality Gate can cleanly classify as DOCUMENT_UNREADABLE
            return [
                OcrPage(
                    page_id=page_id,
                    document_id=document_id,
                    page_number=1,
                    width=width,
                    height=height,
                    dpi=300,
                    lines=[],
                )
            ]"""

assert target_rejection in ocr_code, "target_rejection not found"
ocr_code = ocr_code.replace(target_rejection, replacement_rejection)

with open("src/before_you_pay/services/ocr.py", "w", encoding="utf-8") as f:
    f.write(ocr_code)
print("Updated services/ocr.py successfully")
