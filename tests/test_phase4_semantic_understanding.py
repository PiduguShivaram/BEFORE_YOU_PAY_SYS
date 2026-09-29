"""Phase 4: Semantic Document Understanding Test Suite.

Exhaustively verifies all 32 Phase 4 semantic capabilities:
1. semantic label normalization
2. canonical category mapping
3. charge vs deduction
4. tax/statutory classification
5. registration classification
6. insurance classification
7. warranty classification
8. accessory classification
9. dealer charge classification
10. financing classification
11. discount classification
12. unknown category
13. optionality uncertainty
14. mandatory-status uncertainty
15. missing amount
16. unknown amount
17. unreadable amount
18. zero amount
19. not-applicable amount
20. recurring-charge semantics
21. one-time-charge semantics
22. document-type differences
23. semantic relationships
24. provenance propagation
25. supporting-document context
26. potential overlap
27. amount discrepancy
28. existing Phase 3 question generation
29. existing Phase 3 suggested message
30. Zetran regression
31. handwritten vehicle quotation regression
32. Phase 2 cross-document regression
"""

from uuid import UUID, uuid4

from before_you_pay.models import (
    AmountState,
    BoundingBox,
    ChargeNature,
    ChargeStatus,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    LineItem,
    OptionalityStatus,
    RagEvidenceChunk,
    StructuredFinancialDocument,
    ValidationStatus,
)
from before_you_pay.services.charge_status import ChargeStatusClassifier
from before_you_pay.services.cost_review_questions import CostReviewQuestionsService
from before_you_pay.services.cross_document_comparison import CrossDocumentComparisonService
from before_you_pay.services.financial_taxonomy import (
    classify_component_name,
    get_canonical_category,
    normalize_financial_label,
)
from before_you_pay.services.optionality import OptionalityAnalysisService
from before_you_pay.services.semantic_relationships import (
    SemanticFormulaType,
    SemanticRelationshipService,
    SemanticRelationType,
)
from before_you_pay.services.temporal_semantics import TemporalSemanticsService
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


def _make_component(
    name: str,
    amount_val: float | None = 1000.0,
    amount_state: AmountState = AmountState.PRESENT,
    category: ComponentCategory = ComponentCategory.UNKNOWN,
    charge_nature: ChargeNature = ChargeNature.CHARGE,
    doc_id: UUID | None = None,
) -> FinancialComponent:
    did = doc_id or uuid4()
    prov = _make_prov(did, f"{name}: {amount_val}")
    amt_field = ExtractedField(
        field_id=uuid4(),
        field_key=f"{name.lower().replace(' ', '_')}_amount",
        normalized_value=amount_val,
        confidence=0.95,
        amount_state=amount_state,
        provenance=prov,
    )
    return FinancialComponent(
        component_id=uuid4(),
        name=name,
        raw_text=f"{name}: {amount_val}",
        raw_label=name,
        normalized_label=name,
        amount=amt_field,
        amount_state=amount_state,
        category=category,
        charge_nature=charge_nature,
        source_document_id=did,
        evidence=f"{name}: {amount_val}",
    )


# ── 1. Semantic Label Normalization ──
def test_semantic_label_normalization():
    assert normalize_financial_label("EX-SHOWR00M PRICE") == "Ex-showroom"
    assert normalize_financial_label("Ex Showroom: ₹11,49,900/-") == "Ex-showroom"
    assert normalize_financial_label("INSORANCE PREMIUM") == "Insurance"
    assert normalize_financial_label("INSURANCF") == "Insurance"
    assert normalize_financial_label("R.C. CHARGES") == "Registration"
    assert normalize_financial_label("REGN. FEES") == "Registration"
    assert normalize_financial_label("EXT WARRANTY CHARGES") == "Extended Warranty"
    assert normalize_financial_label("TCS @ 1%") == "TCS"
    assert normalize_financial_label("TEMP + HSRP") == "HSRP"
    assert normalize_financial_label("FAST-TAG") == "FASTag"
    assert normalize_financial_label("BASIC KIT") == "Accessories"
    assert normalize_financial_label("ROAD TAX") == "Road Tax"
    assert normalize_financial_label("EXTRA OFFER") == "Extra Offer"
    assert normalize_financial_label("CASH DISCOUNT") == "Discount"
    assert normalize_financial_label("HYPOTHECATION CHARGES") == "Financing"
    assert normalize_financial_label("BASE PRICE") == "Base Price"


