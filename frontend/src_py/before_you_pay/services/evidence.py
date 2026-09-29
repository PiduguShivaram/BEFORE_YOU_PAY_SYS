"""Phase 7: Evidence-First Explainability Service.

Builds complete evidence traceability for every finding, explanation,
and question in the Before You Pay decision-support system.

The evidence chain:
DOCUMENT → OCR EVIDENCE → EXTRACTED FIELD → FINANCIAL COMPONENT → SEMANTIC INTERPRETATION → DETERMINISTIC VALIDATION → FINDING → EXPLANATION → QUESTION → ACTION

Design principles:
- Every finding traces to actual document evidence
- Semantic interpretation is never presented as literal document text
- Deterministic calculations are never performed by an LLM
- Amount states are preserved (MISSING, UNKNOWN, UNREADABLE never become ₹0)
- Tenant isolation is maintained throughout
"""

from __future__ import annotations

from uuid import UUID

from before_you_pay.models import (
    AmountState,
    CalculationExplanation,
    ConfidenceLevel,
    ContextualFinding,
    DecisionFlag,
    EvidenceFirstResult,
    EvidenceItem,
    EvidenceType,
    FinancialComponent,
    FindingExplanation,
    QuestionProvenance,
    SmartCostReductionQuestion,
    StructuredFinancialDocument,
    SuggestedMessageItem,
    SupportingDocumentExplanation,
    ValidationCheck,
    ValidationStatus,
)


def _get_confidence_level(confidence: float) -> ConfidenceLevel:
    """Map numeric confidence to confidence level."""
    if confidence >= 0.9:
        return ConfidenceLevel.HIGH
    if confidence >= 0.7:
        return ConfidenceLevel.MEDIUM
    if confidence >= 0.4:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.REQUIRES_VERIFICATION


def _build_evidence_from_component(
    component: FinancialComponent,
    document_id: UUID,
) -> EvidenceItem:
    """Build an evidence item from a financial component."""
    amount_val = None
    if component.amount and component.amount.normalized_value is not None:
        try:
            amount_val = float(component.amount.normalized_value)
        except (TypeError, ValueError):
            pass

    # Determine confidence level based on amount state
    amount_state = component.amount_state
    if amount_state in (AmountState.MISSING, AmountState.UNKNOWN, AmountState.UNREADABLE):
        confidence = 0.5
        confidence_level = ConfidenceLevel.REQUIRES_VERIFICATION
        uncertainty_reason = f"Amount state is {amount_state.value}"
    else:
        confidence = component.confidence or 0.95
        confidence_level = _get_confidence_level(confidence)
        uncertainty_reason = None

    return EvidenceItem(
        evidence_type=EvidenceType.EXTRACTED_VALUE,
        source_document_id=document_id,
        source_document_role="primary",
        page_number=component.page,
        field_id=component.amount.field_id if component.amount else None,
        component_id=component.component_id,
        original_text=component.raw_text or component.raw_label or component.name,
        interpreted_as=component.normalized_label or component.normalized_name,
        extracted_value=amount_val,
        normalized_label=component.normalized_label or component.name,
        semantic_category=component.category.value if component.category else None,
        bounding_box=component.bounding_box.model_dump() if component.bounding_box else None,
        confidence=confidence,
        confidence_level=confidence_level,
        uncertainty_reason=uncertainty_reason,
    )


def _build_evidence_from_validation(
    check: ValidationCheck,
    document_id: UUID,
) -> EvidenceItem:
    """Build an evidence item from a validation check."""
    return EvidenceItem(
        evidence_type=EvidenceType.DETERMINISTIC_CALCULATION,
        source_document_id=document_id,
        source_document_role="primary",
        validation_id=check.validation_id,
        original_text=check.message,
        interpreted_as=check.check_code,
        extracted_value=check.calculated_value
        if isinstance(check.calculated_value, (int, float))
        else None,
        semantic_category=check.check_code,
        confidence=1.0,
        confidence_level=ConfidenceLevel.HIGH,
        calculation_inputs={
            "check_code": check.check_code,
            "expected_value": check.expected_value,
            "calculated_value": check.calculated_value,
        },
        calculation_expected=float(check.expected_value)
        if isinstance(check.expected_value, (int, float))
        else None,
        calculation_document_result=float(check.calculated_value)
        if isinstance(check.calculated_value, (int, float))
        else None,
        calculation_delta=check.absolute_delta,
        calculation_status=check.status.value,
    )


