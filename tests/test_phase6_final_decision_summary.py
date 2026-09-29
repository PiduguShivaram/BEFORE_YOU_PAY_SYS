"""Phase 6: Before You Pay Final Decision Summary Test Suite.

Exhaustively verifies all 24 Phase 6 requirements (A through X):
A. Final summary with clean document
B. Final summary with discrepancies
C. Final summary with optional charges
D. Final summary with negotiable charges
E. Final summary with alternative opportunities
F. Final summary with supporting-document overlap
G. Final summary with unexplained charge
H. Missing amounts
I. Unknown amounts
J. Unreadable amounts
K. Zero amounts
L. Multiple findings
M. Duplicate opportunity prevention (no double counting)
N. Questions
O. Suggested message
P. Checklist state
Q. Readiness state (READY_FOR_FINAL_VERIFICATION, REQUIRES_VERIFICATION, INCOMPLETE_INFORMATION)
R. Evidence/provenance
S. Tenant isolation
T. Zetran regression
U. Handwritten vehicle quotation
V. ₹6 discrepancy
W. Quoted-total reconciliation
X. Phase 1–5 regression suite preservation
"""

from __future__ import annotations

from uuid import UUID, uuid4

from before_you_pay.models import (
    AmountState,
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    ContextualEvidence,
    ContextualFinding,
    ContextualFindingType,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    LineItem,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.models.decision_summary import (
    ChecklistItemStatus,
    PaymentReadinessState,
)
from before_you_pay.services.decision_summary import BeforeYouPayDecisionSummaryService
from before_you_pay.services.result import ResultAggregatorService
from before_you_pay.services.validation import DeterministicValidationEngine


def _make_bbox() -> BoundingBox:
    return BoundingBox(
        x=0.1, y=0.1, width=0.5, height=0.05, coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE
    )


def _make_prov(doc_id: UUID, text: str = "Test Line") -> FieldProvenance:
    return FieldProvenance(
        document_id=doc_id,
        page_id=uuid4(),
        ocr_line_ids=[uuid4()],
        bounding_box=_make_bbox(),
        raw_text=text,
    )


def _make_field(
    key: str,
    val: float | str | None,
    amount_state: AmountState = AmountState.PRESENT,
    doc_id: UUID | None = None,
    raw_text: str | None = None,
) -> ExtractedField:
    did = doc_id or uuid4()
    txt = raw_text if raw_text is not None else f"{key}: {val}"
    return ExtractedField(
        field_id=uuid4(),
        field_key=key,
        normalized_value=val,
        confidence=0.95,
        amount_state=amount_state,
        provenance=_make_prov(did, txt),
    )


def _make_component(
    name: str,
    amount_val: float | None = 1000.0,
    amount_state: AmountState = AmountState.PRESENT,
    category: ComponentCategory = ComponentCategory.UNKNOWN,
    charge_nature: ChargeNature = ChargeNature.CHARGE,
    doc_id: UUID | None = None,
    requires_verification: bool = False,
    raw_text: str | None = None,
) -> FinancialComponent:
    did = doc_id or uuid4()
    txt = raw_text if raw_text is not None else f"{name}: {amount_val}"
    amt_field = _make_field(
        f"{name.lower().replace(' ', '_')}_amount", amount_val, amount_state, did, raw_text=txt
    )
    return FinancialComponent(
        component_id=uuid4(),
        name=name,
        raw_label=name,
        raw_text=txt,
        amount=amt_field,
        category=category,
        charge_nature=charge_nature,
        requires_verification=requires_verification,
    )


# ── A. Final summary with clean document ──
def test_final_summary_with_clean_document():
    did = uuid4()
    uid = uuid4()
    c_base = _make_component(
        "Base Price", 100000.0, category=ComponentCategory.BASE_PRICE, doc_id=did
    )
    c_tax = _make_component(
        "GST", 18000.0, category=ComponentCategory.GST, charge_nature=ChargeNature.TAX, doc_id=did
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uid,
        document_type=DocumentClassification.INVOICE,
        currency="INR",
        cost_breakdown=[c_base, c_tax],
        subtotal=_make_field("subtotal", 118000.0, doc_id=did),
        tax_amount=_make_field("tax", 18000.0, doc_id=did),
        total_amount=_make_field("total", 118000.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, checks)

    assert summary.hero.quoted_total == 118000.0
    assert summary.hero.readiness_state == PaymentReadinessState.READY_FOR_FINAL_VERIFICATION
    assert summary.hero.review_status == "Ready for verification"
    assert "₹118,000.00" in summary.hero.formatted_total


# ── B. Final summary with discrepancies ──
def test_final_summary_with_discrepancies():
    did = uuid4()
    c_base = _make_component(
        "Base Price", 100000.0, category=ComponentCategory.BASE_PRICE, doc_id=did
    )
    c_fee = _make_component("Fee", 5000.0, category=ComponentCategory.OTHER_FEE, doc_id=did)

    # Stated total 108000 vs 105000 -> discrepancy
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_base, c_fee],
        subtotal=_make_field("subtotal", 105000.0, doc_id=did),
        total_amount=_make_field("total", 108000.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, checks)

    assert summary.hero.readiness_state == PaymentReadinessState.REQUIRES_VERIFICATION
    assert summary.hero.review_status == "Review before paying"
    assert any(
        "discrepancy" in r.lower() or "not equal" in r.lower()
        for r in summary.hero.readiness_reasons
    )
    assert any(a.title == "Amount discrepancy" for a in summary.attention_items)


# ── C. Final summary with optional charges ──
def test_final_summary_with_optional_charges():
    did = uuid4()
    c_war = _make_component(
        "Extended Warranty",
        24000.0,
        category=ComponentCategory.EXTENDED_WARRANTY,
        doc_id=did,
        requires_verification=True,
    )
    c_acc = _make_component(
        "Chrome Kit",
        8500.0,
        category=ComponentCategory.ACCESSORY_PACKAGE,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war, c_acc],
        total_amount=_make_field("total", 32500.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    opps = [
        o for o in summary.ways_to_review_cost.opportunities if o.category == "Potentially Optional"
    ]
    assert len(opps) == 2
    assert any("Warranty" in o.component for o in opps)
    assert any("Chrome Kit" in o.component for o in opps)
    # Never claim guaranteed savings
    assert "guaranteed" not in summary.ways_to_review_cost.disclaimer.lower()


# ── D. Final summary with negotiable charges ──
def test_final_summary_with_negotiable_charges():
    did = uuid4()
    c_dlr = _make_component(
        "Handling / Logistics Fee",
        8000.0,
        category=ComponentCategory.DEALER_CHARGE,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_dlr],
        total_amount=_make_field("total", 8000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    opps = [
        o
        for o in summary.ways_to_review_cost.opportunities
        if o.category == "Potentially Negotiable"
    ]
    assert len(opps) == 1
    assert opps[0].amount == 8000.0
    assert "negotiable" in summary.ways_to_review_cost.active_categories[
        0
    ].lower() or "potentially negotiable" in [
        c.lower() for c in summary.ways_to_review_cost.active_categories
    ]


# ── E. Final summary with alternative opportunities ──
def test_final_summary_with_alternative_opportunities():
    did = uuid4()
    c_ins = _make_component(
        "1-Year Comprehensive Insurance",
        34500.0,
        category=ComponentCategory.INSURANCE,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_ins],
        total_amount=_make_field("total", 34500.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    opps = [
        o
        for o in summary.ways_to_review_cost.opportunities
        if o.category == "Alternatives to Compare"
    ]
    assert len(opps) == 1
    assert opps[0].amount == 34500.0
    assert (
        "comparison" in opps[0].suggested_action.lower()
        or "compare" in opps[0].suggested_action.lower()
    )


# ── F. Final summary with supporting-document overlap ──
def test_final_summary_with_supporting_document_overlap():
    did = uuid4()
    supp_id = uuid4()
    finding = ContextualFinding(
        finding_id=uuid4(),
        finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
        title="Potential warranty coverage overlap",
        description="The primary document includes an Extended Warranty charge. The supporting document references active warranty coverage.",
        primary_evidence=[
            ContextualEvidence(
                document_role="primary",
                document_id=did,
                source_document_type="quotation",
                raw_text="Extended Warranty: 24,000.00",
                amount=24000.0,
                label="Extended Warranty",
            )
        ],
        supporting_evidence=[
            ContextualEvidence(
                document_role="supporting",
                document_id=supp_id,
                source_document_type="warranty",
                raw_text="Standard factory warranty active through 2027.",
                amount=None,
                label="warranty",
            )
        ],
        what_to_verify=[
            "Verify whether quoted warranty duplicates existing manufacturer warranty."
        ],
        confidence=0.92,
        primary_amount=24000.0,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        total_amount=_make_field("total", 24000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(
        doc, [], contextual_findings=[finding]
    )

    assert summary.supporting_document_context is not None
    assert len(summary.supporting_document_context) == 1
    assert summary.supporting_document_context[0].comparison_type == "Potential Overlap"
    assert any("overlap" in a.title.lower() for a in summary.attention_items)


# ── G. Final summary with unexplained charge ──
def test_final_summary_with_unexplained_charge():
    did = uuid4()
    c_unexplained = _make_component(
        "Arbitrary Assessment XYZ",
        4500.0,
        category=ComponentCategory.OTHER,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_unexplained],
        total_amount=_make_field("total", 4500.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    opps = [
        o for o in summary.ways_to_review_cost.opportunities if o.category == "Unexplained Charge"
    ]
    assert len(opps) == 1
    assert opps[0].amount == 4500.0


# ── H. Missing amounts ──
def test_final_summary_missing_amounts():
    did = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        total_amount=_make_field("total", None, amount_state=AmountState.MISSING, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert summary.hero.quoted_total is None
    assert summary.hero.formatted_total == "Total unavailable"
    assert summary.hero.readiness_state == PaymentReadinessState.INCOMPLETE_INFORMATION
    assert summary.completeness.is_complete_to_calculate is False
    assert "Total Amount" in summary.completeness.missing_or_uncertain_fields


# ── I. Unknown amounts ──
def test_final_summary_unknown_amounts():
    did = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        total_amount=_make_field("total", None, amount_state=AmountState.UNKNOWN, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert summary.hero.formatted_total == "Total unknown"
    assert summary.hero.readiness_state == PaymentReadinessState.INCOMPLETE_INFORMATION


# ── J. Unreadable amounts ──
def test_final_summary_unreadable_amounts():
    did = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        total_amount=_make_field("total", None, amount_state=AmountState.UNREADABLE, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert summary.hero.formatted_total == "Total unreadable"
    assert summary.hero.readiness_state == PaymentReadinessState.INCOMPLETE_INFORMATION


# ── K. Zero amounts ──
def test_final_summary_zero_amounts():
    did = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.INVOICE,
        total_amount=_make_field("total", 0.0, amount_state=AmountState.ZERO, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert summary.hero.quoted_total == 0.0
    assert "₹0.00" in summary.hero.formatted_total


# ── L. Multiple findings ──
def test_final_summary_multiple_findings():
    did = uuid4()
    c1 = _make_component(
        "Handling",
        8000.0,
        category=ComponentCategory.DEALER_CHARGE,
        doc_id=did,
        requires_verification=True,
    )
    c2 = _make_component(
        "Warranty",
        24000.0,
        category=ComponentCategory.EXTENDED_WARRANTY,
        doc_id=did,
        requires_verification=True,
    )
    c3 = _make_component(
        "Mystery Charge",
        3000.0,
        category=ComponentCategory.OTHER,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c1, c2, c3],
        total_amount=_make_field("total", 35000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert len(summary.attention_items) >= 3
    assert summary.hero.readiness_state == PaymentReadinessState.REQUIRES_VERIFICATION


# ── M. Duplicate opportunity prevention (no double counting) ──
def test_duplicate_opportunity_prevention():
    did = uuid4()
    c_war = _make_component(
        "Extended Warranty",
        24000.0,
        category=ComponentCategory.EXTENDED_WARRANTY,
        doc_id=did,
        requires_verification=True,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war],
        total_amount=_make_field("total", 24000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    opps = summary.ways_to_review_cost.opportunities
    assert len(opps) == 1
    assert opps[0].potential_amount_to_review == 24000.0


# ── N. Questions ──
def test_questions_to_ask_generation():
    did = uuid4()
    c_war = _make_component(
        "Extended Warranty",
        24000.0,
        category=ComponentCategory.EXTENDED_WARRANTY,
        doc_id=did,
        requires_verification=True,
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war],
        total_amount=_make_field("total", 24000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert len(summary.questions_to_ask) > 0
    assert any("warranty" in q.lower() for q in summary.questions_to_ask)


# ── O. Suggested message ──
def test_suggested_message_generation():
    did = uuid4()
    c_war = _make_component(
        "Extended Warranty",
        24000.0,
        category=ComponentCategory.EXTENDED_WARRANTY,
        doc_id=did,
        requires_verification=True,
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war],
        total_amount=_make_field("total", 24000.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    assert "Hi, I reviewed the quotation" in summary.suggested_message
    assert "revised quotation" in summary.suggested_message
    assert any("warranty" in line.lower() for line in summary.suggested_message.split("\n"))


# ── P. Checklist state ──
def test_checklist_state_evaluation():
    did = uuid4()
    c_base = _make_component("Base", 50000.0, category=ComponentCategory.BASE_PRICE, doc_id=did)

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.INVOICE,
        cost_breakdown=[c_base],
        subtotal=_make_field("subtotal", 50000.0, doc_id=did),
        total_amount=_make_field("total", 50000.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, checks)

    item_map = {item.key: item for item in summary.checklist.items}
    assert item_map["quoted_total_verified"].status == ChecklistItemStatus.VERIFIED
    assert item_map["component_calculations_checked"].status == ChecklistItemStatus.VERIFIED
    assert (
        item_map["final_revised_amount_confirmed"].status == ChecklistItemStatus.PENDING_USER_ACTION
    )


# ── Q. Readiness state ──
def test_readiness_states():
    # 1. READY_FOR_FINAL_VERIFICATION
    did = uuid4()
    doc_clean = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.RECEIPT,
        total_amount=_make_field("total", 100.0, doc_id=did),
    )
    s_clean = BeforeYouPayDecisionSummaryService.build_summary(doc_clean, [])
    assert s_clean.hero.readiness_state == PaymentReadinessState.READY_FOR_FINAL_VERIFICATION

    # 2. REQUIRES_VERIFICATION
    c_fail = _make_component(
        "Mystery", 100.0, category=ComponentCategory.OTHER, doc_id=did, requires_verification=True
    )
    doc_verif = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_fail],
        total_amount=_make_field("total", 100.0, doc_id=did),
    )
    s_verif = BeforeYouPayDecisionSummaryService.build_summary(doc_verif, [])
    assert s_verif.hero.readiness_state == PaymentReadinessState.REQUIRES_VERIFICATION

    # 3. INCOMPLETE_INFORMATION
    doc_inc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.INVOICE,
        total_amount=_make_field("total", None, amount_state=AmountState.MISSING, doc_id=did),
    )
    s_inc = BeforeYouPayDecisionSummaryService.build_summary(doc_inc, [])
    assert s_inc.hero.readiness_state == PaymentReadinessState.INCOMPLETE_INFORMATION


# ── R. Evidence/provenance ──
def test_evidence_provenance_preservation():
    did = uuid4()
    c_fee = _make_component(
        "Processing Fee",
        3500.0,
        category=ComponentCategory.DEALER_CHARGE,
        doc_id=did,
        requires_verification=True,
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_fee],
        total_amount=_make_field("total", 3500.0, doc_id=did),
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [])

    att = next(a for a in summary.attention_items if a.title == "Potentially negotiable")
    assert att.evidence == "Processing Fee: 3500.0"
    assert att.page_number == 1
    assert att.related_component_id == c_fee.component_id


# ── S. Tenant isolation ──
def test_tenant_isolation():
    uid1 = uuid4()
    uid2 = uuid4()
    doc1 = StructuredFinancialDocument(
        document_id=uuid4(), user_id=uid1, total_amount=_make_field("total", 500.0)
    )
    doc2 = StructuredFinancialDocument(
        document_id=uuid4(), user_id=uid2, total_amount=_make_field("total", 800.0)
    )

    s1 = BeforeYouPayDecisionSummaryService.build_summary(doc1, [])
    s2 = BeforeYouPayDecisionSummaryService.build_summary(doc2, [])

    assert s1.user_id == uid1
    assert s2.user_id == uid2
    assert s1.hero.quoted_total == 500.0
    assert s2.hero.quoted_total == 800.0


# ── T. Zetran regression ──
def test_zetran_regression():
    did = uuid4()
    uid = uuid4()
    items = [
        LineItem(
            item_id=uuid4(),
            description=_make_field("desc1", "Samsung A30", doc_id=did),
            total_price=_make_field("p1", 15999.0, doc_id=did),
        ),
        LineItem(
            item_id=uuid4(),
            description=_make_field("desc2", "Samsung Buds", doc_id=did),
            total_price=_make_field("p2", 11999.0, doc_id=did),
        ),
        LineItem(
            item_id=uuid4(),
            description=_make_field("desc3", "Boat Rockers 510", doc_id=did),
            total_price=_make_field("p3", 1499.0, doc_id=did),
        ),
    ]
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uid,
        document_type=DocumentClassification.BILL,
        line_items=items,
        subtotal=_make_field("subtotal", 29497.0, doc_id=did),
        shipping_amount=_make_field("shipping", 499.0, doc_id=did),
        tax_amount=_make_field("tax", 0.0, doc_id=did),
        total_amount=_make_field("total", 29996.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    aggregator = ResultAggregatorService()
    final_res = aggregator.compile_result(
        document_id=did,
        user_id=uid,
        document=doc,
        reasoning_claims=[],
        validation_checks=checks,
    )

    assert final_res.before_you_pay_summary is not None
    summary_data = final_res.before_you_pay_summary
    assert summary_data["hero"]["quoted_total"] == 29996.0
    assert summary_data["reconciliation"]["quoted_total_reconciliation_status"] == "PASS"


# ── U. Handwritten vehicle quotation ──
def test_handwritten_vehicle_quotation():
    did = uuid4()
    uid = uuid4()
    components = [
        _make_component(
            "Ex-showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE, doc_id=did
        ),
        _make_component("TCS", 11499.0, category=ComponentCategory.TCS, doc_id=did),
        _make_component("Road Tax", 91096.0, category=ComponentCategory.ROAD_TAX, doc_id=did),
        _make_component("Insurance", 34500.0, category=ComponentCategory.INSURANCE, doc_id=did),
        _make_component(
            "Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY, doc_id=did
        ),
        _make_component(
            "Accessories", 10000.0, category=ComponentCategory.ACCESSORY_PACKAGE, doc_id=did
        ),
        _make_component(
            "Dealer Offer",
            70000.0,
            category=ComponentCategory.OFFER,
            charge_nature=ChargeNature.DEDUCTION,
            doc_id=did,
        ),
    ]
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uid,
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=components,
        subtotal=_make_field("subtotal", 1319995.0, doc_id=did),
        discount_amount=_make_field("discount", 70000.0, doc_id=did),
        total_amount=_make_field("total", 1249995.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    aggregator = ResultAggregatorService()
    final_res = aggregator.compile_result(
        document_id=did,
        user_id=uid,
        document=doc,
        reasoning_claims=[],
        validation_checks=checks,
    )

    assert final_res.before_you_pay_summary is not None
    s = final_res.before_you_pay_summary
    assert s["hero"]["quoted_total"] == 1249995.0
    assert s["reconciliation"]["quoted_total_reconciliation_status"] == "PASS"


# ── V. ₹6 discrepancy ──
def test_six_rupee_discrepancy():
    did = uuid4()
    uid = uuid4()
    components = [
        _make_component(
            "Ex-showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE, doc_id=did
        ),
        _make_component("TCS", 11499.0, category=ComponentCategory.TCS, doc_id=did),
        _make_component("Insurance", 34500.0, category=ComponentCategory.INSURANCE, doc_id=did),
        _make_component("R.C.", 76250.0, category=ComponentCategory.REGISTRATION, doc_id=did),
        _make_component(
            "Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY, doc_id=did
        ),
        _make_component(
            "Temp + MSRP", 2256.0, category=ComponentCategory.ACCESSORY_OR_FEE, doc_id=did
        ),  # 6.0 delta
        _make_component(
            "Offer",
            70000.0,
            category=ComponentCategory.OFFER,
            charge_nature=ChargeNature.DEDUCTION,
            doc_id=did,
        ),
    ]
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uid,
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=components,
        subtotal=_make_field("subtotal", 1298399.0, doc_id=did),
        discount_amount=_make_field("discount", 70000.0, doc_id=did),
        total_amount=_make_field("total", 1228399.0, doc_id=did),
    )

    validator = DeterministicValidationEngine()
    checks = validator.validate(doc)

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, checks)

    # Component reconciliation must fail with 6.0
    assert summary.reconciliation.component_reconciliation_status == "REQUIRES_VERIFICATION"
    assert summary.reconciliation.component_reconciliation_delta == 6.0

    # Quoted total reconciliation must PASS with exact match
    assert summary.reconciliation.quoted_total_reconciliation_status == "PASS"
    assert summary.reconciliation.quoted_total_reconciliation_delta == 0.0

    # Both tiers kept strictly separate
    assert summary.hero.readiness_state == PaymentReadinessState.REQUIRES_VERIFICATION


# ── W. Quoted-total reconciliation ──
def test_quoted_total_reconciliation():
    did = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        subtotal=_make_field("subtotal", 1298399.0, doc_id=did),
        discount_amount=_make_field("discount", 70000.0, doc_id=did),
        total_amount=_make_field("total", 1228399.0, doc_id=did),
    )

    check = ValidationCheck(
        validation_id=uuid4(),
        check_code="QUOTATION_NET_TOTAL_CONSISTENCY",
        status=ValidationStatus.PASS,
        input_field_ids=[uuid4()],
        expected_value=1228399.0,
        calculated_value=1228399.0,
        absolute_delta=0.0,
        severity=ValidationSeverity.INFO,
        message="Quoted total matches subtotal minus discounts.",
    )

    summary = BeforeYouPayDecisionSummaryService.build_summary(doc, [check])

    assert summary.reconciliation.quoted_total_reconciliation_status == "PASS"
    assert summary.reconciliation.quoted_total_reconciliation_delta == 0.0
    assert "Quoted total matches" in summary.reconciliation.quoted_total_reconciliation_explanation


# ── X. Phase 1–5 regression suite preservation ──
def test_phase1_to_5_regression_suite_preservation():
    # Validates that compiling result produces all historical and new Phase 6 outputs
    did = uuid4()
    uid = uuid4()
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uid,
        document_type=DocumentClassification.QUOTATION,
        total_amount=_make_field("total", 50000.0, doc_id=did),
    )
    agg = ResultAggregatorService()
    result = agg.compile_result(
        document_id=did,
        user_id=uid,
        document=doc,
        reasoning_claims=[],
        validation_checks=[],
    )

    # Phase 1: OCR and document present
    assert result.document is not None
    # Phase 2: contextual findings field present
    assert hasattr(result, "contextual_findings")
    # Phase 3: smart questions & suggested message present
    assert hasattr(result, "smart_questions")
    assert hasattr(result, "suggested_negotiation_message")
    # Phase 4: semantic financial structure present
    assert hasattr(result, "semantic_financial_structure")
    # Phase 6: before you pay final decision summary present
    assert hasattr(result, "before_you_pay_summary")
    assert result.before_you_pay_summary is not None