# ── 2. Canonical Category Mapping ──
def test_canonical_category_mapping():
    assert (
        get_canonical_category(ComponentCategory.EX_SHOWROOM_PRICE) == ComponentCategory.BASE_PRICE
    )
    assert get_canonical_category(ComponentCategory.BASE_PRICE) == ComponentCategory.BASE_PRICE
    assert get_canonical_category(ComponentCategory.TCS) == ComponentCategory.TAX_OR_STATUTORY
    assert get_canonical_category(ComponentCategory.GST) == ComponentCategory.TAX_OR_STATUTORY
    assert get_canonical_category(ComponentCategory.ROAD_TAX) == ComponentCategory.TAX_OR_STATUTORY
    assert get_canonical_category(ComponentCategory.TAX) == ComponentCategory.TAX_OR_STATUTORY
    assert get_canonical_category(ComponentCategory.RC) == ComponentCategory.REGISTRATION
    assert get_canonical_category(ComponentCategory.HSRP) == ComponentCategory.REGISTRATION
    assert get_canonical_category(ComponentCategory.REGISTRATION) == ComponentCategory.REGISTRATION
    assert get_canonical_category(ComponentCategory.INSURANCE) == ComponentCategory.INSURANCE
    assert get_canonical_category(ComponentCategory.EXTENDED_WARRANTY) == ComponentCategory.WARRANTY
    assert get_canonical_category(ComponentCategory.WARRANTY) == ComponentCategory.WARRANTY
    assert (
        get_canonical_category(ComponentCategory.ACCESSORY_PACKAGE) == ComponentCategory.ACCESSORY
    )
    assert get_canonical_category(ComponentCategory.ACCESSORY) == ComponentCategory.ACCESSORY
    assert get_canonical_category(ComponentCategory.HANDLING_FEE) == ComponentCategory.DEALER_CHARGE
    assert (
        get_canonical_category(ComponentCategory.LOGISTICS_FEE) == ComponentCategory.DEALER_CHARGE
    )
    assert (
        get_canonical_category(ComponentCategory.PROCESSING_FEE) == ComponentCategory.DEALER_CHARGE
    )
    assert get_canonical_category(ComponentCategory.FASTAG) == ComponentCategory.DEALER_CHARGE
    assert get_canonical_category(ComponentCategory.FINANCING) == ComponentCategory.FINANCING
    assert get_canonical_category(ComponentCategory.OFFER) == ComponentCategory.DISCOUNT
    assert get_canonical_category(ComponentCategory.DISCOUNT) == ComponentCategory.DISCOUNT


# ── 3. Charge vs Deduction ──
def test_charge_vs_deduction():
    cat_off, _, nature_off, _, _ = classify_component_name("Offer ₹50,000")
    assert nature_off == ChargeNature.DEDUCTION
    assert nature_off.is_deduction is True
    assert nature_off.is_additive is False

    cat_disc, _, nature_disc, _, _ = classify_component_name("Special Trade Discount")
    assert nature_disc == ChargeNature.DEDUCTION
    assert nature_disc.is_deduction is True

    cat_chg, _, nature_chg, _, _ = classify_component_name("Handling Fee ₹5,000")
    assert nature_chg == ChargeNature.CHARGE
    assert nature_chg.is_additive is True
    assert nature_chg.is_deduction is False


# ── 4. Tax / Statutory Classification ──
def test_tax_statutory_classification():
    cat, norm, nature, _, _ = classify_component_name("Tax Collected at Source (TCS)")
    assert cat == ComponentCategory.TCS
    assert cat.to_canonical_category() == ComponentCategory.TAX_OR_STATUTORY

    status_assess = ChargeStatusClassifier.classify(
        raw_text="TCS @ 1%",
        category=ComponentCategory.TCS,
        amount=11499.0,
    )
    assert status_assess.status == ChargeStatus.MANDATORY_STATUTORY
    assert status_assess.requires_verification is False


