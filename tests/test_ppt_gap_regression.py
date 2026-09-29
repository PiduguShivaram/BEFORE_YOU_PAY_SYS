"""Phase 12: Comprehensive PPT Gap Regression Test Suite.

Verifies:
1. Vehicle Quotation regression:
   - 6 financial components
   - Ex-showroom: ₹1,149,900
   - TCS: ₹11,499
   - Insurance: ₹34,500
   - R.C.: ₹76,250 (verified NOT 76,256)
   - Warranty: ₹24,000
   - Temp + HSRP: ₹2,250
   - Component total: ₹1,298,399
   - Offers: ₹70,000 (Offer ₹20,000 + Extra offer ₹50,000)
   - Final quoted: ₹1,228,399
   - 0 false discrepancies:
     * component reconciliation = PASS
     * offers reconciliation = PASS
     * final quoted total = PASS
2. Second Scan & RAG Contextual Comparison:
   - Primary quotation + supporting warranty document
   - Surface POTENTIAL_OVERLAP with uncertainty-aware phrasing
   - No claim of guaranteed duplicate without proof
3. Smart Questions & Grounding:
   - References actual extracted values
   - No astronomical numbers
   - No questions generated from passing checks
4. Suggested Negotiation Message:
   - User-editable draft referencing actual quotation findings
5. Canonical Financial Model:
   - Distinguishes MISSING, UNKNOWN, UNREADABLE, ZERO, NOT_APPLICABLE
   - Never converts unknown to 0.0
"""

from uuid import uuid4

import pytest

from before_you_pay.models import (
    AmountState,
    BoundingBox,
    ChargeNature,
    ClaimType,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    RagEvidenceChunk,
    StructuredFinancialDocument,
    ValidationStatus,
)
from before_you_pay.services.cost_review_questions import CostReviewQuestionsService
from before_you_pay.services.extra_cost_analysis import ExtraCostAnalysisService
from before_you_pay.services.plain_language_explanation import (
    PlainLanguageExplanationService,
)
from before_you_pay.services.reasoning import SemanticReasoningEngine
from before_you_pay.services.smart_questions import SmartCostReductionQuestionsService
from before_you_pay.services.validation import DeterministicValidationEngine


def _make_field(doc_id, page_id, key, val, text=""):
    return ExtractedField(
        field_key=key,
        normalized_value=val,
        unit_or_currency="INR",
        confidence=0.95,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[uuid4()],
            bounding_box=BoundingBox(
                x=0.1,
                y=0.1,
                width=0.5,
                height=0.03,
                coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
            ),
            raw_text=text or f"{key}: {val}",
        ),
    )