def _build_calculation_explanation(check: ValidationCheck) -> CalculationExplanation:
    """Build a calculation explanation from a validation check."""
    return CalculationExplanation(
        check_code=check.check_code,
        title=_get_check_title(check.check_code),
        inputs={
            "expected_value": check.expected_value,
            "calculated_value": check.calculated_value,
        },
        expected_result=float(check.expected_value)
        if isinstance(check.expected_value, (int, float))
        else None,
        document_result=float(check.calculated_value)
        if isinstance(check.calculated_value, (int, float))
        else None,
        delta=check.absolute_delta,
        status=check.status.value,
        explanation=check.message,
        input_field_ids=check.input_field_ids,
    )


def _get_check_title(check_code: str) -> str:
    """Get human-readable title for a check code."""
    titles = {
        "QUOTATION_SUBTOTAL_CONSISTENCY": "Component Reconciliation",
        "QUOTATION_NET_TOTAL_CONSISTENCY": "Quoted Total Reconciliation",
        "ARITHMETIC_LINE_ITEMS_SUM": "Line Item Sum",
        "ARITHMETIC_TOTAL_CONSISTENCY": "Total Consistency",
        "ARITHMETIC_TAX_MATCH": "Tax Calculation",
        "LINE_ITEM_EXTENSION_MATCH": "Line Item Extension",
        "DATE_SEQUENCE_CHECK": "Date Sequence",
        "PAYMENT_STATUS_RECONCILIATION": "Payment Status",
        "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR": "Financial Content",
    }
    return titles.get(check_code, check_code.replace("_", " ").title())


def _build_finding_explanation_from_validation(
    check: ValidationCheck,
    document: StructuredFinancialDocument,
    document_id: UUID,
) -> FindingExplanation:
    """Build a finding explanation from a validation check."""
    evidence_items = [_build_evidence_from_validation(check, document_id)]

    # Add component evidence for the input fields
    for field_id in check.input_field_ids:
        for comp in document.cost_breakdown:
            if comp.amount and comp.amount.field_id == field_id:
                evidence_items.append(_build_evidence_from_component(comp, document_id))
                break

    # Build what we know
    what_we_know = []
    if check.expected_value is not None:
        what_we_know.append(f"Expected value: {check.expected_value}")
    if check.calculated_value is not None:
        what_we_know.append(f"Calculated value: {check.calculated_value}")
    if check.absolute_delta is not None:
        what_we_know.append(f"Difference: {check.absolute_delta}")

    # Build what we infer
    what_we_infer = []
    if check.status == ValidationStatus.FAIL:
        what_we_infer.append("The stated amounts do not mathematically reconcile.")
    elif check.status == ValidationStatus.INCONCLUSIVE:
        what_we_infer.append(
            "The calculation could not be completed due to missing or unreadable data."
        )
    else:
        what_we_infer.append("The stated amounts mathematically reconcile.")

    # Build what remains uncertain
    what_remains_uncertain = []
    if check.status == ValidationStatus.INCONCLUSIVE:
        what_remains_uncertain.append(
            "The document does not contain sufficient information to complete this verification."
        )
    if check.absolute_delta and check.absolute_delta > 0.02:
        what_remains_uncertain.append(
            "The reason for the discrepancy is not established by the available evidence."
        )

    # Build action
    action = None
    if check.status == ValidationStatus.FAIL and check.absolute_delta:
        action = f"Ask the seller to explain the {check.absolute_delta} difference."
    elif check.status == ValidationStatus.INCONCLUSIVE:
        action = "Request clarification from the seller."

    # Build why flagged
    why_flagged = _get_why_flagged_for_check(check)

    return FindingExplanation(
        finding_id=check.validation_id,
        finding_type=check.check_code,
        concise_explanation=check.message,
        what_we_know=what_we_know,
        what_we_infer=what_we_infer,
        what_remains_uncertain=what_remains_uncertain,
        action=action,
        evidence=evidence_items,
        calculation_explanation=_build_calculation_explanation(check),
        confidence=1.0,
        confidence_level=ConfidenceLevel.HIGH,
        why_flagged=why_flagged,
    )


