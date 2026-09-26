# 1. Update src/before_you_pay/services/validation.py
with open("src/before_you_pay/services/validation.py", encoding="utf-8") as f:
    val_code = f.read()

target_financial_check = """            return ValidationCheck(
                validation_id=uuid4(),
                check_code="NO_FINANCIAL_DATA_DETECTED",
                status=ValidationStatus.FAIL,
                input_field_ids=input_ids,
                expected_value="Identifiable financial commitments or line items",
                calculated_value="0.00",
                absolute_delta=0.0,
                severity=ValidationSeverity.CRITICAL,
                message="No financial amounts, itemized line items, or monetary commitments could be identified. The uploaded document does not appear to be a valid invoice, bill, quotation, or financial contract.",
            )"""

replacement_financial_check = """            return ValidationCheck(
                validation_id=uuid4(),
                check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                status=ValidationStatus.FAIL,
                input_field_ids=input_ids,
                expected_value="Identifiable financial commitments or line items",
                calculated_value="0.00",
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
            )"""

assert target_financial_check in val_code, "target_financial_check not found in validation.py"
val_code = val_code.replace(target_financial_check, replacement_financial_check)

with open("src/before_you_pay/services/validation.py", "w", encoding="utf-8") as f:
    f.write(val_code)
print("Updated services/validation.py successfully")

# 2. Update src/before_you_pay/services/result.py
with open("src/before_you_pay/services/result.py", encoding="utf-8") as f:
    res_code = f.read()

# Add imports to result.py
target_imports = """from before_you_pay.models import (
    BoundingBox,
    ClaimType,
    DecisionFlag,
    DecisionStatus,
    ExtractedField,
    FinalDecisionSupportResult,
    ReasoningClaim,
    ResultSummary,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)"""

replacement_imports = """from before_you_pay.models import (
    AnalysisState,
    BoundingBox,
    ClaimType,
    DecisionFlag,
    DecisionStatus,
    ExtractedField,
    FinalDecisionSupportResult,
    OCRQualityResult,
    OcrLine,
    ReasoningClaim,
    ResultSummary,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)"""

assert target_imports in res_code, "target_imports not found in result.py"
res_code = res_code.replace(target_imports, replacement_imports)

# Replace compile_result method
target_compile = """    def compile_result(
        self,
        document_id: UUID,
        user_id: UUID,
        document: StructuredFinancialDocument,
        reasoning_claims: list[ReasoningClaim],
        validation_checks: list[ValidationCheck],
        raw_ocr_lines: list[str] | None = None,
    ) -> FinalDecisionSupportResult:"""

replacement_compile = """    def compile_result(
        self,
        document_id: UUID,
        user_id: UUID,
        document: StructuredFinancialDocument,
        reasoning_claims: list[ReasoningClaim],
        validation_checks: list[ValidationCheck],
        raw_ocr_lines: list[str] | None = None,
        ocr_lines: list[OcrLine] | None = None,
        ocr_quality: OCRQualityResult | None = None,
        analysis_state: AnalysisState | None = None,
    ) -> FinalDecisionSupportResult:"""

assert target_compile in res_code, "target_compile not found in result.py"
res_code = res_code.replace(target_compile, replacement_compile)

# Update headline and status determination in compile_result
target_status_logic = """        has_critical_failure = any(f.severity == ValidationSeverity.CRITICAL for f in flags)
        has_warning = any(f.severity == ValidationSeverity.WARNING for f in flags)
        has_no_financial_flag = any("No Financial Data" in f.label for f in flags)

        if has_no_financial_flag:
            overall_status = DecisionStatus.CRITICAL_WARNING
            headline = "Action Recommended: No valid financial transactions or line items detected in document."
        elif has_critical_failure:
            overall_status = DecisionStatus.CRITICAL_WARNING
            headline = f"Action Recommended: {len(flags)} discrepancies detected before proceeding with payment."
        elif has_warning:
            overall_status = DecisionStatus.REQUIRES_ATTENTION
            headline = f"Review Recommended: {len(flags)} item{'s' if len(flags) > 1 else ''} require{'s' if len(flags) == 1 else ''} attention or verification."
        else:
            total_val = float(document.total_amount.normalized_value) if document.total_amount else 0.0
            if total_val <= 0.0 and not document.line_items and not document.clauses_and_notes:
                overall_status = DecisionStatus.REQUIRES_ATTENTION
                headline = "Review Recommended: Document contains no verified financial commitments."
            else:
                overall_status = DecisionStatus.CLEAR
                headline = "All verified: Stated totals and contract terms align with expectations."

        summary = ResultSummary(
            headline=headline,
            overall_status=overall_status,
            total_flags=len(flags),
            requires_human_verification=len(flags) > 0,
        )

        return FinalDecisionSupportResult(
            result_id=uuid4(),
            document_id=document_id,
            user_id=user_id,
            summary=summary,
            flags=flags,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            document=document,
            raw_ocr_lines=raw_ocr_lines or [],
            generated_at=datetime.now(UTC),
        )"""

