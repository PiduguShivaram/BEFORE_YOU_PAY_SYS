"""Result compilation service producing evidence-backed decision payloads with visual bounding boxes."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from before_you_pay.models import (
    AnalysisState,
    BoundingBox,
    ClaimType,
    DecisionFlag,
    DecisionStatus,
    DocumentClassification,
    ExtractedField,
    FinalDecisionSupportResult,
    OcrLine,
    OCRQualityResult,
    ReasoningClaim,
    ResultSummary,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)


class ResultAggregatorService:
    """Aggregates reasoning claims, deterministic math checks, and spatial bounding boxes for mobile UI."""

    def compile_result(
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
    ) -> FinalDecisionSupportResult:
        """Construct FinalDecisionSupportResult with tap-to-source bounding boxes."""
        # Index all extracted fields for fast bounding-box lookup
        field_map: dict[UUID, ExtractedField] = {}
        if document.total_amount:
            field_map[document.total_amount.field_id] = document.total_amount
        if document.subtotal:
            field_map[document.subtotal.field_id] = document.subtotal
        if document.tax_amount:
            field_map[document.tax_amount.field_id] = document.tax_amount
        if document.shipping_amount:
            field_map[document.shipping_amount.field_id] = document.shipping_amount
        if document.discount_amount:
            field_map[document.discount_amount.field_id] = document.discount_amount
        if document.amount_paid:
            field_map[document.amount_paid.field_id] = document.amount_paid
        if document.balance_due:
            field_map[document.balance_due.field_id] = document.balance_due
        if document.vendor_name:
            field_map[document.vendor_name.field_id] = document.vendor_name
        for item in document.line_items:
            field_map[item.description.field_id] = item.description
            field_map[item.total_price.field_id] = item.total_price
            if item.unit_price:
                field_map[item.unit_price.field_id] = item.unit_price
            if item.mrp:
                field_map[item.mrp.field_id] = item.mrp
            if item.discount:
                field_map[item.discount.field_id] = item.discount
        for fee in document.fees:
            field_map[fee.field_id] = fee
        for clause in document.clauses_and_notes:
            field_map[clause.field_id] = clause
        for comp in document.cost_breakdown:
            if hasattr(comp, "amount") and comp.amount:
                field_map[comp.amount.field_id] = comp.amount

        flags: list[DecisionFlag] = []

        # 1. Convert failed deterministic validation checks to prominent flags
        for check in validation_checks:
            if check.status == ValidationStatus.FAIL:
                box_list = self._lookup_boxes(check.input_field_ids, field_map)
                claim_type = (
                    ClaimType.ADDITIONAL_CHARGE_DETECTED
                    if "SUM" in check.check_code or "TOTAL" in check.check_code
                    else ClaimType.REQUIRES_VERIFICATION
                )
                flags.append(
                    DecisionFlag(
                        flag_id=uuid4(),
                        claim_type=claim_type,
                        label=self._format_check_label(check.check_code),
                        message=check.message,
                        severity=check.severity,
                        associated_validation_id=check.validation_id,
                        field_ids=check.input_field_ids,
                        bounding_boxes=box_list,
                    )
                )

        # 2. Convert reasoning claims to flags
        for claim in reasoning_claims:
            box_list = self._lookup_boxes(claim.field_references, field_map)
            severity = getattr(claim, "severity", ValidationSeverity.WARNING)
            flags.append(
                DecisionFlag(
                    flag_id=uuid4(),
                    claim_type=claim.type,
                    label=claim.title,
                    message=claim.description,
                    severity=severity,
                    associated_claim_id=claim.claim_id,
                    field_ids=claim.field_references,
                    bounding_boxes=box_list,
                )
            )

        # 3. Determine overall status and headline
        overall_status = DecisionStatus.CLEAR
        headline = "All verified: Stated totals and contract terms align with expectations."

        has_critical_failure = any(f.severity == ValidationSeverity.CRITICAL for f in flags)
        has_warning = any(f.severity == ValidationSeverity.WARNING for f in flags)
        has_no_financial_check = any(
            c.check_code in ("NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR", "NO_FINANCIAL_DATA_DETECTED")
            for c in validation_checks
        )

        total_val = float(document.total_amount.normalized_value) if document.total_amount else 0.0
        has_monetary_content = (
            total_val > 0.0 or len(document.line_items) > 0 or len(document.fees) > 0 or len(document.cost_breakdown) > 0
        )

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
            if document.document_type in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN) or document.cost_breakdown:
                headline = "Quotation verified: All charges and applied offers mathematically reconcile."
            else:
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
        """Compile safe, evidence-grounded result when OCR is corrupted or document is unreadable."""
        is_empty = (
            analysis_state == AnalysisState.DOCUMENT_UNREADABLE or ocr_quality.line_count == 0
        )

        headline = (
            "Document could not be read" if is_empty else "Document could not be reliably read"
        )
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

        all_lines = [ln for p in ocr_result.pages for ln in p.lines]
        raw_lines = [ln.text for ln in all_lines]

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
        )

    def _lookup_boxes(
        self,
        field_ids: list[UUID],
        field_map: dict[UUID, ExtractedField],
    ) -> list[BoundingBox]:
        """Collect all visual bounding boxes from referenced fields."""
        boxes: list[BoundingBox] = []
        for fid in field_ids:
            field = field_map.get(fid)
            if field and field.provenance and field.provenance.bounding_box:
                boxes.append(field.provenance.bounding_box)
        return boxes

    def _format_check_label(self, check_code: str) -> str:
        """Format check code into human-readable mobile UI badge label."""
        if "NO_FINANCIAL_DATA" in check_code or "FINANCIAL_CONTENT" in check_code:
            return "No Financial Data Detected"
        if "EXTENSION" in check_code:
            return "Line Item Arithmetic Discrepancy"
        if "SUM" in check_code:
            return "Line Item Arithmetic Discrepancy"
        if "TOTAL" in check_code:
            return "Grand Total Mismatch"
        if "TAX" in check_code:
            return "Tax Calculation Attention"
        if "DATE" in check_code:
            return "Date Sequence Discrepancy"
        if "PAYMENT" in check_code:
            return "Payment Status Discrepancy"
        return "Validation Check"
