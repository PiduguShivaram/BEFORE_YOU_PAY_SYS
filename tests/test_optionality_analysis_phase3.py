"""Comprehensive Test Suite for Phase 3: Mandatory / Optional / Potentially Optional Cost Analysis.

Verifies:
1. Allowed statuses: CONFIRMED_MANDATORY, CONFIRMED_OPTIONAL, POTENTIALLY_OPTIONAL, UNCLEAR, NOT_APPLICABLE.
2. Never classify purely from name.
3. Multi-factor evidence across 6 dimensions:
   - Document wording
   - Explicit optional/mandatory language
   - User-provided context
   - Authoritative statutory knowledge
   - Jurisdiction
   - Product/service context
4. Explicit 3-part evidence breakdown:
   - WHAT THE DOCUMENT STATES (document_states)
   - WHAT THE SYSTEM KNOWS (system_knows)
   - WHAT REQUIRES CONFIRMATION (requires_confirmation)
5. Strict adherence to examples:
   - "Extended Warranty — ₹24,000" -> Potentially optional ("Verify whether this can be removed.")
   - "Optional accessories" -> Confirmed optional
   - "Mandatory registration fee" -> Confirmed mandatory ("Document states mandatory")
   - Bare "Registration — ₹76,250" without evidence -> Unclear ("Status: Requires verification")
   - "XYZ ₹5,000" -> Unclear ("Optionality: Unclear")
   - Deductions / Aggregates -> Not applicable
6. Never converts uncertainty into certainty.
"""

from uuid import uuid4

from before_you_pay.models.document import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OcrLine,
    OcrPage,
    OcrResult,
    OptionalityStatus,
)
from before_you_pay.services.extraction import FinancialExtractionEngine
from before_you_pay.services.optionality import OptionalityAnalysisService


def _make_field(key: str, val: float, text: str) -> ExtractedField:
    doc_id = uuid4()
    page_id = uuid4()
    line_id = uuid4()
    return ExtractedField(
        field_key=key,
        normalized_value=val,
        unit_or_currency="INR",
        confidence=0.98,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[line_id],
            bounding_box=BoundingBox(x=0.1, y=0.2, width=0.8, height=0.05),
            raw_text=text,
        ),
    )


def _make_line(text: str, doc_id=None, page_id=None, y=0.1) -> OcrLine:
    return OcrLine(
        document_id=doc_id or uuid4(),
        page_id=page_id or uuid4(),
        line_number=1,
        text=text,
        bounding_box=BoundingBox(x=0.1, y=y, width=0.8, height=0.04),
        confidence=0.95,
    )


