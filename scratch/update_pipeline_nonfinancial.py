with open("src/before_you_pay/services/pipeline.py", encoding="utf-8") as f:
    code = f.read()

# Make sure FieldProvenance and ExtractedField and StructuredFinancialDocument and ValidationCheck are imported
target_imports = """from before_you_pay.models import (
    AnalysisState,
    DocumentClassification,
    FinalDecisionSupportResult,
    OCRQualityStatus,
    OkfQuery,
    RagQuery,
)"""

replacement_imports = """from uuid import uuid4
from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    AnalysisState,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinalDecisionSupportResult,
    OCRQualityStatus,
    OkfQuery,
    RagQuery,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)"""

assert target_imports in code, "target_imports not found in pipeline.py"
code = code.replace(target_imports, replacement_imports)

# In run_full_pipeline: wrap extraction in try/except for ContractViolationException
target_extraction_block = """        # 3. Structured Extraction (Gemini Failover Pool with Regex Fallback)
        extraction_res = self.extraction_engine.extract(
            document_id=document_id,
            user_id=user_id,
            ocr_result=ocr_result,
            document_type_hint=document_type_hint,
        )
        if isinstance(extraction_res, tuple):
            extracted_doc, _ = extraction_res
        else:
            extracted_doc = extraction_res"""

replacement_extraction_block = """        # 3. Structured Extraction (Gemini Failover Pool with Regex Fallback)
        try:
            extraction_res = self.extraction_engine.extract(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                document_type_hint=document_type_hint,
            )
            if isinstance(extraction_res, tuple):
                extracted_doc, _ = extraction_res
            else:
                extracted_doc = extraction_res
        except ContractViolationException as cve:
            if "No total amount or itemized financial figures" in str(cve):
                # Reliable OCR found no financial data -> transition safely to NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR
                all_lines = [line for p in ocr_result.pages for line in p.lines]
                p_id = ocr_result.pages[0].page_id if ocr_result.pages else uuid4()
                zero_prov = FieldProvenance(document_id=document_id, page_id=p_id, ocr_line_ids=[], raw_text="")
                extracted_doc = StructuredFinancialDocument(
                    document_id=document_id,
                    user_id=user_id,
                    document_type=DocumentClassification.OTHER,
                    total_amount=ExtractedField(
                        field_key="total_amount",
                        normalized_value=0.0,
                        confidence=1.0,
                        provenance=zero_prov,
                    ),
                    line_items=[],
                )
                return self.result_service.compile_result(
                    document_id=document_id,
                    user_id=user_id,
                    document=extracted_doc,
                    reasoning_claims=[],
                    validation_checks=[
                        ValidationCheck(
                            validation_id=uuid4(),
                            check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                            status=ValidationStatus.PASS,
                            severity=ValidationSeverity.INFO,
                            message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
                        )
                    ],
                    raw_ocr_lines=[ln.text for ln in all_lines],
                    ocr_lines=all_lines,
                    ocr_quality=ocr_quality,
                    analysis_state=AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR,
                )
            raise"""

assert target_extraction_block in code, "target_extraction_block not found in pipeline.py"
code = code.replace(target_extraction_block, replacement_extraction_block)

# In run_streaming_pipeline: wrap extraction in try/except for ContractViolationException
target_stream_extraction = """        # Stage 3: Structured Extraction (Gemini Failover Pool)
        yield {
            \"stage\": \"structured_extraction\",
            \"status\": \"in_progress\",
            \"message\": \"Extracting vendor, line items, and terms via AI inference...\",
            \"progress\": 55,
        }
        extraction_res = self.extraction_engine.extract(
            document_id=document_id,
            user_id=user_id,
            ocr_result=ocr_result,
            document_type_hint=document_type_hint,
        )
        if isinstance(extraction_res, tuple):
            extracted_doc, extraction_provider = extraction_res
        else:
            extracted_doc, extraction_provider = extraction_res, \"UNKNOWN\""""

replacement_stream_extraction = """        # Stage 3: Structured Extraction (Gemini Failover Pool)
        yield {
            \"stage\": \"structured_extraction\",
            \"status\": \"in_progress\",
            \"message\": \"Extracting vendor, line items, and terms via AI inference...\",
            \"progress\": 55,
        }
        try:
            extraction_res = self.extraction_engine.extract(
                document_id=document_id,
                user_id=user_id,
                ocr_result=ocr_result,
                document_type_hint=document_type_hint,
            )
            if isinstance(extraction_res, tuple):
                extracted_doc, extraction_provider = extraction_res
            else:
                extracted_doc, extraction_provider = extraction_res, \"UNKNOWN\"
        except ContractViolationException as cve:
            if \"No total amount or itemized financial figures\" in str(cve):
                all_lines = [line for p in ocr_result.pages for line in p.lines]
                p_id = ocr_result.pages[0].page_id if ocr_result.pages else uuid4()
                zero_prov = FieldProvenance(document_id=document_id, page_id=p_id, ocr_line_ids=[], raw_text=\"\")
                extracted_doc = StructuredFinancialDocument(
                    document_id=document_id,
                    user_id=user_id,
                    document_type=DocumentClassification.OTHER,
                    total_amount=ExtractedField(
                        field_key=\"total_amount\",
                        normalized_value=0.0,
                        confidence=1.0,
                        provenance=zero_prov,
                    ),
                    line_items=[],
                )
                final_res = self.result_service.compile_result(
                    document_id=document_id,
                    user_id=user_id,
                    document=extracted_doc,
                    reasoning_claims=[],
                    validation_checks=[
                        ValidationCheck(
                            validation_id=uuid4(),
                            check_code=\"NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR\",
                            status=ValidationStatus.PASS,
                            severity=ValidationSeverity.INFO,
                            message=\"No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.\",
                        )
                    ],
                    raw_ocr_lines=[ln.text for ln in all_lines],
                    ocr_lines=all_lines,
                    ocr_quality=ocr_quality,
                    analysis_state=AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR,
                )
                yield {
                    \"stage\": \"complete\",
                    \"status\": \"completed\",
                    \"message\": \"Document reliably analyzed. No financial obligations detected.\",
                    \"progress\": 100,
                    \"result\": final_res.model_dump(mode=\"json\"),
                }
                return
            raise"""

assert target_stream_extraction in code, "target_stream_extraction not found in pipeline.py"
code = code.replace(target_stream_extraction, replacement_stream_extraction)

with open("src/before_you_pay/services/pipeline.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated pipeline.py successfully")