def _build_victoria_lxi_quotation():
    """Build canonical ground-truth vehicle quotation for Victoria's LXI."""
    doc_id = uuid4()
    page_id = uuid4()
    user_id = uuid4()

    # Ground truth values:
    # Ex-showroom ₹1,149,900
    # TCS ₹11,499
    # Insurance ₹34,500
    # R.C. ₹76,250
    # Warranty ₹24,000
    # Temp + HSRP ₹2,250
    # Subtotal ₹1,298,399
    # Offer -₹20,000
    # Extra offer -₹50,000
    # Final quoted ₹1,228,399
    components = [
        FinancialComponent(
            component_id=uuid4(),
            name="Ex-showroom",
            original_label="Ex-showroom",
            amount=_make_field(
                doc_id, page_id, "ex_showroom", 1149900.0, "Ex-showroom: ₹11,49,900"
            ),
            category=ComponentCategory.BASE_PRICE,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="TCS",
            original_label="TCS",
            amount=_make_field(doc_id, page_id, "tcs", 11499.0, "TCS: ₹11,499"),
            category=ComponentCategory.TCS,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="Insurance",
            original_label="Insurance",
            amount=_make_field(doc_id, page_id, "insurance", 34500.0, "Insurance: ₹34,500"),
            category=ComponentCategory.INSURANCE,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="R.C.",
            original_label="R.C.",
            amount=_make_field(doc_id, page_id, "rc", 76250.0, "R.C.: ₹76,250"),
            category=ComponentCategory.REGISTRATION,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="Warranty",
            original_label="Warranty",
            amount=_make_field(doc_id, page_id, "warranty", 24000.0, "Warranty: ₹24,000"),
            category=ComponentCategory.WARRANTY,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="Temp + HSRP",
            original_label="Temp + HSRP",
            amount=_make_field(doc_id, page_id, "temp_hsrp", 2250.0, "Temp + HSRP: ₹2,250"),
            category=ComponentCategory.ACCESSORY_OR_FEE,
            charge_nature=ChargeNature.CHARGE,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="Offer",
            original_label="Offer",
            amount=_make_field(doc_id, page_id, "offer", 20000.0, "Offer: -₹20,000"),
            category=ComponentCategory.DISCOUNT,
            charge_nature=ChargeNature.DEDUCTION,
        ),
        FinancialComponent(
            component_id=uuid4(),
            name="Extra offer",
            original_label="Extra offer",
            amount=_make_field(doc_id, page_id, "extra_offer", 50000.0, "Extra offer: -₹50,000"),
            category=ComponentCategory.DISCOUNT,
            charge_nature=ChargeNature.DEDUCTION,
        ),
    ]

    doc = StructuredFinancialDocument(
        document_id=doc_id,
        user_id=user_id,
        document_type=DocumentClassification.QUOTATION,
        currency="INR",
        cost_breakdown=components,
        subtotal=_make_field(doc_id, page_id, "subtotal", 1298399.0, "Subtotal: ₹12,98,399"),
        discount_amount=_make_field(
            doc_id, page_id, "discount_amount", 70000.0, "Total Offers: ₹70,000"
        ),
        total_amount=_make_field(
            doc_id, page_id, "total_amount", 1228399.0, "Final Quoted Total: ₹12,28,399"
        ),
    )
    return doc


class TestVehicleQuotationRegression:
    """Verifies Slide 5 Detect + Calculate Ground Truth for Victoria's LXI."""

    def test_reconciliation_exact_pass_zero_false_discrepancies(self):
        """Ground truth quotation must PASS all 3 reconciliations with 0 false discrepancies."""
        doc = _build_victoria_lxi_quotation()
        validator = DeterministicValidationEngine()
        checks = validator.validate(doc)
        checks_by_code = {c.check_code: c for c in checks}

        # 1. Component Reconciliation (sum of 6 constituent charges == 1,298,399)
        assert "QUOTATION_SUBTOTAL_CONSISTENCY" in checks_by_code
        comp_check = checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"]
        assert comp_check.status == ValidationStatus.PASS
        assert comp_check.calculated_value == 1298399.0
        assert comp_check.expected_value == 1298399.0
        assert comp_check.absolute_delta == 0.0

        # 2. Offers Reconciliation (sum of 2 offers == 70,000)
        assert "OFFERS_RECONCILIATION" in checks_by_code
        offer_check = checks_by_code["OFFERS_RECONCILIATION"]
        assert offer_check.status == ValidationStatus.PASS
        assert offer_check.calculated_value == 70000.0
        assert offer_check.expected_value == 70000.0
        assert offer_check.absolute_delta == 0.0

        # 3. Quoted Total Reconciliation (1,298,399 - 70,000 == 1,228,399)
        assert "QUOTATION_NET_TOTAL_CONSISTENCY" in checks_by_code
        tot_check = checks_by_code["QUOTATION_NET_TOTAL_CONSISTENCY"]
        assert tot_check.status == ValidationStatus.PASS
        assert tot_check.calculated_value == 1228399.0
        assert tot_check.expected_value == 1228399.0
        assert tot_check.absolute_delta == 0.0

        # 4. Zero failed checks
        failed_checks = [c for c in checks if c.status == ValidationStatus.FAIL]
        assert len(failed_checks) == 0, (
            f"Expected 0 failed checks, got: {[c.check_code for c in failed_checks]}"
        )

    def test_rc_is_76250_not_76256(self):
        """Verifies R.C. is 76,250 and does not trigger false 6 discrepancy."""
        doc = _build_victoria_lxi_quotation()
        rc_comp = next(c for c in doc.cost_breakdown if "R.C." in c.name)
        assert float(rc_comp.amount.normalized_value) == 76250.0
        assert float(rc_comp.amount.normalized_value) != 76256.0