class TestPromptExamplesAndExactRules:
    """Verifies all direct examples mandated in the Phase 3 specification."""

    def test_extended_warranty_does_not_automatically_say_optional(self):
        """Prompt requirement:
        "Extended Warranty — ₹24,000"
        Do NOT automatically say: "Optional"
        Instead:
        "Extended warranty"
        "Potentially optional"
        "Verify whether this can be removed."
        """
        amt = _make_field("extended_warranty", 24000.0, "Extended Warranty: ₹24,000")
        comp = FinancialComponent(
            name="Extended Warranty — ₹24,000",
            amount=amt,
        )

        assert comp.normalized_label in ("Extended warranty", "Extended Warranty")
        assert comp.optionality_status == OptionalityStatus.POTENTIALLY_OPTIONAL
        assert comp.optionality_display == "Potentially optional"
        assert "Verify whether this can be removed" in comp.requires_confirmation
        assert comp.document_states is not None
        assert comp.system_knows is not None
        assert "supplemental coverage contract" in comp.system_knows

    def test_explicit_optional_accessories_confirmed_optional(self):
        """Prompt requirement:
        If the quotation explicitly says:
        "Optional accessories"
        then:
        "Accessories"
        "Confirmed optional"
        """
        amt = _make_field("accessories", 15500.0, "Optional accessories ₹15,500")
        comp = FinancialComponent(
            name="Optional accessories",
            amount=amt,
        )

        assert comp.normalized_label == "Accessories"
        assert comp.optionality_status == OptionalityStatus.CONFIRMED_OPTIONAL
        assert comp.optionality_display == "Confirmed optional"
        assert "explicitly designates this charge as optional" in comp.document_states
        assert "Can be declined or removed" in comp.requires_confirmation

    def test_explicit_mandatory_registration_fee_confirmed_mandatory(self):
        """Prompt requirement:
        If the quotation says:
        "Mandatory registration fee"
        then:
        "Registration"
        "Document states mandatory"
        """
        amt = _make_field("registration", 65000.0, "Mandatory registration fee ₹65,000")
        comp = FinancialComponent(
            name="Mandatory registration fee",
            amount=amt,
        )

        assert comp.normalized_label == "Registration"
        assert comp.optionality_status == OptionalityStatus.CONFIRMED_MANDATORY
        assert comp.optionality_display == "Document states mandatory"
        assert "Document explicitly states mandatory fee" in comp.document_states
        assert comp.requires_confirmation is not None

    def test_bare_registration_requires_verification(self):
        """Prompt requirement:
        If the quotation says:
        "Registration — ₹76,250"
        and there is NO evidence indicating mandatory/optional in document:
        "Registration"
        "Status: Requires verification"
        """
        amt = _make_field("registration", 76250.0, "Registration: ₹76,250")
        comp = FinancialComponent(
            name="Registration — ₹76,250",
            amount=amt,
        )

        assert comp.normalized_label == "Registration"
        assert comp.optionality_status == OptionalityStatus.UNCLEAR
        assert comp.optionality_display == "Status: Requires verification"
        assert "Status: Requires verification" in comp.requires_confirmation
        assert "bundle unauthorized documentation fees" in comp.system_knows

    def test_unidentified_xyz_charge_is_unclear(self):
        """Prompt requirement:
        "XYZ ₹5,000"
        If evidence is insufficient:
        "Optionality: Unclear"
        or: "Potentially optional — verify with seller"
        """
        amt = _make_field("xyz", 5000.0, "XYZ ₹5,000")
        comp = FinancialComponent(
            name="XYZ 5000",
            amount=amt,
        )

        assert comp.category == ComponentCategory.UNCLEAR
        assert comp.optionality_status == OptionalityStatus.UNCLEAR
        assert comp.optionality_display == "Optionality: Unclear"
        assert "Optionality: Unclear" in comp.requires_confirmation


