"""Tests for Phase 1B: Dealer Response & Counter-Offer Parser."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from before_you_pay.main import app
from before_you_pay.models.dealer_response import (
    DealerActionType,
    DealerResponseAnalysisResult,
)
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
from before_you_pay.services.dealer_response_parser import DealerResponseParserService


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


class TestPhase1BDealerResponseParser:
    """Unit tests for DealerResponseParserService."""

    def test_parse_handling_charge_waiver_and_insurance_reduction(self):
        service = DealerResponseParserService()
        user_id = uuid4()
        doc = _create_mock_document(
            "Dealer Alpha",
            1150000.0,
            [
                ("Ex-Showroom", "base", 1000000.0),
                ("Handling Charges", "handling", 8500.0),
                ("Insurance Zero Dep", "insurance", 45000.0),
                ("Road Tax", "tax", 96500.0),
            ],
        )

        dealer_text = (
            "Dear customer, as discussed, we can waive the handling charges of Rs. 8,500. "
            "Also insurance price reduced to Rs. 35,000. "
            "Your final on-road price will be Rs. 11,31,500."
        )

        result = service.parse(
            dealer_text=dealer_text,
            user_id=user_id,
            original_document=doc,
        )

        assert isinstance(result, DealerResponseAnalysisResult)
        assert len(result.extracted_actions) >= 3

        # Verify handling waiver
        waiver = next(
            a for a in result.extracted_actions if a.action_type == DealerActionType.CHARGE_WAIVED
        )
        assert waiver.reduction_amount == 8500.0

        # Verify insurance reduction: 45,000 -> 35,000 (reduction: 10,000)
        ins = next(
            a for a in result.extracted_actions if a.action_type == DealerActionType.PRICE_REDUCED
        )
        assert ins.revised_amount == 35000.0
        assert ins.reduction_amount == 10000.0

        # Verify mathematical reconciliation: 1,150,000 - 8,500 - 10,000 = 1,131,500
        assert result.total_reduction == 18500.0
        assert result.calculated_new_total == 1131500.0
        assert result.stated_counter_total == 1131500.0
        assert result.math_reconciliation_status == "RECONCILED"
        assert result.reconciliation_difference == 0.0

    def test_parse_discrepancy_between_stated_and_itemized_concessions(self):
        service = DealerResponseParserService()
        user_id = uuid4()

        dealer_text = (
            "We will give an additional discount of Rs. 20,000 on the quote of Rs. 10,00,000. "
            "So your final price is Rs. 9,70,000."
        )

        result = service.parse(
            dealer_text=dealer_text,
            user_id=user_id,
            original_total=1000000.0,
        )

        # Expected new total: 10,00,000 - 20,000 = 9,80,000. Stated is 9,70,000. Discrepancy = 10,000.
        assert result.total_reduction == 20000.0
        assert result.calculated_new_total == 980000.0
        assert result.stated_counter_total == 970000.0
        assert result.math_reconciliation_status == "DISCREPANCY"
        assert result.reconciliation_difference == 10000.0
        assert any("variance" in rec.lower() for rec in result.follow_up_recommendations)

    def test_parse_refusal_non_negotiable_charge(self):
        service = DealerResponseParserService()
        user_id = uuid4()

        dealer_text = (
            "Handling fee is mandatory company policy and we cannot waive handling. "
            "However we can offer an extra discount of Rs. 5,000."
        )

        result = service.parse(dealer_text=dealer_text, user_id=user_id, original_total=1000000.0)

        refusal = next(
            a
            for a in result.extracted_actions
            if a.action_type == DealerActionType.REFUSED_NON_NEGOTIABLE
        )
        assert "Handling" in refusal.target_component_name

        disc = next(
            a for a in result.extracted_actions if a.action_type == DealerActionType.DISCOUNT_ADDED
        )
        assert disc.reduction_amount == 5000.0

    def test_empty_dealer_text_raises_error(self):
        service = DealerResponseParserService()
        with pytest.raises(ValueError, match="cannot be empty"):
            service.parse(dealer_text="   ", user_id=uuid4())

    def test_non_committal_guardrails_on_dealer_response_models(self):
        with pytest.raises(ValueError, match="Prohibited phrase"):
            DealerResponseAnalysisResult(
                user_id=uuid4(),
                dealer_raw_text="We offer 10k discount",
                summary_text="This is a great good deal and you should buy this car immediately.",
            )


class TestPhase1BDealerResponseApiEndpoint:
    """Integration tests for POST /api/v1/parse-dealer-response."""

    def test_parse_dealer_response_api(self):
        client = TestClient(app)
        user_id = str(uuid4())

        data = {
            "dealer_text": "We will waive handling charges of Rs. 8,500 and give extra discount of Rs. 10,000. Final on-road is Rs. 11,31,500.",
            "user_id": user_id,
            "original_total": "1150000",
            "currency": "INR",
        }

        response = client.post("/api/v1/parse-dealer-response", data=data)
        assert response.status_code == 200
        payload = response.json()
        assert "extracted_actions" in payload
        assert len(payload["extracted_actions"]) >= 2
        assert payload["math_reconciliation_status"] == "RECONCILED"
        assert payload["calculated_new_total"] == 1131500.0
        assert "summary_text" in payload