def _get_why_flagged_for_check(check: ValidationCheck) -> str:
    """Get a concise 'why flagged' explanation for a validation check."""
    if check.check_code == "QUOTATION_SUBTOTAL_CONSISTENCY":
        return "Listed components differ from the stated subtotal."
    if check.check_code == "QUOTATION_NET_TOTAL_CONSISTENCY":
        return "The quoted total does not match the calculated net total."
    if check.check_code == "ARITHMETIC_LINE_ITEMS_SUM":
        return "Itemized line items do not sum to the stated total."
    if check.check_code == "ARITHMETIC_TOTAL_CONSISTENCY":
        return "The grand total does not match the sum of components."
    if check.check_code == "ARITHMETIC_TAX_MATCH":
        return "The tax amount does not match the expected calculation."
    if check.check_code == "LINE_ITEM_EXTENSION_MATCH":
        return "Line item quantity × unit price does not equal the stated total."
    if check.check_code == "DATE_SEQUENCE_CHECK":
        return "The due date precedes the issue date."
    if check.check_code == "PAYMENT_STATUS_RECONCILIATION":
        return "Payment amounts do not reconcile with the stated total."
    if check.check_code == "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR":
        return "No financial data was detected in the document."
    return "A discrepancy was detected during validation."


def _build_finding_explanation_from_contextual(
    finding: ContextualFinding,
    document_id: UUID,
) -> FindingExplanation:
    """Build a finding explanation from a contextual finding."""
    evidence_items = []

    # Add primary evidence
    for ev in finding.primary_evidence:
        evidence_items.append(
            EvidenceItem(
                evidence_type=EvidenceType.DOCUMENT_TEXT,
                source_document_id=ev.document_id,
                source_document_role="primary",
                page_number=ev.page_number,
                original_text=ev.raw_text,
                interpreted_as=ev.label,
                extracted_value=ev.amount,
                normalized_label=ev.label,
                bounding_box=ev.bounding_box.model_dump() if ev.bounding_box else None,
                confidence=finding.confidence,
                confidence_level=_get_confidence_level(finding.confidence),
            )
        )

    # Add supporting evidence
    for ev in finding.supporting_evidence:
        evidence_items.append(
            EvidenceItem(
                evidence_type=EvidenceType.SUPPORTING_DOCUMENT,
                source_document_id=ev.document_id,
                source_document_role="supporting",
                page_number=ev.page_number,
                original_text=ev.raw_text,
                interpreted_as=ev.label,
                extracted_value=ev.amount,
                normalized_label=ev.label,
                bounding_box=ev.bounding_box.model_dump() if ev.bounding_box else None,
                confidence=finding.confidence,
                confidence_level=_get_confidence_level(finding.confidence),
            )
        )

    # Build what we know
    what_we_know = []
    if finding.primary_amount is not None:
        what_we_know.append(f"Current document amount: {finding.primary_amount}")
    if finding.supporting_amount is not None:
        what_we_know.append(f"Supporting document amount: {finding.supporting_amount}")
    if finding.delta_amount is not None:
        what_we_know.append(f"Difference: {finding.delta_amount}")

    # Build what we infer
    what_we_infer = []
    if finding.finding_type.value == "POTENTIAL_OVERLAP":
        what_we_infer.append("Potential overlap between current and supporting documents.")
    elif finding.finding_type.value == "PRICE_VARIANCE":
        what_we_infer.append("Price variance between current and supporting documents.")
    elif finding.finding_type.value == "COVERAGE_COMPARISON":
        what_we_infer.append("Coverage comparison between current and supporting documents.")

    # Build what remains uncertain
    what_remains_uncertain = finding.what_to_verify

    # Build action
    action = finding.questions_to_ask[0] if finding.questions_to_ask else "Verify with the seller."

    # Build why flagged
    why_flagged = _get_why_flagged_for_contextual(finding)

    # Build supporting document explanation
    supporting_explanation = None
    if finding.supporting_evidence:
        supporting_explanation = SupportingDocumentExplanation(
            finding_type=finding.finding_type.value,
            current_document_label=finding.primary_evidence[0].label
            if finding.primary_evidence
            else "Current document",
            current_document_amount=finding.primary_amount,
            current_document_text=finding.primary_evidence[0].raw_text
            if finding.primary_evidence
            else None,
            supporting_document_label=finding.supporting_evidence[0].label
            if finding.supporting_evidence
            else "Supporting document",
            supporting_document_amount=finding.supporting_amount,
            supporting_document_text=finding.supporting_evidence[0].raw_text
            if finding.supporting_evidence
            else None,
            finding=finding.finding_type.value.replace("_", " ").title(),
            uncertainty="; ".join(finding.what_to_verify)
            if finding.what_to_verify
            else "Requires verification.",
            action=finding.questions_to_ask[0]
            if finding.questions_to_ask
            else "Verify with the seller.",
            primary_evidence=[e for e in evidence_items if e.source_document_role == "primary"],
            supporting_evidence=[
                e for e in evidence_items if e.source_document_role == "supporting"
            ],
        )

    return FindingExplanation(
        finding_id=finding.finding_id,
        finding_type=finding.finding_type.value,
        concise_explanation=finding.description,
        what_we_know=what_we_know,
        what_we_infer=what_we_infer,
        what_remains_uncertain=what_remains_uncertain,
        action=action,
        evidence=evidence_items,
        supporting_document_explanation=supporting_explanation,
        confidence=finding.confidence,
        confidence_level=_get_confidence_level(finding.confidence),
        why_flagged=why_flagged,
    )