class TestExplicitThreePartEvidenceBreakdown:
    """Verifies that every component provides the 3 required dimensions:
    - WHAT THE DOCUMENT STATES
    - WHAT THE SYSTEM KNOWS
    - WHAT REQUIRES CONFIRMATION
    """

    def test_three_dimensions_populated_on_all_components(self):
        cases = [
            ("Ex-Showroom: ₹11,49,900", 1149900.0),
            ("TCS @ 1%: ₹11,499", 11499.0),
            ("Handling Charges: ₹8,500", 8500.0),
            ("Motor Insurance: ₹34,500", 34500.0),
            ("FASTag: ₹1,000", 1000.0),
            ("Special Offer: -₹15,000", 15000.0),
        ]

        for text, amt_val in cases:
            amt = _make_field("fee", amt_val, text)
            comp = FinancialComponent(name=text, amount=amt)

            # 1. WHAT THE DOCUMENT STATES
            assert comp.document_states is not None
            assert len(comp.document_states) > 5

            # 2. WHAT THE SYSTEM KNOWS
            assert comp.system_knows is not None
            assert len(comp.system_knows) > 5

            # 3. WHAT REQUIRES CONFIRMATION
            assert comp.requires_confirmation is not None
            assert len(comp.requires_confirmation) > 5

            # Standardized payload contains all 3 dimensions
            payload = comp.to_charge_payload()
            assert "document_states" in payload
            assert "system_knows" in payload
            assert "requires_confirmation" in payload
            assert "optionality_display" in payload

    def test_handling_and_logistics_fees_are_potentially_optional_with_legal_citation(self):
        """Dealers frequently mark handling fees as mandatory, but legal precedents declare them illegal."""
        amt = _make_field("handling", 8500.0, "Handling / Logistics Fee: ₹8,500")
        comp = FinancialComponent(
            name="Handling / Logistics Fee",
            amount=amt,
        )

        assert comp.category in (ComponentCategory.HANDLING_FEE, ComponentCategory.LOGISTICS_FEE)
        assert comp.optionality_status == OptionalityStatus.POTENTIALLY_OPTIONAL
        assert "potentially optional" in comp.optionality_display.lower()
        assert "High Courts" in comp.system_knows or "Transport" in comp.system_knows
        assert "Contest with dealer" in comp.requires_confirmation

    def test_insurance_system_knows_external_purchase_right(self):
        """Insurance is legally mandatory for vehicle operation, but dealer policy bundling is optional."""
        amt = _make_field("insurance", 34500.0, "Comprehensive Insurance: ₹34,500")
        comp = FinancialComponent(
            name="Comprehensive Insurance",
            amount=amt,
        )

        assert comp.category == ComponentCategory.INSURANCE
        assert comp.optionality_status == OptionalityStatus.POTENTIALLY_OPTIONAL
        assert "Motor Vehicles Act" in comp.system_knows
        assert "IRDAI" in comp.system_knows or "independently" in comp.system_knows
        assert "price-matched or purchased independently" in comp.requires_confirmation

    def test_statutory_taxes_confirmed_mandatory(self):
        """TCS under Section 206C is confirmed mandatory."""
        amt = _make_field("tcs", 11499.0, "TCS @ 1%: ₹11,499")
        comp = FinancialComponent(
            name="TCS @ 1%",
            amount=amt,
        )

        assert comp.category == ComponentCategory.TCS
        assert comp.optionality_status == OptionalityStatus.CONFIRMED_MANDATORY
        assert comp.optionality_display == "Confirmed mandatory"
        assert "Section 206C" in comp.system_knows
        assert "Form 26AS" in comp.requires_confirmation

    def test_deductions_and_totals_are_not_applicable(self):
        """Deductions, discounts, and totals are arithmetic figures, not optional add-ons."""
        amt = _make_field("offer", 15000.0, "Dealer Offer: -15,000")
        comp = FinancialComponent(
            name="Dealer Offer",
            amount=amt,
            charge_nature=ChargeNature.DEDUCTION,
        )

        assert comp.optionality_status == OptionalityStatus.NOT_APPLICABLE
        assert comp.optionality_display == "Not applicable"
        assert "No optionality confirmation required" in comp.requires_confirmation