# ── 5. Registration Classification ──
def test_registration_classification():
    cat, _, _, _, _ = classify_component_name("Registration Charges")
    assert cat in (ComponentCategory.REGISTRATION, ComponentCategory.RC)
    assert cat.to_canonical_category() == ComponentCategory.REGISTRATION

    opt_assess = OptionalityAnalysisService.analyze(
        raw_text="Registration Charges ₹45,000",
        category=ComponentCategory.REGISTRATION,
    )
    # Never unconditionally asserts mandatory because dealers routinely bundle markups
    assert opt_assess.status in (OptionalityStatus.UNCLEAR, OptionalityStatus.POTENTIALLY_OPTIONAL)
    assert "verification" in opt_assess.requires_confirmation.lower()


# ── 6. Insurance Classification ──
def test_insurance_classification():
    cat, _, _, _, _ = classify_component_name("Comprehensive Motor Insurance")
    assert cat == ComponentCategory.INSURANCE
    assert cat.to_canonical_category() == ComponentCategory.INSURANCE

    status_assess = ChargeStatusClassifier.classify(
        raw_text="Insurance Premium ₹32,000",
        category=ComponentCategory.INSURANCE,
        amount=32000.0,
    )
    assert status_assess.status == ChargeStatus.POTENTIALLY_OPTIONAL
    assert status_assess.requires_verification is True


# ── 7. Warranty Classification ──
def test_warranty_classification():
    cat_ew, _, _, _, _ = classify_component_name("Extended Warranty 4th & 5th Year")
    assert cat_ew == ComponentCategory.EXTENDED_WARRANTY
    assert cat_ew.to_canonical_category() == ComponentCategory.WARRANTY

    opt_assess = OptionalityAnalysisService.analyze(
        raw_text="Extended Warranty ₹24,000",
        category=ComponentCategory.EXTENDED_WARRANTY,
    )
    assert opt_assess.status == OptionalityStatus.POTENTIALLY_OPTIONAL


# ── 8. Accessory Classification ──
def test_accessory_classification():
    cat, _, _, _, _ = classify_component_name("Basic Accessories Kit")
    assert cat in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE)
    assert cat.to_canonical_category() == ComponentCategory.ACCESSORY

    status_assess = ChargeStatusClassifier.classify(
        raw_text="Essential Kit ₹8,500",
        category=ComponentCategory.ACCESSORY_PACKAGE,
        amount=8500.0,
    )
    assert status_assess.status == ChargeStatus.POTENTIALLY_OPTIONAL


# ── 9. Dealer Charge Classification ──
def test_dealer_charge_classification():
    cat, _, _, _, _ = classify_component_name("Handling & Logistics Fee")
    assert cat in (
        ComponentCategory.HANDLING_FEE,
        ComponentCategory.LOGISTICS_FEE,
        ComponentCategory.DEALER_CHARGE,
    )
    assert cat.to_canonical_category() == ComponentCategory.DEALER_CHARGE

    status_assess = ChargeStatusClassifier.classify(
        raw_text="Incidental Charges ₹7,500",
        category=ComponentCategory.HANDLING_FEE,
        amount=7500.0,
    )
    assert status_assess.status in (ChargeStatus.NEGOTIABLE, ChargeStatus.POTENTIALLY_OPTIONAL)
    assert status_assess.requires_verification is True


# ── 10. Financing Classification ──
def test_financing_classification():
    cat, norm, _, _, _ = classify_component_name("Hypothecation Charges")
    assert cat == ComponentCategory.FINANCING
    assert cat.to_canonical_category() == ComponentCategory.FINANCING

    status_assess = ChargeStatusClassifier.classify(
        raw_text="Loan Processing Fee ₹2,500",
        category=ComponentCategory.FINANCING,
        amount=2500.0,
    )
    assert status_assess.status == ChargeStatus.POTENTIALLY_OPTIONAL
    assert status_assess.requires_verification is True


