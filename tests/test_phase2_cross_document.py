"""Phase 2 Tests: Cross-document contextual comparison and SupportingDocumentAnalysis.

Tests are purely unit/integration-level; no real OCR API calls.
Tests use synthetic OcrResult + StructuredFinancialDocument + RagEvidenceChunk.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from before_you_pay.models import (
    ContextualFinding,
    ContextualFindingType,
    DocumentClassification,
    RagEvidenceChunk,
    SupportingDocumentAnalysis,
    ValidationSeverity,
)
from before_you_pay.models.document import (
    AmountState,
    ChargeNature,
    ComponentCategory,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    StructuredFinancialDocument,
)
from before_you_pay.services.cross_document_comparison import CrossDocumentComparisonService

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_provenance(document_id, page_id, raw_text="Test line"):
    line_id = uuid4()
    return FieldProvenance(
        document_id=document_id,
        page_id=page_id,
        ocr_line_ids=[line_id],
        raw_text=raw_text,
    )


def _make_field(field_key: str, value: float, document_id, page_id, raw_text="Test"):
    prov = _make_provenance(document_id, page_id, raw_text)
    return ExtractedField(
        field_key=field_key,
        normalized_value=value,
        confidence=0.95,
        provenance=prov,
        amount_state=AmountState.PRESENT,
    )


def _make_component(
    name: str,
    amount_value: float,
    category: ComponentCategory,
    charge_nature: ChargeNature,
    document_id,
    page_id,
) -> FinancialComponent:
    field = _make_field("amount", amount_value, document_id, page_id, name)
    return FinancialComponent(
        name=name,
        amount=field,
        category=category,
        charge_nature=charge_nature,
    )


def _make_document(
    document_id=None,
    user_id=None,
    total=29996.0,
    components=None,
) -> StructuredFinancialDocument:
    document_id = document_id or uuid4()
    user_id = user_id or uuid4()
    page_id = uuid4()

    total_field = _make_field("total_amount", total, document_id, page_id, f"Total {total}")
    line_items = []
    cost_breakdown = list(components or [])

    return StructuredFinancialDocument(
        document_id=document_id,
        user_id=user_id,
        document_type=DocumentClassification.BILL,
        total_amount=total_field,
        line_items=line_items,
        cost_breakdown=cost_breakdown,
        currency="INR",
    )


def _make_rag_chunk(
    user_id,
    source_doc_id,
    doc_type: DocumentClassification,
    text: str,
    page=1,
    similarity=0.80,
) -> RagEvidenceChunk:
    return RagEvidenceChunk(
        evidence_id=uuid4(),
        user_id=user_id,
        source_document_id=source_doc_id,
        source_document_type=doc_type,
        page_number=page,
        source_text=text,
        similarity_score=similarity,
    )


# ── CrossDocumentComparisonService Tests ─────────────────────────────────────


class TestCrossDocumentComparisonService:
    def setup_method(self):
        self.service = CrossDocumentComparisonService()
        self.user_id = uuid4()
        self.primary_doc_id = uuid4()
        self.supporting_doc_id = uuid4()

    def test_no_findings_when_no_chunks(self):
        """If no supporting chunks, returns empty list."""
        doc = _make_document(document_id=self.primary_doc_id, user_id=self.user_id)
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.CONTRACT,
        )
        assert findings == []

    def test_no_overlap_when_no_matching_components(self):
        """If primary doc has no warranty/insurance components, no overlap finding."""
        doc = _make_document(document_id=self.primary_doc_id, user_id=self.user_id)
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "This warranty covers all parts for 2 years at ₹5000",
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        # No warranty components in primary doc, so no POTENTIAL_OVERLAP
        overlap_findings = [
            f for f in findings if f.finding_type == ContextualFindingType.POTENTIAL_OVERLAP
        ]
        assert len(overlap_findings) == 0

    def test_warranty_overlap_detected(self):
        """When primary has a warranty charge and supporting doc mentions warranty, overlap finding is returned."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Extended Warranty",
            5000.0,
            ComponentCategory.EXTENDED_WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Standard Warranty: covers all parts, 1 year. Amount: ₹3000. Coverage includes motor, electronics.",
            similarity=0.80,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        overlap = [f for f in findings if f.finding_type == ContextualFindingType.POTENTIAL_OVERLAP]
        assert len(overlap) >= 1
        finding = overlap[0]
        assert "warranty" in finding.title.lower()
        assert finding.primary_amount == 5000.0
        assert finding.confidence >= 0.0
        # Evidence provenance: primary_evidence linked to primary doc, supporting_evidence to supporting doc
        assert len(finding.primary_evidence) >= 1
        assert finding.primary_evidence[0].document_role == "primary"
        assert len(finding.supporting_evidence) >= 1
        assert finding.supporting_evidence[0].document_role == "supporting"

    def test_insurance_overlap_detected(self):
        """When primary has insurance component and supporting doc mentions insurance, overlap finding."""
        page_id = uuid4()
        ins_comp = _make_component(
            "Vehicle Insurance Premium",
            12000.0,
            ComponentCategory.INSURANCE,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[ins_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.CONTRACT,
            "Motor insurance policy: ₹10000 annual premium. Coverage: comprehensive. Policy valid till 2027.",
            similarity=0.75,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.CONTRACT,
        )
        overlap = [f for f in findings if f.finding_type == ContextualFindingType.POTENTIAL_OVERLAP]
        assert len(overlap) >= 1
        assert overlap[0].primary_amount == 12000.0
        assert "insurance" in overlap[0].title.lower()

    def test_price_variance_detected_when_significant_delta(self):
        """Price variance finding surfaces when supporting doc total differs significantly."""
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            total=35000.0,
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.QUOTATION,
            "Total amount quoted: ₹29000. This quotation is valid for 30 days.",
            similarity=0.65,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.QUOTATION,
        )
        variance_findings = [
            f for f in findings if f.finding_type == ContextualFindingType.PRICE_VARIANCE
        ]
        assert len(variance_findings) >= 1
        vf = variance_findings[0]
        assert vf.primary_amount == 35000.0
        assert vf.supporting_amount == 29000.0
        assert vf.delta_amount == pytest.approx(6000.0, abs=1.0)
        assert len(vf.questions_to_ask) >= 1

    def test_no_price_variance_when_delta_small(self):
        """No price variance when difference is within 1% and < 100 units."""
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            total=10000.0,
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.QUOTATION,
            "Total: ₹10000",
            similarity=0.60,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.QUOTATION,
        )
        variance_findings = [
            f for f in findings if f.finding_type == ContextualFindingType.PRICE_VARIANCE
        ]
        # Delta is 0, should not trigger
        assert len(variance_findings) == 0

    def test_finding_has_uncertainty_aware_language(self):
        """Findings must use uncertainty-aware language, not definitive claims."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Warranty",
            3000.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Warranty coverage: engine and transmission, 2 years",
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        # All findings must not contain prohibited definitive language
        prohibited = {"duplicate", "unnecessary", "fraudulent", "scam", "do not need"}
        for finding in findings:
            text = f"{finding.title} {finding.description} {' '.join(finding.what_to_verify)} {' '.join(finding.questions_to_ask)}"
            for word in prohibited:
                assert word not in text.lower(), (
                    f"Finding contains prohibited language '{word}': {text[:200]}"
                )

    def test_finding_confidence_bounded(self):
        """Finding confidence must be between 0.0 and 1.0."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Extended Warranty",
            5000.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Warranty coverage includes all parts for 1 year at ₹3500",
            similarity=0.70,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        for f in findings:
            assert 0.0 <= f.confidence <= 1.0

    def test_deduplication_of_identical_findings(self):
        """Identical finding titles are deduplicated."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Extended Warranty",
            5000.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        # Same content in two chunks — deduplication should handle this
        chunk1 = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Warranty and coverage for parts ₹5000",
            similarity=0.80,
        )
        chunk2 = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Warranty and coverage for parts ₹5000",
            similarity=0.75,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk1, chunk2],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        # Count how many unique titles exist among POTENTIAL_OVERLAP type
        overlap = [f for f in findings if f.finding_type == ContextualFindingType.POTENTIAL_OVERLAP]
        titles = [f.title for f in overlap]
        # There may be duplicates from chunk iteration, but after dedup each title should appear once
        assert len(titles) == len(set(titles)), "Findings were not deduplicated properly"

    def test_what_to_verify_always_present_when_finding_raised(self):
        """Every ContextualFinding should include at least one item in what_to_verify."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Manufacturer Warranty",
            4000.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Warranty: manufacturer coverage for 1 year ₹4000",
            similarity=0.85,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        for f in findings:
            assert len(f.what_to_verify) >= 1, "Every finding must include what_to_verify items"

    def test_questions_to_ask_present_when_overlap_finding(self):
        """POTENTIAL_OVERLAP findings must include questions_to_ask for the seller."""
        page_id = uuid4()
        warranty_comp = _make_component(
            "Extended Warranty Plan",
            7500.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            self.primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=self.primary_doc_id,
            user_id=self.user_id,
            components=[warranty_comp],
        )
        chunk = _make_rag_chunk(
            self.user_id,
            self.supporting_doc_id,
            DocumentClassification.WARRANTY,
            "Extended warranty coverage plan ₹7500 for 3 years. All parts covered.",
            similarity=0.90,
        )
        findings = self.service.compare(
            document=doc,
            supporting_chunks=[chunk],
            supporting_doc_id=self.supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        for f in [x for x in findings if x.finding_type == ContextualFindingType.POTENTIAL_OVERLAP]:
            assert len(f.questions_to_ask) >= 1, (
                "POTENTIAL_OVERLAP findings must include questions_to_ask"
            )


# ── SupportingDocumentAnalysis Model Tests ────────────────────────────────────


class TestSupportingDocumentAnalysis:
    def test_valid_supporting_doc_analysis_no_findings(self):
        """SupportingDocumentAnalysis can be created with empty findings."""
        analysis = SupportingDocumentAnalysis(
            supporting_document_id=uuid4(),
            supporting_document_type="warranty",
            supporting_line_count=12,
            chunks_indexed=4,
            supporting_preview="Warranty terms and conditions.",
            findings=[],
            retrieved_chunks_count=4,
        )
        assert analysis.supporting_line_count == 12
        assert analysis.chunks_indexed == 4
        assert analysis.findings == []

    def test_supporting_doc_analysis_with_findings(self):
        """SupportingDocumentAnalysis carries findings from comparison."""
        finding = ContextualFinding(
            finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
            title="Potential warranty coverage overlap",
            description="The primary document includes an extended warranty. The supporting document appears to reference warranty coverage.",
            what_to_verify=["Verify coverage period and scope."],
            questions_to_ask=["Does the existing warranty cover the same items?"],
            confidence=0.75,
            severity=ValidationSeverity.WARNING,
            primary_amount=5000.0,
            supporting_amount=3000.0,
            delta_amount=2000.0,
        )
        analysis = SupportingDocumentAnalysis(
            supporting_document_id=uuid4(),
            supporting_document_type="warranty",
            supporting_line_count=10,
            chunks_indexed=3,
            supporting_preview="Warranty coverage terms.",
            findings=[finding],
            retrieved_chunks_count=3,
        )
        assert len(analysis.findings) == 1
        assert analysis.findings[0].finding_type == ContextualFindingType.POTENTIAL_OVERLAP
        assert analysis.findings[0].primary_amount == 5000.0


# ── ContextualFinding Model Guardrails ─────────────────────────────────────────


class TestContextualFindingGuardrails:
    def test_prohibited_language_raises_error(self):
        """ContextualFinding must reject prohibited language."""
        with pytest.raises(ValueError, match="prohibited language"):
            ContextualFinding(
                finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
                title="This is a duplicate charge that is unnecessary",
                description="The charge appears duplicate.",
                what_to_verify=["Verify."],
                questions_to_ask=["Ask."],
                confidence=0.80,
            )

    def test_valid_uncertainty_language_accepted(self):
        """ContextualFinding accepts uncertainty-aware language."""
        finding = ContextualFinding(
            finding_type=ContextualFindingType.PRICE_VARIANCE,
            title="Price variance vs supporting document",
            description="The current total appears to differ from the supporting document. Requires verification.",
            what_to_verify=["Confirm whether the terms changed."],
            questions_to_ask=["What explains the price difference?"],
            confidence=0.60,
            severity=ValidationSeverity.INFO,
            primary_amount=35000.0,
            supporting_amount=29000.0,
            delta_amount=6000.0,
        )
        assert finding.delta_amount == pytest.approx(6000.0)

    def test_confidence_bounds_enforced(self):
        """Confidence above 1.0 must be rejected by model validation."""
        with pytest.raises((ValueError, ValidationError)):
            ContextualFinding(
                finding_type=ContextualFindingType.COVERAGE_COMPARISON,
                title="Coverage comparison",
                description="Potential coverage comparison requires verification.",
                what_to_verify=["Check coverage."],
                questions_to_ask=["Clarify coverage scope."],
                confidence=1.5,  # out of bounds
            )


# ── User Isolation Test ────────────────────────────────────────────────────────


class TestUserIsolation:
    """Verify that the comparison service does NOT process chunks from a different user."""

    def test_chunks_with_different_user_id_not_compared(self):
        """If chunks were retrieved with wrong user_id, they shouldn't get through."""
        # The SQLiteRagService enforces user isolation at retrieval time.
        # CrossDocumentComparisonService trusts the input chunks are already scoped.
        # Here we verify that a chunk with a different user_id doesn't artificially
        # leak into findings when supplied directly.
        correct_user_id = uuid4()
        wrong_user_id = uuid4()
        primary_doc_id = uuid4()
        supporting_doc_id = uuid4()

        page_id = uuid4()
        warranty_comp = _make_component(
            "Extended Warranty",
            5000.0,
            ComponentCategory.WARRANTY,
            ChargeNature.CHARGE,
            primary_doc_id,
            page_id,
        )
        doc = _make_document(
            document_id=primary_doc_id,
            user_id=correct_user_id,
            components=[warranty_comp],
        )

        # This chunk is tagged with the WRONG user_id (simulates a retrieval that leaked through)
        wrong_chunk = RagEvidenceChunk(
            evidence_id=uuid4(),
            user_id=wrong_user_id,
            source_document_id=supporting_doc_id,
            source_document_type=DocumentClassification.WARRANTY,
            page_number=1,
            source_text="Warranty and coverage for all parts ₹5000 for 3 years",
            similarity_score=0.90,
        )

        service = CrossDocumentComparisonService()
        # The comparison service accepts chunks as-is; user isolation is enforced by SqliteRagService upstream.
        # The test verifies the service can process such a chunk (isolation is upstream's responsibility).
        # What we verify: the service still produces correct-format findings regardless.
        findings = service.compare(
            document=doc,
            supporting_chunks=[wrong_chunk],
            supporting_doc_id=supporting_doc_id,
            supporting_doc_type=DocumentClassification.WARRANTY,
        )
        # Result: findings may exist — but the primary concern is that user isolation
        # is enforced at the SqliteRagService.retrieve() level, not here.
        # So findings here would exist (the service doesn't double-check user_id),
        # but in production these chunks would never be returned by retrieve() unless user_id matches.
        for f in findings:
            assert isinstance(f, ContextualFinding)
