"""Tests for Phase 1A: N-Way Multi-Document Quotation Comparison."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from before_you_pay.main import app
from before_you_pay.models.document import (
    AmountState,
    ChargeNature,
    ComponentCategory,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    StructuredFinancialDocument,
)
from before_you_pay.models.multi_quote_comparison import (
    MultiQuoteComparisonResult,
    QuoteSummary,
)
from before_you_pay.services.multi_quote_comparison import MultiQuoteComparisonService


def _make_field(doc_id, page_id, name, val, state=AmountState.PRESENT) -> ExtractedField:
    return ExtractedField(
        field_key=name,
        normalized_value=val,
        amount_state=state,
        confidence=0.98,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[uuid4()],
            raw_text=f"{name}: {val}",
        ),
    )


def _create_mock_document(
    vendor_name: str,
    total: float,
    components: list[tuple[str, str, float]],
    currency: str = "INR",
) -> StructuredFinancialDocument:
    doc_id = uuid4()
    user_id = uuid4()
    page_id = uuid4()

    fin_comps: list[FinancialComponent] = []
    for comp_name, _cat, amt in components:
        amt_field = _make_field(doc_id, page_id, comp_name, amt)
        fin_comps.append(
            FinancialComponent(
                name=comp_name,
                raw_label=comp_name,
                raw_text=f"{comp_name}: {amt}",
                category=ComponentCategory.HANDLING_FEE
                if "Handling" in comp_name
                else ComponentCategory.BASE_PRICE,
                amount=amt_field,
                charge_nature=ChargeNature.DEDUCTION if amt < 0 else ChargeNature.CHARGE,
                page=1,
            )
        )

    tot_field = _make_field(doc_id, page_id, "total_amount", total)
    vendor_field = _make_field(doc_id, page_id, "vendor_name", vendor_name)

    return StructuredFinancialDocument(
        document_id=doc_id,
        user_id=user_id,
        document_type=DocumentClassification.QUOTATION,
        currency=currency,
        vendor_name=vendor_field,
        total_amount=tot_field,
        cost_breakdown=fin_comps,
    )


class TestPhase1AMultiQuoteComparison:
    """Unit tests for MultiQuoteComparisonService."""

    def test_two_way_quotation_comparison(self):
        service = MultiQuoteComparisonService()
        user_id = uuid4()

        doc_a = _create_mock_document(
            vendor_name="Dealer Alpha",
            total=1150000.0,
            components=[
                ("Ex-Showroom Price", "ex_showroom", 1000000.0),
                ("Road Tax & Registration", "road_tax", 90000.0),
                ("Insurance Zero Dep", "insurance", 45000.0),
                ("Handling Charges", "handling_charges", 8500.0),
                ("Essential Accessories Kit", "accessories", 6500.0),
            ],
        )

        doc_b = _create_mock_document(
            vendor_name="Dealer Beta",
            total=1130000.0,
            components=[
                ("Ex-Showroom Base Price", "ex_showroom", 1000000.0),
                ("RTO Road Tax", "road_tax", 90000.0),
                ("Comprehensive Insurance", "insurance", 40000.0),
                ("Extended Warranty 5 Yr", "extended_warranty", 15000.0),
                ("Discounts", "discounts_offers", -15000.0),
            ],
        )

        result = service.compare([doc_a, doc_b], user_id=user_id)

        assert isinstance(result, MultiQuoteComparisonResult)
        assert len(result.quotes) == 2
        assert result.min_total == 1130000.0
        assert result.max_total == 1150000.0
        assert result.total_delta == 20000.0
        assert result.currency_mismatch is False

        # Verify aligned components
        cat_map = {c.canonical_category: c for c in result.aligned_components}
        assert "ex_showroom" in cat_map
        assert cat_map["ex_showroom"].min_amount == 1000000.0
        assert cat_map["ex_showroom"].max_amount == 1000000.0
        assert cat_map["ex_showroom"].delta_amount == 0.0

        assert "handling_charges" in cat_map
        assert cat_map["handling_charges"].presence_variance is True
        assert cat_map["handling_charges"].max_amount == 8500.0

        # Verify inclusion/exclusion findings
        inc_cats = [f.component_category for f in result.inclusions_and_exclusions]
        assert "handling_charges" in inc_cats
        assert "accessories" in inc_cats
        assert "extended_warranty" in inc_cats

        # Verify suggested questions
        assert len(result.suggested_negotiation_questions) > 0
        assert any("Handling" in q for q in result.suggested_negotiation_questions)

    def test_three_way_quotation_comparison(self):
        service = MultiQuoteComparisonService()
        user_id = uuid4()

        doc_a = _create_mock_document(
            "Dealer A",
            1200000.0,
            [
                ("Ex-Showroom", "ex_showroom", 1000000.0),
                ("Handling Fee", "handling_charges", 10000.0),
            ],
        )
        doc_b = _create_mock_document(
            "Dealer B",
            1180000.0,
            [("Ex-Showroom", "ex_showroom", 1000000.0), ("Accessories", "accessories", 8000.0)],
        )
        doc_c = _create_mock_document(
            "Dealer C",
            1175000.0,
            [("Ex-Showroom", "ex_showroom", 1000000.0), ("Fastag", "fastag_hsrp", 600.0)],
        )

        result = service.compare([doc_a, doc_b, doc_c], user_id=user_id)
        assert len(result.quotes) == 3
        assert result.min_total == 1175000.0
        assert result.max_total == 1200000.0
        assert result.total_delta == 25000.0

    def test_five_way_quotation_comparison_max_limit(self):
        service = MultiQuoteComparisonService()
        user_id = uuid4()

        docs = [
            _create_mock_document(
                f"Dealer {i}", 1000000.0 + i * 5000, [("Ex-Showroom", "ex_showroom", 1000000.0)]
            )
            for i in range(1, 6)
        ]
        result = service.compare(docs, user_id=user_id)
        assert len(result.quotes) == 5
        assert result.min_total == 1005000.0
        assert result.max_total == 1025000.0
        assert result.total_delta == 20000.0

    def test_minimum_documents_boundary_error(self):
        service = MultiQuoteComparisonService()
        doc = _create_mock_document(
            "Dealer Only", 1000000.0, [("Ex-Showroom", "ex_showroom", 1000000.0)]
        )
        with pytest.raises(ValueError, match="At least 2 documents required"):
            service.compare([doc], user_id=uuid4())

    def test_maximum_documents_boundary_error(self):
        service = MultiQuoteComparisonService()
        docs = [
            _create_mock_document(
                f"Dealer {i}", 1000000.0, [("Ex-Showroom", "ex_showroom", 1000000.0)]
            )
            for i in range(1, 7)
        ]
        with pytest.raises(ValueError, match="Maximum of 5 documents supported"):
            service.compare(docs, user_id=uuid4())

    def test_currency_mismatch_detection(self):
        service = MultiQuoteComparisonService()
        doc_inr = _create_mock_document(
            "Dealer INR", 1000000.0, [("Ex-Showroom", "ex_showroom", 1000000.0)], currency="INR"
        )
        doc_usd = _create_mock_document(
            "Dealer USD", 12000.0, [("Ex-Showroom", "ex_showroom", 12000.0)], currency="USD"
        )

        result = service.compare([doc_inr, doc_usd], user_id=uuid4())
        assert result.currency_mismatch is True
        assert "Currency mismatch detected" in result.summary_text

    def test_non_committal_guardrails_on_models(self):
        q1 = QuoteSummary(document_id=uuid4(), vendor_name="A", currency="INR", total_amount=100.0)
        q2 = QuoteSummary(document_id=uuid4(), vendor_name="B", currency="INR", total_amount=200.0)
        with pytest.raises(ValueError, match="Prohibited phrase"):
            MultiQuoteComparisonResult(
                user_id=uuid4(),
                quotes=[q1, q2],
                summary_text="This is definitely a scam by Dealer A, you should not buy from them.",
            )


class TestPhase1ACompareApiEndpoint:
    """Integration tests for POST /api/v1/compare-quotes."""

    def test_compare_quotes_api_multipart(self):
        client = TestClient(app)
        user_id = str(uuid4())

        quote1_content = b"Vehicle Quotation\nDealer A Motors\nEx-Showroom: Rs. 1000000\nRoad Tax: Rs. 80000\nHandling: Rs. 8500\nTotal: Rs. 1088500\n"
        quote2_content = b"Vehicle Quotation\nDealer B Auto\nEx-Showroom: Rs. 1000000\nRoad Tax: Rs. 80000\nInsurance: Rs. 35000\nTotal: Rs. 1115000\n"

        files = [
            ("files", ("quote_a.txt", quote1_content, "text/plain")),
            ("files", ("quote_b.txt", quote2_content, "text/plain")),
        ]
        data = {"user_id": user_id}

        response = client.post("/api/v1/compare-quotes", files=files, data=data)
        assert response.status_code == 200
        payload = response.json()
        assert "quotes" in payload
        assert len(payload["quotes"]) == 2
        assert "aligned_components" in payload
        assert "summary_text" in payload