# ── 11. Discount Classification ──
def test_discount_classification():
    cat, norm, nature, _, _ = classify_component_name("Exchange Offer Bonus")
    assert cat in (ComponentCategory.OFFER, ComponentCategory.DISCOUNT)
    assert cat.to_canonical_category() == ComponentCategory.DISCOUNT
    assert nature.is_deduction is True


# ── 12. Unknown Category ──
def test_unknown_category():
    cat, norm, nature, _, _ = classify_component_name("Xyzzy Foobar Random 9876")
    assert cat in (ComponentCategory.UNCLEAR, ComponentCategory.UNKNOWN, ComponentCategory.OTHER)
    assert cat.to_canonical_category() in (ComponentCategory.OTHER, ComponentCategory.UNKNOWN)
    assert "Xyzzy Foobar Random" in norm


# ── 13. Optionality Uncertainty ──
def test_optionality_uncertainty():
    comp = _make_component(
        "Dealer Service Fee", amount_val=5000.0, category=ComponentCategory.OTHER_FEE
    )
    assert comp.optionality_status in (
        OptionalityStatus.POTENTIALLY_OPTIONAL,
        OptionalityStatus.UNCLEAR,
    )
    assert comp.requires_verification is True


# ── 14. Mandatory Status Uncertainty ──
def test_mandatory_status_uncertainty():
    # Registration charges must not be blindly asserted as mandatory without proof
    comp = _make_component(
        "RTO / Registration", amount_val=50000.0, category=ComponentCategory.REGISTRATION
    )
    payload = comp.to_charge_payload()
    assert payload["charge_status"] != "MANDATORY_NON_NEGOTIABLE"
    assert payload["requires_verification"] is True


# ── 15. Missing Amount ──
def test_missing_amount():
    comp = _make_component("Registration", amount_val=None, amount_state=AmountState.MISSING)
    assert comp.amount_state == AmountState.MISSING
    payload = comp.to_charge_payload()
    assert payload["amount"] is None
    assert payload["amount_state"] == "MISSING"


# ── 16. Unknown Amount ──
def test_unknown_amount():
    comp = _make_component("Warranty", amount_val=None, amount_state=AmountState.UNKNOWN)
    assert comp.amount_state == AmountState.UNKNOWN
    payload = comp.to_charge_payload()
    assert payload["amount"] is None
    assert payload["amount_state"] == "UNKNOWN"


# ── 17. Unreadable Amount ──
def test_unreadable_amount():
    comp = _make_component("Insurance", amount_val=None, amount_state=AmountState.UNREADABLE)
    assert comp.amount_state == AmountState.UNREADABLE
    payload = comp.to_charge_payload()
    assert payload["amount"] is None
    assert payload["amount_state"] == "UNREADABLE"


# ── 18. Zero Amount ──
def test_zero_amount():
    comp = _make_component("Tax", amount_val=0.0, amount_state=AmountState.ZERO)
    assert comp.amount_state == AmountState.ZERO
    payload = comp.to_charge_payload()
    assert payload["amount"] == 0.0
    assert payload["amount_state"] == "ZERO"


# ── 19. Not Applicable Amount ──
def test_not_applicable_amount():
    comp = _make_component("Accessories", amount_val=None, amount_state=AmountState.NOT_APPLICABLE)
    assert comp.amount_state == AmountState.NOT_APPLICABLE
    payload = comp.to_charge_payload()
    assert payload["amount"] is None
    assert payload["amount_state"] == "NOT_APPLICABLE"


# ── 20. Recurring Charge Semantics ──
def test_recurring_charge_semantics():
    info_mo = TemporalSemanticsService.extract_temporal_info("Cloud Storage ₹500/month")
    assert info_mo.is_recurring is True
    assert info_mo.billing_frequency == "monthly"

    info_yr = TemporalSemanticsService.extract_temporal_info(
        "Annual Maintenance Contract: ₹12,000 p.a."
    )
    assert info_yr.is_recurring is True
    assert info_yr.billing_frequency == "yearly"

    info_renew = TemporalSemanticsService.extract_temporal_info("Domain Renewal Fee: ₹899")
    assert info_renew.is_recurring is True
    assert info_renew.billing_frequency == "renewal"


