"""End-to-end pipeline orchestrator for document analysis."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

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
)
from before_you_pay.services.llm_extraction import HybridLlmExtractionEngine
from before_you_pay.services.ocr import SpatialOcrEngine
from before_you_pay.services.ocr_quality import OCRQualityEvaluator
from before_you_pay.services.okf import OkfCatalogService
from before_you_pay.services.precondition import PreconditionChecker
from before_you_pay.services.rag import SqliteRagService
from before_you_pay.services.reasoning import SemanticReasoningEngine
from before_you_pay.services.result import ResultAggregatorService
from before_you_pay.services.validation import DeterministicValidationEngine


class PipelineService:
    """Orchestrates the 7-stage decision support workflow with clean service separation."""

    def __init__(
        self,
        ocr_engine: SpatialOcrEngine | None = None,
        extraction_engine: HybridLlmExtractionEngine | None = None,
        rag_service: SqliteRagService | None = None,
        okf_service: OkfCatalogService | None = None,
        validation_engine: DeterministicValidationEngine | None = None,
        reasoning_engine: SemanticReasoningEngine | None = None,
        result_service: ResultAggregatorService | None = None,
    ) -> None:
        self.precondition = PreconditionChecker()
        self.ocr_engine = ocr_engine or SpatialOcrEngine()
        self.ocr_quality_evaluator = OCRQualityEvaluator()
        self.extraction_engine = extraction_engine or HybridLlmExtractionEngine()
        self.rag_service = rag_service or SqliteRagService()
        self.okf_service = okf_service or OkfCatalogService()
        self.validation_engine = validation_engine or DeterministicValidationEngine()
        self.reasoning_engine = reasoning_engine or SemanticReasoningEngine()
        self.result_service = result_service or ResultAggregatorService()

    async def run_full_pipeline(
        self,
        document_id: UUID,
        user_id: UUID,
        file_bytes: bytes,
        mime_type: str,
        document_type_hint: DocumentClassification = DocumentClassification.OTHER,
    ) -> FinalDecisionSupportResult:
        """Execute all 7 stages sequentially without storing unbounded state in RAM."""
        # 1. Precondition check (glare, blur, size, MIME)
        self.precondition.validate_file(file_bytes, mime_type, user_id)

        # 2. Spatial OCR with Multi-Pass Recovery
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

        # 3. Structured Extraction (Gemini Failover Pool with Regex Fallback)
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
                first_line = all_lines[0] if all_lines else None
                first_line_id = first_line.line_id if first_line else uuid4()
                first_text = first_line.text if first_line else "Non-financial"
                zero_prov = FieldProvenance(
                    document_id=document_id,
                    page_id=p_id,
                    ocr_line_ids=[first_line_id],
                    raw_text=first_text,
                )
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
                            input_field_ids=[extracted_doc.total_amount.field_id],
                            severity=ValidationSeverity.INFO,
                            message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
                        )
                    ],
                    raw_ocr_lines=[ln.text for ln in all_lines],
                    ocr_lines=all_lines,
                    ocr_quality=ocr_quality,
                    analysis_state=AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR,
                )
            raise

        # 4. User Document RAG Retrieval (SQLite, isolated by user_id)
        keywords = []
        if extracted_doc.vendor_name:
            keywords.append(str(extracted_doc.vendor_name.normalized_value))
        keywords.extend(
            [str(item.description.normalized_value) for item in extracted_doc.line_items[:3]]
        )
        query_text = " ".join(keywords) or "financial commitment warranty agreement"

        rag_query = RagQuery(
            user_id=user_id,
            current_document_id=document_id,
            query_text=query_text,
            top_k=5,
            min_similarity=0.30,
        )
        rag_evidence = await self.rag_service.retrieve(rag_query)

        # 5. OKF Catalog Retrieval (Curated JSON rules)
        okf_query = OkfQuery(
            document_type=extracted_doc.document_type,
            concept_keywords=["renewal", "fee", "warranty", "penalty", "tax"],
        )
        okf_evidence = await self.okf_service.query_rules(okf_query)

        # 6. Semantic Reasoning
        reasoning_claims = await self.reasoning_engine.generate_claims(
            document=extracted_doc,
            rag_evidence=rag_evidence,
            okf_evidence=okf_evidence,
        )

        # 7. Deterministic Validation (sole arithmetic authority)
        validation_checks = self.validation_engine.validate(extracted_doc)

        all_lines = [line for p in ocr_result.pages for line in p.lines]
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
        )

    async def run_streaming_pipeline(
        self,
        document_id: UUID,
        user_id: UUID,
        file_bytes: bytes,
        mime_type: str,
        document_type_hint: DocumentClassification = DocumentClassification.OTHER,
    ) -> AsyncGenerator[dict, None]:
        """Execute 7-stage pipeline yielding real-time progressive SSE updates."""
        # Stage 1: Precondition check
        yield {
            "stage": "precondition",
            "status": "in_progress",
            "message": "Validating file integrity, MIME format, and size bounds...",
            "progress": 10,
        }
        self.precondition.validate_file(file_bytes, mime_type, user_id)
        yield {
            "stage": "precondition",
            "status": "completed",
            "message": "Preconditions passed successfully.",
            "progress": 20,
        }

        # Stage 2: Spatial OCR with Multi-Pass Recovery
        yield {
            "stage": "spatial_ocr",
            "status": "in_progress",
            "message": "Extracting text layers and spatial bounding boxes...",
            "progress": 30,
        }
        ocr_result = await self.ocr_engine.process_document(document_id, file_bytes, mime_type)
        line_count = sum(len(p.lines) for p in ocr_result.pages)
        ocr_quality = ocr_result.quality or self.ocr_quality_evaluator.evaluate(ocr_result)

        recovery_info = (
            f" (Recovered in pass {ocr_result.recovery_pass})"
            if ocr_result.recovery_attempted and ocr_result.recovery_pass > 1
            else ""
        )
        yield {
            "stage": "spatial_ocr",
            "status": "completed",
            "message": f"Recognized {line_count} text lines across {len(ocr_result.pages)} page(s){recovery_info}. Quality: {ocr_quality.status.value}.",
            "progress": 45,
            "data": {
                "line_count": line_count,
                "page_count": len(ocr_result.pages),
                "quality_status": ocr_quality.status.value,
                "quality_score": ocr_quality.score,
                "recovery_attempted": ocr_result.recovery_attempted,
                "recovery_pass": ocr_result.recovery_pass,
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
                "stage": "complete",
                "status": "completed",
                "message": "Document contains no readable text. Financial extraction skipped.",
                "progress": 100,
                "result": final_res.model_dump(mode="json"),
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
                "stage": "complete",
                "status": "completed",
                "message": "OCR quality unreliable. Financial extraction bypassed to prevent false conclusions.",
                "progress": 100,
                "result": final_res.model_dump(mode="json"),
            }
            return

        # Stage 3: Structured Extraction (Gemini Failover Pool)
        yield {
            "stage": "structured_extraction",
            "status": "in_progress",
            "message": "Extracting vendor, line items, and terms via AI inference...",
            "progress": 55,
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
                extracted_doc, extraction_provider = extraction_res, "UNKNOWN"
        except ContractViolationException as cve:
            if "No total amount or itemized financial figures" in str(cve):
                all_lines = [line for p in ocr_result.pages for line in p.lines]
                p_id = ocr_result.pages[0].page_id if ocr_result.pages else uuid4()
                first_line = all_lines[0] if all_lines else None
                first_line_id = first_line.line_id if first_line else uuid4()
                first_text = first_line.text if first_line else "Non-financial"
                zero_prov = FieldProvenance(
                    document_id=document_id,
                    page_id=p_id,
                    ocr_line_ids=[first_line_id],
                    raw_text=first_text,
                )
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
                final_res = self.result_service.compile_result(
                    document_id=document_id,
                    user_id=user_id,
                    document=extracted_doc,
                    reasoning_claims=[],
                    validation_checks=[
                        ValidationCheck(
                            validation_id=uuid4(),
                            check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                            status=ValidationStatus.PASS,
                            input_field_ids=[extracted_doc.total_amount.field_id],
                            severity=ValidationSeverity.INFO,
                            message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
                        )
                    ],
                    raw_ocr_lines=[ln.text for ln in all_lines],
                    ocr_lines=all_lines,
                    ocr_quality=ocr_quality,
                    analysis_state=AnalysisState.NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR,
                )
                yield {
                    "stage": "complete",
                    "status": "completed",
                    "message": "Document reliably analyzed. No financial obligations detected.",
                    "progress": 100,
                    "result": final_res.model_dump(mode="json"),
                }
                return
            raise

        yield {
            "stage": "structured_extraction",
            "status": "completed",
            "message": f"Entities extracted successfully via {extraction_provider}.",
            "progress": 65,
            "data": {
                "provider": extraction_provider,
                "vendor": extracted_doc.vendor_name.normalized_value
                if extracted_doc.vendor_name
                else "Unknown",
                "item_count": len(extracted_doc.line_items),
                "total": float(extracted_doc.total_amount.normalized_value),
            },
        }

        # Stage 4: Historical RAG & OKF Rules
        yield {
            "stage": "knowledge_retrieval",
            "status": "in_progress",
            "message": "Cross-referencing tenant history (SQLite RAG) and curated OKF rules...",
            "progress": 70,
        }
        keywords = []
        if extracted_doc.vendor_name:
            keywords.append(str(extracted_doc.vendor_name.normalized_value))
        keywords.extend(
            [str(item.description.normalized_value) for item in extracted_doc.line_items[:3]]
        )
        query_text = " ".join(keywords) or "financial commitment warranty agreement"

        rag_evidence = await self.rag_service.retrieve(
            RagQuery(
                user_id=user_id,
                current_document_id=document_id,
                query_text=query_text,
                top_k=5,
                min_similarity=0.30,
            )
        )
        okf_evidence = await self.okf_service.query_rules(
            OkfQuery(
                document_type=extracted_doc.document_type,
                concept_keywords=["renewal", "fee", "warranty", "penalty", "tax"],
            )
        )
        yield {
            "stage": "knowledge_retrieval",
            "status": "completed",
            "message": f"Retrieved {len(rag_evidence)} prior records and {len(okf_evidence)} compliance rules.",
            "progress": 80,
            "data": {"rag_count": len(rag_evidence), "okf_count": len(okf_evidence)},
        }

        # Stage 5: Deterministic Arithmetic Verification Gate
        yield {
            "stage": "arithmetic_gate",
            "status": "in_progress",
            "message": "Executing deterministic Python mathematical gate (line items, tax, total)...",
            "progress": 85,
        }
        validation_checks = self.validation_engine.validate(extracted_doc)
        failed_checks = [c for c in validation_checks if c.status.value == "failed"]
        yield {
            "stage": "arithmetic_gate",
            "status": "completed",
            "message": f"Arithmetic validation completed. Discrepancies detected: {len(failed_checks)}.",
            "progress": 90,
            "data": {
                "checks_count": len(validation_checks),
                "failed_count": len(failed_checks),
            },
        }

        # Stage 6: Semantic Reasoning Synthesis
        yield {
            "stage": "semantic_reasoning",
            "status": "in_progress",
            "message": "Synthesizing grounded decision-support claims and audit flags...",
            "progress": 93,
        }
        reasoning_claims = await self.reasoning_engine.generate_claims(
            document=extracted_doc,
            rag_evidence=rag_evidence,
            okf_evidence=okf_evidence,
        )
        yield {
            "stage": "semantic_reasoning",
            "status": "completed",
            "message": f"Generated {len(reasoning_claims)} evidence-grounded claims.",
            "progress": 96,
            "data": {"claims_count": len(reasoning_claims)},
        }

        # Stage 7: Final Result Compilation
        yield {
            "stage": "final_verdict",
            "status": "in_progress",
            "message": "Compiling final decision-support verdict with spatial bounding boxes...",
            "progress": 98,
        }
        all_lines = [line for p in ocr_result.pages for line in p.lines]
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
        )
        yield {
            "stage": "complete",
            "status": "completed",
            "message": "Audit analysis complete.",
            "progress": 100,
            "result": final_result.model_dump(mode="json"),
        }