replacement_status_logic = """        has_critical_failure = any(f.severity == ValidationSeverity.CRITICAL for f in flags)
        has_warning = any(f.severity == ValidationSeverity.WARNING for f in flags)
        has_no_financial_check = any(
            c.check_code in ("NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR", "NO_FINANCIAL_DATA_DETECTED")
            for c in validation_checks
        )

        total_val = float(document.total_amount.normalized_value) if document.total_amount else 0.0
        has_monetary_content = total_val > 0.0 or len(document.line_items) > 0 or len(document.fees) > 0

        if analysis_state is None:
            if not has_monetary_content or has_no_financial_check:
                analysis_state = AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR
            else:
                analysis_state = AnalysisState.FINANCIAL_DATA_FOUND

        if analysis_state == AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR:
            overall_status = DecisionStatus.REQUIRES_ATTENTION
            headline = "No Financial Data Detected: Document contains no payable obligations."
        elif has_critical_failure:
            overall_status = DecisionStatus.CRITICAL_WARNING
            headline = f"Action Recommended: {len(flags)} discrepancies detected before proceeding with payment."
        elif has_warning:
            overall_status = DecisionStatus.REQUIRES_ATTENTION
            headline = f"Review Recommended: {len(flags)} item{'s' if len(flags) > 1 else ''} require{'s' if len(flags) == 1 else ''} attention or verification."
        else:
            overall_status = DecisionStatus.CLEAR
            headline = "All verified: Stated totals and contract terms align with expectations."

        summary = ResultSummary(
            headline=headline,
            overall_status=overall_status,
            total_flags=len(flags),
            requires_human_verification=len(flags) > 0,
            analysis_state=analysis_state,
            ocr_quality=ocr_quality,
        )

        return FinalDecisionSupportResult(
            result_id=uuid4(),
            document_id=document_id,
            user_id=user_id,
            summary=summary,
            flags=flags,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            document=document,
            raw_ocr_lines=raw_ocr_lines or [],
            ocr_lines=ocr_lines or [],
            analysis_state=analysis_state,
            ocr_quality=ocr_quality,
            generated_at=datetime.now(UTC),
        )

    def compile_unreliable_result(
        self,
        document_id: UUID,
        user_id: UUID,
        ocr_result: Any,
        ocr_quality: OCRQualityResult,
        analysis_state: AnalysisState = AnalysisState.OCR_UNRELIABLE,
    ) -> FinalDecisionSupportResult:
        \"\"\"Compile safe, evidence-grounded result when OCR is corrupted or document is unreadable.\"\"\"
        is_empty = analysis_state == AnalysisState.DOCUMENT_UNREADABLE or ocr_quality.line_count == 0

        headline = "Document could not be read" if is_empty else "Document could not be reliably read"
        message = (
            "No readable text lines were found in the document. Please upload a clear photo or searchable PDF."
            if is_empty
            else "Some text extracted from this document appears corrupted or unreadable, so financial analysis was not performed. Try uploading a clearer image or higher-resolution PDF."
        )

        flags = [
            DecisionFlag(
                flag_id=uuid4(),
                claim_type=ClaimType.REQUIRES_VERIFICATION,
                label="Document Unreadable" if is_empty else "OCR Unreliable",
                message=message,
                severity=ValidationSeverity.WARNING,
                field_ids=[],
                bounding_boxes=[],
            )
        ]

        summary = ResultSummary(
            headline=headline,
            overall_status=DecisionStatus.REQUIRES_ATTENTION,
            total_flags=1,
            requires_human_verification=True,
            analysis_state=analysis_state,
            ocr_quality=ocr_quality,
        )

        all_lines = [l for p in ocr_result.pages for l in p.lines]
        raw_lines = [l.text for l in all_lines]

        return FinalDecisionSupportResult(
            result_id=uuid4(),
            document_id=document_id,
            user_id=user_id,
            summary=summary,
            flags=flags,
            reasoning_claims=[],
            validation_checks=[],
            document=None,
            raw_ocr_lines=raw_lines,
            ocr_lines=all_lines,
            analysis_state=analysis_state,
            ocr_quality=ocr_quality,
            generated_at=datetime.now(UTC),
        )"""