# ── 21. One-time Charge Semantics ──
def test_one_time_charge_semantics():
    info_one = TemporalSemanticsService.extract_temporal_info("One-time Setup Fee: ₹1,500")
    assert info_one.is_recurring is False
    assert info_one.billing_frequency == "one-time"

    # Strict guardrail: Do not infer recurring without explicit evidence
    info_none = TemporalSemanticsService.extract_temporal_info("Car Cover: ₹2,000")
    assert info_none.is_recurring is None
    assert info_none.billing_frequency is None


# ── 22. Document Type Differences ──
def test_document_type_differences():
    for dt in (
        DocumentClassification.INVOICE,
        DocumentClassification.BILL,
        DocumentClassification.QUOTATION,
        DocumentClassification.CONTRACT,
        DocumentClassification.SUBSCRIPTION,
        DocumentClassification.WARRANTY,
        DocumentClassification.RECEIPT,
        DocumentClassification.ESTIMATE,
    ):
        doc = StructuredFinancialDocument(
            document_id=uuid4(),
            user_id=uuid4(),
            document_type=dt,
            total_amount=ExtractedField(
                field_id=uuid4(),
                field_key="total",
                normalized_value=100.0,
                confidence=0.95,
                provenance=_make_prov(uuid4(), "Total: 100"),
            ),
        )
        assert doc.document_type == dt


# ── 23. Semantic Relationships ──
def test_semantic_relationships():
    did = uuid4()
    c_base = _make_component(
        "Base Price", 1000000.0, category=ComponentCategory.BASE_PRICE, doc_id=did
    )
    c_tax = _make_component("GST", 180000.0, category=ComponentCategory.GST, doc_id=did)
    c_ins = _make_component("Insurance", 30000.0, category=ComponentCategory.INSURANCE, doc_id=did)
    c_disc = _make_component(
        "Trade Discount",
        10000.0,
        category=ComponentCategory.DISCOUNT,
        charge_nature=ChargeNature.DEDUCTION,
        doc_id=did,
    )

    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_base, c_tax, c_ins, c_disc],
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total_amount",
            normalized_value=1200000.0,
            confidence=0.95,
            provenance=_make_prov(did, "Net Total: 1200000"),
        ),
    )

    structure = SemanticRelationshipService.analyze_document(doc)
    assert structure.formula_type == SemanticFormulaType.VEHICLE_QUOTATION_BREAKDOWN
    assert structure.is_reconciled is True
    assert structure.calculated_sum == 1200000.0
    assert any(r.canonical_category == ComponentCategory.BASE_PRICE for r in structure.relations)
    assert any(r.relation_type == SemanticRelationType.DEDUCTIVE for r in structure.relations)


# ── 24. Provenance Propagation ──
def test_provenance_propagation():
    did = uuid4()
    prov = _make_prov(did, "Ex-Showroom: ₹11,49,900")
    amt_field = ExtractedField(
        field_id=uuid4(),
        field_key="ex_showroom",
        normalized_value=1149900.0,
        confidence=0.95,
        provenance=prov,
    )
    comp = FinancialComponent(
        component_id=uuid4(),
        name="Ex-showroom",
        amount=amt_field,
        category=ComponentCategory.EX_SHOWROOM_PRICE,
        source_document_id=did,
    )
    payload = comp.to_charge_payload()
    assert payload["evidence"] == "Ex-Showroom: ₹11,49,900"
    assert payload["bounding_box"] is not None
    assert payload["source_document_id"] == str(did)


# ── 25. Supporting Document Context ──
def test_supporting_document_context():
    doc_id = uuid4()
    supp_id = uuid4()
    c_war = _make_component(
        "Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY, doc_id=doc_id
    )

    doc = StructuredFinancialDocument(
        document_id=doc_id,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war],
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total",
            normalized_value=24000.0,
            confidence=0.95,
            provenance=_make_prov(doc_id, "Total: 24000"),
        ),
    )

    chunk = RagEvidenceChunk(
        user_id=doc.user_id,
        source_document_id=supp_id,
        source_document_type=DocumentClassification.WARRANTY,
        source_text="Manufacturer factory warranty includes mechanical coverage for 3 years or 100,000 km.",
        page_number=1,
        similarity_score=0.9,
    )

    service = CrossDocumentComparisonService()
    findings = service.compare(
        document=doc,
        supporting_chunks=[chunk],
        supporting_doc_id=supp_id,
        supporting_doc_type=DocumentClassification.WARRANTY,
    )

    assert len(findings) > 0
    f = findings[0]
    assert len(f.primary_evidence) > 0
    assert len(f.supporting_evidence) > 0
    assert f.primary_evidence[0].document_id == doc_id
    assert f.supporting_evidence[0].document_id == supp_id