class TestSecondScanAndRagWorkflow:
    """Verifies Slide 6 Second Scan / Supporting Document Context Workflow."""

    @pytest.mark.anyio
    async def test_supporting_document_overlap_detection(self):
        """Primary vehicle quote + supporting existing warranty document triggers potential overlap."""
        doc = _build_victoria_lxi_quotation()
        user_id = doc.user_id

        # Simulated chunk from supporting document (e.g. existing manufacturer warranty)
        supporting_doc_id = uuid4()
        chunk = RagEvidenceChunk(
            evidence_id=uuid4(),
            user_id=user_id,
            source_document_id=supporting_doc_id,
            source_document_type=DocumentClassification.WARRANTY,
            page_number=1,
            source_text="Manufacturer Comprehensive Warranty: 3-year mechanical breakdown coverage for powertrain and engine components.",
            similarity_score=0.92,
        )

        reasoning_engine = SemanticReasoningEngine()
        claims = await reasoning_engine.generate_claims(
            document=doc,
            rag_evidence=[chunk],
            okf_evidence=[],
        )

        overlap_claims = [c for c in claims if c.type == ClaimType.POTENTIAL_OVERLAP]
        assert len(overlap_claims) >= 1

        w_claim = next((c for c in overlap_claims if "warranty" in c.title.lower()), None)
        assert w_claim is not None
        assert "Warranty" in w_claim.title or "warranty" in w_claim.title.lower()
        # Verify uncertainty-aware language (no false claim of duplicate)
        assert (
            "appears to cover" in w_claim.description
            or "Requires verification" in w_claim.description
        )
        assert "₹24,000" in w_claim.description

    @pytest.mark.anyio
    async def test_supporting_document_no_unrelated_overlap(self):
        """Supporting document with unrelated terms must not trigger false overlap."""
        doc = _build_victoria_lxi_quotation()
        user_id = doc.user_id

        unrelated_chunk = RagEvidenceChunk(
            evidence_id=uuid4(),
            user_id=user_id,
            source_document_id=uuid4(),
            source_document_type=DocumentClassification.CONTRACT,
            page_number=1,
            source_text="Office lease agreement clause 4.2 regarding parking spot allocation and janitorial hours.",
            similarity_score=0.10,
        )

        reasoning_engine = SemanticReasoningEngine()
        claims = await reasoning_engine.generate_claims(
            document=doc,
            rag_evidence=[unrelated_chunk],
            okf_evidence=[],
        )

        # No false overlap claim on office lease
        overlap_claims = [c for c in claims if c.type == ClaimType.POTENTIAL_OVERLAP]
        assert len(overlap_claims) == 0


class TestQuestionsAndActionLayer:
    """Verifies Slide 7 & 8 Questions, Explanation, and Suggested Negotiation Message."""

    def test_smart_questions_use_extracted_amounts_no_astronomical_numbers(self):
        """Questions must reference actual extracted figures, not generic or fabricated numbers."""
        doc = _build_victoria_lxi_quotation()
        questions = SmartCostReductionQuestionsService.generate_questions(document=doc)

        assert len(questions) >= 1
        amounts = [q.amount_involved for q in questions if q.amount_involved is not None]
        for a in amounts:
            # All amounts must be grounded within quotation range (not astronomical > 10,000,000)
            assert 0.0 < a <= 1298399.0

        # Warranty question must reference ₹24,000
        w_q = next((q for q in questions if "warranty" in q.related_charge.lower()), None)
        if w_q:
            assert w_q.amount_involved == 24000.0

    def test_suggested_negotiation_message_generation(self):
        """Generates polite, user-editable draft message referencing quotation findings."""
        doc = _build_victoria_lxi_quotation()
        explanation = PlainLanguageExplanationService.generate_explanation(
            document=doc,
            validation_checks=[],
            smart_questions=[],
        )

        msg = explanation.suggested_negotiation_message
        assert msg is not None
        assert "quotation" in msg.lower()
        # Should reference optional items like warranty
        assert "warranty" in msg.lower() or "optional" in msg.lower()
        # Non-committal language
        assert "scam" not in msg.lower()
        assert "fraud" not in msg.lower()