class TestExtractionEngineE2EOptionality:
    """Verifies that the extraction engine produces complete Phase 3 optionality metadata from OCR lines."""

    def test_vehicle_quotation_lines_produce_full_optionality_profiles(self):
        svc = FinancialExtractionEngine()
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()

        lines = [
            _make_line("VEHICLE ESTIMATE", doc_id=doc_id, page_id=page_id, y=0.05),
            _make_line("Ex-Showroom Price: ₹11,49,900", doc_id=doc_id, page_id=page_id, y=0.10),
            _make_line("TCS (1%): ₹11,499", doc_id=doc_id, page_id=page_id, y=0.15),
            _make_line("Road Tax / Life Tax: ₹76,250", doc_id=doc_id, page_id=page_id, y=0.20),
            _make_line("Registration — ₹5,000", doc_id=doc_id, page_id=page_id, y=0.25),
            _make_line("Optional Accessories Kit: ₹15,500", doc_id=doc_id, page_id=page_id, y=0.30),
            _make_line("Extended Warranty (5 Yr): ₹24,000", doc_id=doc_id, page_id=page_id, y=0.35),
            _make_line("Handling & Depo Charges: ₹8,500", doc_id=doc_id, page_id=page_id, y=0.40),
            _make_line("Dealer Special Discount: -₹15,000", doc_id=doc_id, page_id=page_id, y=0.45),
            _make_line("Total Quoted Price: ₹12,75,649", doc_id=doc_id, page_id=page_id, y=0.50),
        ]

        ocr_res = OcrResult(
            document_id=doc_id,
            engine_name="test_engine",
            pages=[
                OcrPage(
                    document_id=doc_id,
                    page_number=1,
                    page_id=page_id,
                    width=1200,
                    height=1600,
                    lines=lines,
                )
            ],
        )

        doc = svc.extract(
            document_id=doc_id,
            user_id=user_id,
            ocr_result=ocr_res,
            document_type_hint=DocumentClassification.QUOTATION,
        )

        assert len(doc.cost_breakdown) >= 6

        # 1. Ex-showroom -> Confirmed mandatory
        ex_show = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.EX_SHOWROOM_PRICE)
        assert ex_show.optionality_status == OptionalityStatus.CONFIRMED_MANDATORY
        assert ex_show.optionality_display == "Confirmed mandatory"

        # 2. TCS -> Confirmed mandatory
        tcs = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.TCS)
        assert tcs.optionality_status == OptionalityStatus.CONFIRMED_MANDATORY

        # 3. Optional accessories -> Confirmed optional (because line explicitly stated "Optional")
        acc = next(c for c in doc.cost_breakdown if c.category in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE))
        assert acc.optionality_status == OptionalityStatus.CONFIRMED_OPTIONAL
        assert acc.optionality_display == "Confirmed optional"

        # 4. Extended Warranty -> Potentially optional ("Verify whether this can be removed.")
        ew = next(c for c in doc.cost_breakdown if c.category == ComponentCategory.EXTENDED_WARRANTY)
        assert ew.optionality_status == OptionalityStatus.POTENTIALLY_OPTIONAL
        assert ew.optionality_display == "Potentially optional"
        assert "Verify whether this can be removed" in ew.requires_confirmation

        # 5. Handling charges -> Potentially optional ("Contest with dealer")
        hdl = next(c for c in doc.cost_breakdown if c.category in (ComponentCategory.HANDLING_FEE, ComponentCategory.LOGISTICS_FEE))
        assert hdl.optionality_status == OptionalityStatus.POTENTIALLY_OPTIONAL
        assert "Contest with dealer" in hdl.requires_confirmation

        # 6. Bare registration without mandatory label -> Requires verification
        reg = next(c for c in doc.cost_breakdown if c.category in (ComponentCategory.REGISTRATION, ComponentCategory.RC))
        assert reg.optionality_status == OptionalityStatus.UNCLEAR
        assert "Requires verification" in reg.optionality_display


class TestNeverConvertsUncertaintyIntoCertainty:
    """Verifies the core safety requirement that ambiguity is never suppressed or assumed."""

    def test_ambiguous_line_does_not_assume_mandatory(self):
        amt = _make_field("random_fee", 3500.0, "Documentation & Misc 3500")
        comp = FinancialComponent(
            name="Documentation & Misc 3500",
            amount=amt,
        )

        assert comp.optionality_status in (OptionalityStatus.POTENTIALLY_OPTIONAL, OptionalityStatus.UNCLEAR)
        assert comp.optionality_status != OptionalityStatus.CONFIRMED_MANDATORY
        assert any(term in comp.requires_confirmation.lower() for term in ("verify", "clarify", "contest", "removal", "seller"))

    def test_manual_explicit_override_is_honored(self):
        """User-provided explicit context is respected without hallucinating extra requirements."""
        assessment = OptionalityAnalysisService.analyze(
            raw_text="Customer Selected Sunroof Addon",
            category=ComponentCategory.ACCESSORY,
            explicit_status=OptionalityStatus.CONFIRMED_OPTIONAL,
        )

        assert assessment.status == OptionalityStatus.CONFIRMED_OPTIONAL
        assert assessment.display_label == "Confirmed optional"