# ── 26. Potential Overlap ──
def test_potential_overlap():
    doc_id = uuid4()
    supp_id = uuid4()
    c_war = _make_component(
        "Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY, doc_id=doc_id
    )
    doc = StructuredFinancialDocument(
        document_id=doc_id,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_war],
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total",
            normalized_value=24000.0,
            confidence=0.95,
            provenance=_make_prov(doc_id, "Total: 24000"),
        ),
    )
    chunk = RagEvidenceChunk(
        user_id=doc.user_id,
        source_document_id=supp_id,
        source_document_type=DocumentClassification.WARRANTY,
        source_text="Active standard warranty coverage until Dec 2027.",
        page_number=1,
        similarity_score=0.9,
    )

    service = CrossDocumentComparisonService()
    findings = service.compare(
        document=doc,
        supporting_chunks=[chunk],
        supporting_doc_id=supp_id,
        supporting_doc_type=DocumentClassification.WARRANTY,
    )
    assert len(findings) > 0
    # Must use "potential overlap", NEVER claim "Duplicate warranty"
    assert "overlap" in findings[0].title.lower()
    assert "potential" in findings[0].title.lower()
    assert "duplicate" not in findings[0].title.lower()


# ── 27. Amount Discrepancy ──
def test_amount_discrepancy():
    did = uuid4()
    # Vehicle quotation: calculated breakdown = 1240996, stated total = 1241002 (₹6 delta)
    c1 = _make_component(
        "Ex-showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE, doc_id=did
    )
    c2 = _make_component(
        "Registration", 91096.0, category=ComponentCategory.REGISTRATION, doc_id=did
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c1, c2],
        subtotal=ExtractedField(
            field_id=uuid4(),
            field_key="subtotal",
            normalized_value=1240996.0,
            confidence=0.95,
            provenance=_make_prov(did, "Subtotal: 1240996"),
        ),
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total_amount",
            normalized_value=1241002.0,
            confidence=0.95,
            provenance=_make_prov(did, "Quoted Total: 1241002"),
        ),
    )

    val_engine = DeterministicValidationEngine()
    checks = val_engine.check_quotation_breakdown_consistency(doc)
    net_check = next((c for c in checks if c.check_code == "QUOTATION_NET_TOTAL_CONSISTENCY"), None)
    assert net_check is not None
    assert net_check.status == ValidationStatus.FAIL
    assert net_check.absolute_delta == 6.0


# ── 28. Existing Phase 3 Question Generation ──
def test_phase3_question_generation_preserved():
    did = uuid4()
    c_acc = _make_component(
        "Accessories Package", 15000.0, category=ComponentCategory.ACCESSORY_PACKAGE, doc_id=did
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=[c_acc],
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total",
            normalized_value=15000.0,
            confidence=0.95,
            provenance=_make_prov(did, "Total: 15000"),
        ),
    )

    questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[c_acc], document=doc)
    assert len(questions) > 0
    q = questions[0]
    # Verify strict Phase 3 rules
    assert "potential amount to review" in q.potential_impact.lower()
    assert "you will save" not in q.potential_impact.lower()
    assert "give me a discount" not in q.question.lower()


# ── 29. Existing Phase 3 Suggested Message ──
def test_phase3_suggested_message_preserved():
    did = uuid4()
    c_hand = _make_component(
        "Handling Fee", 5000.0, category=ComponentCategory.HANDLING_FEE, doc_id=did
    )
    questions = CostReviewQuestionsService.generate_questions(cost_breakdown=[c_hand])
    msg = CostReviewQuestionsService.generate_suggested_negotiation_message(questions=questions)
    assert msg is not None
    assert len(msg) > 20
    assert "handling" in msg.lower()
    assert "you will save" not in msg.lower()