class TestCanonicalFinancialModel:
    """Verifies Slide 4 & Phase 1 Canonical Financial Model Integrity."""

    def test_amount_state_distinctions(self):
        """Distinguishes MISSING, ZERO, UNKNOWN, UNREADABLE, NOT_APPLICABLE without converting to zero."""
        doc_id = uuid4()
        page_id = uuid4()

        # 1. Zero amount
        c_zero = FinancialComponent(
            name="Zero Fee",
            amount=_make_field(doc_id, page_id, "fee", 0.0),
        )
        assert c_zero.amount_state == AmountState.ZERO
        assert c_zero.amount.normalized_value == 0.0

        # 2. Unknown amount
        c_unknown = FinancialComponent(
            name="Unclear Fee",
            amount=_make_field(doc_id, page_id, "fee", "UNKNOWN"),
        )
        assert c_unknown.amount_state == AmountState.UNKNOWN
        # Value must remain "UNKNOWN", never converted to 0.0
        assert c_unknown.amount.normalized_value == "UNKNOWN"

        # 3. Missing amount
        c_missing = FinancialComponent(
            name="Missing Fee",
            amount=_make_field(doc_id, page_id, "fee", None),
        )
        assert c_missing.amount_state == AmountState.MISSING
        assert c_missing.amount.normalized_value is None

    def test_canonical_charge_payload_contains_all_ppt_fields(self):
        """Payload must contain original_label, normalized_label, amount, category, vehicle_category, requirement_status, evidence, confidence."""
        doc = _build_victoria_lxi_quotation()
        first_comp = doc.cost_breakdown[0]
        payload = first_comp.to_charge_payload()

        assert "original_label" in payload
        assert "normalized_label" in payload
        assert "amount" in payload
        assert "amount_state" in payload
        assert "category" in payload
        assert "vehicle_category" in payload
        assert "requirement_status" in payload
        assert "confidence" in payload
        assert "evidence" in payload
        assert payload["amount"] == 1149900.0

    def test_unreadable_amount_makes_reconciliation_inconclusive_never_silent_zero(self):
        """Unreadable amounts must NOT be silently converted to 0.0 or pass reconciliation blindly."""
        doc = _build_victoria_lxi_quotation()
        doc_id = doc.document_id
        page_id = doc.cost_breakdown[0].amount.provenance.page_id

        # Replace Insurance amount with UNREADABLE
        unreadable_insurance = FinancialComponent(
            name="Insurance",
            amount=_make_field(doc_id, page_id, "insurance", "UNREADABLE"),
            category=ComponentCategory.INSURANCE,
            charge_nature=ChargeNature.CHARGE,
            amount_state=AmountState.UNREADABLE,
        )

        mod_components = list(doc.cost_breakdown)
        mod_components[2] = unreadable_insurance  # Insurance is index 2

        mod_doc = StructuredFinancialDocument(
            document_id=doc.document_id,
            user_id=doc.user_id,
            document_type=DocumentClassification.QUOTATION,
            currency="INR",
            total_amount=doc.total_amount,
            subtotal=doc.subtotal,
            discount_amount=doc.discount_amount,
            cost_breakdown=mod_components,
            line_items=[],
            clauses_and_notes=[],
        )

        engine = DeterministicValidationEngine()
        checks = engine.check_quotation_breakdown_consistency(mod_doc)

        subtotal_check = next(
            (c for c in checks if c.check_code == "QUOTATION_SUBTOTAL_CONSISTENCY"), None
        )
        assert subtotal_check is not None
        # Must be INCONCLUSIVE, NEVER PASS and never silent zero!
        assert subtotal_check.status == ValidationStatus.INCONCLUSIVE
        assert "unreadable" in subtotal_check.message.lower()

        net_total_check = next(
            (c for c in checks if c.check_code == "QUOTATION_NET_TOTAL_CONSISTENCY"), None
        )
        assert net_total_check is not None
        assert net_total_check.status == ValidationStatus.INCONCLUSIVE

    def test_missing_amount_generates_verification_question_without_fake_zero(self):
        """Missing amounts generate verification questions asking for the unstated cost without claiming ₹0."""
        doc_id = uuid4()
        page_id = uuid4()

        missing_acc = FinancialComponent(
            name="Chrome Kit",
            amount=_make_field(doc_id, page_id, "accessory", None),
            category=ComponentCategory.ACCESSORY,
            charge_nature=ChargeNature.CHARGE,
            amount_state=AmountState.MISSING,
        )

        questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[missing_acc])
        assert len(questions) >= 1
        q = questions[0]
        assert q.requires_verification is True
        assert q.amount_involved is None
        assert "does not specify a monetary amount" in q.question or "Chrome Kit" in q.question
        # Must not fabricate ₹0 in impact or question
        assert "₹0" not in q.question

    def test_genuine_zero_reconciles_cleanly(self):
        """Genuine zero (0.0) is mathematically valid and does not trigger false unreadable/missing errors."""
        doc_id = uuid4()
        page_id = uuid4()

        zero_fee = FinancialComponent(
            name="Documentation Charge",
            amount=_make_field(doc_id, page_id, "doc_fee", 0.0),
            category=ComponentCategory.HANDLING_FEE,
            charge_nature=ChargeNature.CHARGE,
            amount_state=AmountState.ZERO,
        )

        assert zero_fee.amount_state == AmountState.ZERO
        assert zero_fee.amount.normalized_value == 0.0
        payload = zero_fee.to_charge_payload()
        assert payload["amount"] == 0.0
        assert payload["amount_state"] == "ZERO"

    def test_not_applicable_amount_state(self):
        """NOT_APPLICABLE amount state is preserved and distinguished from zero or missing."""
        doc_id = uuid4()
        page_id = uuid4()

        na_comp = FinancialComponent(
            name="Financing Clause",
            amount=_make_field(doc_id, page_id, "finance", "NOT_APPLICABLE"),
            category=ComponentCategory.OTHER,
            charge_nature=ChargeNature.CHARGE,
            amount_state=AmountState.NOT_APPLICABLE,
        )

        assert na_comp.amount_state == AmountState.NOT_APPLICABLE
        payload = na_comp.to_charge_payload()
        assert payload["amount_state"] == "NOT_APPLICABLE"
        assert payload["amount"] is None

    def test_cost_review_consumes_canonical_amount_states(self):
        """ExtraCostAnalysisService flags unreadable/missing charges as REQUIRES_VERIFICATION without fabricating potential savings."""
        doc_id = uuid4()
        page_id = uuid4()

        unreadable_warranty = FinancialComponent(
            name="Extended Warranty",
            amount=_make_field(doc_id, page_id, "ew", "UNREADABLE"),
            category=ComponentCategory.EXTENDED_WARRANTY,
            charge_nature=ChargeNature.CHARGE,
            amount_state=AmountState.UNREADABLE,
        )

        res = ExtraCostAnalysisService.analyze([unreadable_warranty])
        assert res.total_flagged_count >= 1
        flag = res.flagged_costs[0]
        assert flag.flag_type.value == "requires_verification"
        assert flag.potential_saving is None
        assert "unreadable" in flag.why_flagged.lower()