def _get_why_flagged_for_contextual(finding: ContextualFinding) -> str:
    """Get a concise 'why flagged' explanation for a contextual finding."""
    if finding.finding_type.value == "POTENTIAL_OVERLAP":
        return "Similar items appear in both the current and supporting documents."
    if finding.finding_type.value == "PRICE_VARIANCE":
        return "The current document total differs from the supporting document."
    if finding.finding_type.value == "COVERAGE_COMPARISON":
        return "Coverage in the current document may overlap with the supporting document."
    return "A potential issue was identified during cross-document comparison."


def _build_question_provenance(
    question: SmartCostReductionQuestion,
    finding_type: str,
    finding_id: UUID | None,
    evidence_ids: list[UUID],
) -> QuestionProvenance:
    """Build provenance for a generated question."""
    return QuestionProvenance(
        question_id=question.question_id,
        question=question.question,
        source_finding_type=finding_type,
        source_finding_id=finding_id,
        source_evidence_ids=evidence_ids,
        confidence=question.confidence,
    )


def _build_suggested_message_items(
    questions: list[SmartCostReductionQuestion],
    question_provenance: list[QuestionProvenance],
) -> list[SuggestedMessageItem]:
    """Build suggested message items with provenance."""
    items = []
    for q in questions:
        # Find matching provenance
        prov = next(
            (p for p in question_provenance if p.question_id == q.question_id),
            None,
        )
        items.append(
            SuggestedMessageItem(
                text=q.question,
                source_finding_type=prov.source_finding_type if prov else "UNKNOWN",
                source_finding_id=prov.source_finding_id if prov else None,
                source_question_id=q.question_id,
                source_evidence_ids=prov.source_evidence_ids if prov else [],
            )
        )
    return items


class EvidenceFirstService:
    """Builds evidence-first explainability payloads for findings.

    This service is purely deterministic and does not call an LLM.
    It structures existing pipeline results into evidence traceability.
    """

    @classmethod
    def build_evidence_result(
        cls,
        result_id: UUID,
        document: StructuredFinancialDocument,
        validation_checks: list[ValidationCheck],
        flags: list[DecisionFlag],
        contextual_findings: list[ContextualFinding],
        smart_questions: list[SmartCostReductionQuestion],
    ) -> EvidenceFirstResult:
        """Build complete evidence-first explainability payload."""
        document_id = document.document_id

        # Build evidence items from components
        evidence_items = []
        for comp in document.cost_breakdown:
            evidence_items.append(_build_evidence_from_component(comp, document_id))

        # Build finding explanations from validation checks
        finding_explanations = []
        for check in validation_checks:
            # Always add validation evidence to the top-level evidence items
            evidence_items.append(_build_evidence_from_validation(check, document_id))
            if check.status in (ValidationStatus.FAIL, ValidationStatus.INCONCLUSIVE):
                finding_explanations.append(
                    _build_finding_explanation_from_validation(check, document, document_id)
                )

        # Build finding explanations from contextual findings
        for finding in contextual_findings:
            explanation = _build_finding_explanation_from_contextual(finding, document_id)
            finding_explanations.append(explanation)
            # Also add contextual finding evidence to top-level evidence items
            evidence_items.extend(explanation.evidence)

        # Build question provenance
        question_provenance = []
        for q in smart_questions:
            # Determine finding type from question category or classification
            finding_type = q.classification or q.category or "UNKNOWN"
            evidence_ids = []
            if q.ocr_line:
                # Find matching evidence
                for ev in evidence_items:
                    if ev.original_text and q.ocr_line in ev.original_text:
                        evidence_ids.append(ev.evidence_id)
                        break

            question_provenance.append(
                _build_question_provenance(q, finding_type, None, evidence_ids)
            )

        # Build suggested message items
        suggested_message_items = _build_suggested_message_items(
            smart_questions, question_provenance
        )

        return EvidenceFirstResult(
            result_id=result_id,
            evidence_items=evidence_items,
            finding_explanations=finding_explanations,
            question_provenance=question_provenance,
            suggested_message_items=suggested_message_items,
        )