# ── 30. Zetran Regression ──
def test_zetran_regression():
    did = uuid4()
    item1 = LineItem(
        item_id=uuid4(),
        description=ExtractedField(
            field_id=uuid4(),
            field_key="desc1",
            normalized_value="Samsung Galaxy A30",
            confidence=0.95,
            provenance=_make_prov(did, "Samsung Galaxy A30"),
        ),
        total_price=ExtractedField(
            field_id=uuid4(),
            field_key="price1",
            normalized_value=17999.0,
            confidence=0.95,
            provenance=_make_prov(did, "17,999.00"),
        ),
    )
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.INVOICE,
        line_items=[item1],
        subtotal=ExtractedField(
            field_id=uuid4(),
            field_key="subtotal",
            normalized_value=17999.0,
            confidence=0.95,
            provenance=_make_prov(did, "Subtotal: 17,999.00"),
        ),
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total",
            normalized_value=17999.0,
            confidence=0.95,
            provenance=_make_prov(did, "Total: 17,999.00"),
        ),
    )
    val_engine = DeterministicValidationEngine()
    check = val_engine.check_line_items_sum(doc)
    assert check.status == ValidationStatus.PASS
    assert check.absolute_delta == 0.0

    rel_service = SemanticRelationshipService()
    structure = rel_service.analyze_document(doc)
    assert structure.formula_type == SemanticFormulaType.COMMERCE_INVOICE
    assert structure.calculated_sum == 17999.0
    assert structure.is_reconciled is True


# ── 31. Handwritten Vehicle Quotation Regression ──
def test_handwritten_vehicle_quotation_regression():
    did = uuid4()
    components = [
        _make_component(
            "Ex-showroom", 1149900.0, category=ComponentCategory.EX_SHOWROOM_PRICE, doc_id=did
        ),
        _make_component("TCS", 11499.0, category=ComponentCategory.TCS, doc_id=did),
        _make_component("Road Tax", 91096.0, category=ComponentCategory.ROAD_TAX, doc_id=did),
        _make_component("Insurance", 32000.0, category=ComponentCategory.INSURANCE, doc_id=did),
        _make_component(
            "Extended Warranty", 24000.0, category=ComponentCategory.EXTENDED_WARRANTY, doc_id=did
        ),
        _make_component(
            "Accessories", 10000.0, category=ComponentCategory.ACCESSORY_PACKAGE, doc_id=did
        ),
        _make_component("FASTag", 500.0, category=ComponentCategory.FASTAG, doc_id=did),
        _make_component(
            "Dealer Offer",
            78000.0,
            category=ComponentCategory.OFFER,
            charge_nature=ChargeNature.DEDUCTION,
            doc_id=did,
        ),
    ]
    doc = StructuredFinancialDocument(
        document_id=did,
        user_id=uuid4(),
        document_type=DocumentClassification.QUOTATION,
        cost_breakdown=components,
        total_amount=ExtractedField(
            field_id=uuid4(),
            field_key="total",
            normalized_value=1240995.0,
            confidence=0.95,
            provenance=_make_prov(did, "Total: 1240995"),
        ),
    )
    structure = SemanticRelationshipService.analyze_document(doc)
    assert structure.formula_type == SemanticFormulaType.VEHICLE_QUOTATION_BREAKDOWN
    assert structure.is_reconciled is True


# ── 32. Phase 2 Cross-Document Regression ──
def test_phase2_cross_document_regression():
    service = CrossDocumentComparisonService()
    assert service is not None
    # Verify no exceptions on empty chunks
    res = service.compare(
        document=StructuredFinancialDocument(
            document_id=uuid4(),
            user_id=uuid4(),
            total_amount=ExtractedField(
                field_id=uuid4(),
                field_key="t",
                normalized_value=100.0,
                confidence=0.9,
                provenance=_make_prov(uuid4(), "100"),
            ),
        ),
        supporting_chunks=[],
        supporting_doc_id=uuid4(),
        supporting_doc_type=DocumentClassification.OTHER,
    )
    assert res == []