assert target_status_logic in res_code, "target_status_logic not found in result.py"
res_code = res_code.replace(target_status_logic, replacement_status_logic)

with open("src/before_you_pay/services/result.py", "w", encoding="utf-8") as f:
    f.write(res_code)
print("Updated services/result.py successfully")

# 3. Update src/before_you_pay/services/pipeline.py
with open("src/before_you_pay/services/pipeline.py", encoding="utf-8") as f:
    pipe_code = f.read()

# Update imports
pipe_target_imports = """from before_you_pay.models import (
    DocumentClassification,
    FinalDecisionSupportResult,
    OkfQuery,
    RagQuery,
)"""

pipe_replacement_imports = """from before_you_pay.models import (
    AnalysisState,
    DocumentClassification,
    FinalDecisionSupportResult,
    OCRQualityStatus,
    OkfQuery,
    RagQuery,
)
from before_you_pay.services.ocr_quality import OCRQualityEvaluator"""

assert pipe_target_imports in pipe_code, "pipe_target_imports not found"
pipe_code = pipe_code.replace(pipe_target_imports, pipe_replacement_imports)

# In PipelineService.__init__, add ocr_quality_evaluator
target_pipe_init = """        self.precondition = PreconditionChecker()
        self.ocr_engine = ocr_engine or SpatialOcrEngine()"""

replacement_pipe_init = """        self.precondition = PreconditionChecker()
        self.ocr_engine = ocr_engine or SpatialOcrEngine()
        self.ocr_quality_evaluator = OCRQualityEvaluator()"""

assert target_pipe_init in pipe_code, "target_pipe_init not found"
pipe_code = pipe_code.replace(target_pipe_init, replacement_pipe_init)

# In run_full_pipeline, add quality gate check
target_run_full = """        # 2. Spatial OCR
        ocr_result = await self.ocr_engine.process_document(document_id, file_bytes, mime_type)

        # 3. Structured Extraction (Gemini Failover Pool with Regex Fallback)"""

replacement_run_full = """        # 2. Spatial OCR with Multi-Pass Recovery
        ocr_result = await self.ocr_engine.process_document(document_id, file_bytes, mime_type)
        ocr_quality = ocr_result.quality or self.ocr_quality_evaluator.evaluate(ocr_result)

        # 2b. Deterministic OCR Quality Gate
        if ocr_quality.line_count == 0 or ocr_quality.character_count == 0:
            return self.result_service.compile_unreliable_result(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                ocr_quality=ocr_quality,
                analysis_state=AnalysisState.DOCUMENT_UNREADABLE,
            )

        if ocr_quality.status == OCRQualityStatus.UNRELIABLE:
            return self.result_service.compile_unreliable_result(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                ocr_quality=ocr_quality,
                analysis_state=AnalysisState.OCR_UNRELIABLE,
            )

        # 3. Structured Extraction (Gemini Failover Pool with Regex Fallback)"""

assert target_run_full in pipe_code, "target_run_full not found"
pipe_code = pipe_code.replace(target_run_full, replacement_run_full)

# In compile_result call in run_full_pipeline
target_pipe_compile = """        raw_ocr_lines = [line.text for p in ocr_result.pages for line in p.lines]

        # 8. Compile Final Result with visual bounding boxes for mobile UI
        return self.result_service.compile_result(
            document_id=document_id,
            user_id=user_id,
            document=extracted_doc,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            raw_ocr_lines=raw_ocr_lines,
        )"""

replacement_pipe_compile = """        all_lines = [line for p in ocr_result.pages for line in p.lines]
        raw_ocr_lines = [line.text for line in all_lines]

        # 8. Compile Final Result with visual bounding boxes for mobile UI
        return self.result_service.compile_result(
            document_id=document_id,
            user_id=user_id,
            document=extracted_doc,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            raw_ocr_lines=raw_ocr_lines,
            ocr_lines=all_lines,
            ocr_quality=ocr_quality,
        )"""

assert target_pipe_compile in pipe_code, "target_pipe_compile not found"
pipe_code = pipe_code.replace(target_pipe_compile, replacement_pipe_compile)

# In run_streaming_pipeline, update Stage 2 to emit OCR quality and early-return if unreliable
target_stream_stage2 = """        # Stage 2: Spatial OCR
        yield {
            \"stage\": \"spatial_ocr\",
            \"status\": \"in_progress\",
            \"message\": \"Extracting text layers and spatial bounding boxes...\",
            \"progress\": 30,
        }
        ocr_result = await self.ocr_engine.process_document(document_id, file_bytes, mime_type)
        line_count = sum(len(p.lines) for p in ocr_result.pages)
        yield {
            \"stage\": \"spatial_ocr\",
            \"status\": \"completed\",
            \"message\": f\"Recognized {line_count} text lines across {len(ocr_result.pages)} page(s).\",
            \"progress\": 45,
            \"data\": {\"line_count\": line_count, \"page_count\": len(ocr_result.pages)},
        }

        # Stage 3: Structured Extraction (Gemini Failover Pool)"""

replacement_stream_stage2 = """        # Stage 2: Spatial OCR with Multi-Pass Recovery
        yield {
            \"stage\": \"spatial_ocr\",
            \"status\": \"in_progress\",
            \"message\": \"Extracting text layers and spatial bounding boxes...\",
            \"progress\": 30,
        }
        ocr_result = await self.ocr_engine.process_document(document_id, file_bytes, mime_type)
        line_count = sum(len(p.lines) for p in ocr_result.pages)
        ocr_quality = ocr_result.quality or self.ocr_quality_evaluator.evaluate(ocr_result)

        recovery_info = (
            f\" (Recovered in pass {ocr_result.recovery_pass})\"
            if ocr_result.recovery_attempted and ocr_result.recovery_pass > 1
            else \"\"
        )
        yield {
            \"stage\": \"spatial_ocr\",
            \"status\": \"completed\",
            \"message\": f\"Recognized {line_count} text lines across {len(ocr_result.pages)} page(s){recovery_info}. Quality: {ocr_quality.status.value}.\",
            \"progress\": 45,
            \"data\": {
                \"line_count\": line_count,
                \"page_count\": len(ocr_result.pages),
                \"quality_status\": ocr_quality.status.value,
                \"quality_score\": ocr_quality.score,
                \"recovery_attempted\": ocr_result.recovery_attempted,
                \"recovery_pass\": ocr_result.recovery_pass,
            },
        }

        # Quality Gate Check: Abort downstream extraction if unreadable or corrupted
        if ocr_quality.line_count == 0 or ocr_quality.character_count == 0:
            final_res = self.result_service.compile_unreliable_result(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                ocr_quality=ocr_quality,
                analysis_state=AnalysisState.DOCUMENT_UNREADABLE,
            )
            yield {
                \"stage\": \"complete\",
                \"status\": \"completed\",
                \"message\": \"Document contains no readable text. Financial extraction skipped.\",
                \"progress\": 100,
                \"result\": final_res.model_dump(mode=\"json\"),
            }
            return

        if ocr_quality.status == OCRQualityStatus.UNRELIABLE:
            final_res = self.result_service.compile_unreliable_result(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                ocr_quality=ocr_quality,
                analysis_state=AnalysisState.OCR_UNRELIABLE,
            )
            yield {
                \"stage\": \"complete\",
                \"status\": \"completed\",
                \"message\": \"OCR quality unreliable. Financial extraction bypassed to prevent false conclusions.\",
                \"progress\": 100,
                \"result\": final_res.model_dump(mode=\"json\"),
            }
            return

        # Stage 3: Structured Extraction (Gemini Failover Pool)"""

assert target_stream_stage2 in pipe_code, "target_stream_stage2 not found"
pipe_code = pipe_code.replace(target_stream_stage2, replacement_stream_stage2)

# Update compile_result in run_streaming_pipeline final stage
target_stream_compile = """        raw_ocr_lines = [line.text for p in ocr_result.pages for line in p.lines]
        final_result = self.result_service.compile_result(
            document_id=document_id,
            user_id=user_id,
            document=extracted_doc,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            raw_ocr_lines=raw_ocr_lines,
        )"""

replacement_stream_compile = """        all_lines = [line for p in ocr_result.pages for line in p.lines]
        raw_ocr_lines = [line.text for line in all_lines]
        final_result = self.result_service.compile_result(
            document_id=document_id,
            user_id=user_id,
            document=extracted_doc,
            reasoning_claims=reasoning_claims,
            validation_checks=validation_checks,
            raw_ocr_lines=raw_ocr_lines,
            ocr_lines=all_lines,
            ocr_quality=ocr_quality,
        )"""

assert target_stream_compile in pipe_code, "target_stream_compile not found"
pipe_code = pipe_code.replace(target_stream_compile, replacement_stream_compile)

with open("src/before_you_pay/services/pipeline.py", "w", encoding="utf-8") as f:
    f.write(pipe_code)
print("Updated services/pipeline.py successfully")
