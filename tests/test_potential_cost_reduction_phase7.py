"""Tests for Phase 7: Potential Cost Reduction Summary.

Covers:
- Strict non-promising language (no "You can save ₹X")
- 3-tier partitioning: Confirmed Optional, Potentially Optional, Unclear / Needs Confirmation
- Independent range calculation (₹X–₹Y)
- Zero double counting (discounts, offers, bundled charges, subtotal components)
- Exclusion of mandatory statutory charges (Road tax, TCS, GST, Registration, Statutory Insurance)
- Integration into ResultAggregatorService
"""

from uuid import uuid4

import pytest

from before_you_pay.models.analysis import (
    PotentialCostReductionSummary,
)
from before_you_pay.models.document import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    OptionalityStatus,
    StructuredFinancialDocument,
)
from before_you_pay.services.cost_reduction import PotentialCostReductionService
from before_you_pay.services.result import ResultAggregatorService


def _make_component(
    name: str,
    amount: float,
    category: ComponentCategory,
    optionality: OptionalityStatus = OptionalityStatus.UNCLEAR,
    nature: ChargeNature = ChargeNature.CHARGE,
    evidence: str | None = None,
) -> FinancialComponent:
    """Helper to build test FinancialComponent."""
    doc_id = uuid4()
    page_id = uuid4()
    line_id = uuid4()
    return FinancialComponent(
        name=name,
        amount=ExtractedField(
            field_key="amount",
            normalized_value=amount,
            unit_or_currency="INR",
            confidence=0.98,
            provenance=FieldProvenance(
                document_id=doc_id,
                page_id=page_id,
                ocr_line_ids=[line_id],
                bounding_box=BoundingBox(x=0.1, y=0.2, width=0.8, height=0.05),
                raw_text=f"{name}: ₹{amount:,.0f}",
            ),
        ),
        category=category,
        optionality_status=optionality,
        charge_nature=nature,
        charge_or_deduction=nature.value,
        evidence=evidence or f"{name}: ₹{amount:,.0f}",
    )


class TestPotentialCostReductionSummary:
    """Phase 7 specification test suite."""

    def test_forbidden_savings_promise_rejected(self):
        """Must reject any attempt to promise savings ('You can save ₹X')."""
        with pytest.raises(ValueError, match="prohibited savings promise"):
            PotentialCostReductionSummary(
                confirmed_optional_amount=10000.0,
                potential_range_display="You can save ₹10,000",
            )

        with pytest.raises(ValueError, match="prohibited savings promise"):
            PotentialCostReductionSummary(
                review_message="Guaranteed savings on this purchase!",
            )

    def test_three_tier_separation(self):
        """Correctly categorizes charges into Confirmed Optional, Potentially Optional, and Unclear."""
        components = [
            # Tier 1: Confirmed Optional
            _make_component(
                "Optional Floor Mats",
                3500.0,
                ComponentCategory.ACCESSORY,
                optionality=OptionalityStatus.CONFIRMED_OPTIONAL,
                evidence="Quotation explicitly states 'Optional Floor Mats'",
            ),
            # Tier 2: Potentially Optional
            _make_component(
                "Extended Warranty",
                24000.0,
                ComponentCategory.EXTENDED_WARRANTY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            _make_component(
                "Dealer Incidental Charges",
                8500.0,
                ComponentCategory.HANDLING_FEE,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            # Tier 3: Unclear / Needs Confirmation
            _make_component(
                "Documentation & Processing Fee",
                4500.0,
                ComponentCategory.OTHER_FEE,
                optionality=OptionalityStatus.UNCLEAR,
            ),
            # Mandatory / Statutory - MUST BE EXCLUDED
            _make_component(
                "Ex-Showroom Price",
                1149900.0,
                ComponentCategory.BASE_PRICE,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "TCS 1%",
                11499.0,
                ComponentCategory.TCS,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "RTO Registration",
                76250.0,
                ComponentCategory.REGISTRATION,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "Third-party Insurance",
                34500.0,
                ComponentCategory.INSURANCE,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
        ]

        summary = PotentialCostReductionService.calculate_summary(components)

        # Tier 1
        assert summary.confirmed_optional_amount == 3500.0
        assert len(summary.confirmed_optional_items) == 1
        assert summary.confirmed_optional_items[0].name == "Optional Floor Mats"

        # Tier 2
        assert summary.potentially_optional_amount == 32500.0  # 24000 + 8500
        assert len(summary.potentially_optional_items) == 2

        # Tier 3
        assert summary.unclear_confirmation_amount == 4500.0
        assert len(summary.unclear_confirmation_items) == 1

        # Range calculation: min = 3500, max = 3500 + 32500 + 4500 = 40500
        assert summary.min_potential_reduction == 3500.0
        assert summary.max_potential_reduction == 40500.0
        assert summary.potential_range_display == "₹3,500–₹40,500"
        assert summary.is_range_valid is True

        # Non-committal review message
        assert summary.review_message == (
            "You may be able to reduce the quoted amount if the seller confirms these charges are optional or removable."
        )

    def test_no_double_counting_discounts_and_offers(self):
        """Never count discounts, offers, or deductions in potential removable cost."""
        components = [
            _make_component(
                "Extended Warranty",
                24000.0,
                ComponentCategory.EXTENDED_WARRANTY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            _make_component(
                "Dealer Festival Offer",
                50000.0,
                ComponentCategory.OFFER,
                optionality=OptionalityStatus.CONFIRMED_OPTIONAL,
                nature=ChargeNature.DEDUCTION,
            ),
            _make_component(
                "Corporate Discount",
                20000.0,
                ComponentCategory.DISCOUNT,
                optionality=OptionalityStatus.CONFIRMED_OPTIONAL,
                nature=ChargeNature.DEDUCTION,
            ),
        ]

        summary = PotentialCostReductionService.calculate_summary(components)

        # Only the extended warranty charge is evaluated, discounts are completely ignored
        assert summary.confirmed_optional_amount == 0.0
        assert summary.potentially_optional_amount == 24000.0
        assert summary.max_potential_reduction == 24000.0
        assert summary.potential_range_display == "₹0–₹24,000"

    def test_bundled_and_duplicate_deduplication(self):
        """Prevent double counting of bundled subcomponents or identical duplicate entries."""
        components = [
            _make_component(
                "Accessories Kit",
                15000.0,
                ComponentCategory.ACCESSORY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            _make_component(
                "Mud Flaps (bundled in package)",
                1500.0,
                ComponentCategory.ACCESSORY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            # Exact duplicate line in quote
            _make_component(
                "Accessories Kit",
                15000.0,
                ComponentCategory.ACCESSORY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
        ]

        summary = PotentialCostReductionService.calculate_summary(components)

        assert len(summary.potentially_optional_items) == 1
        assert summary.potentially_optional_amount == 15000.0

    def test_fastag_markup_handling(self):
        """FASTag official issuance is capped at ~₹500; only dealer markup over ₹500 is potentially optional."""
        components = [
            _make_component(
                "FASTag",
                1200.0,
                ComponentCategory.FASTAG,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
        ]

        summary = PotentialCostReductionService.calculate_summary(components)

        # Markup is 1200 - 500 = 700
        assert summary.potentially_optional_amount == 700.0
        assert summary.potentially_optional_items[0].amount == 700.0
        assert summary.potentially_optional_items[0].status_label == "Potentially Optional Markup"

    def test_zero_optional_charges_handling(self):
        """When quotation has zero optional charges, range display shows ₹0."""
        components = [
            _make_component(
                "Ex-Showroom Price",
                800000.0,
                ComponentCategory.BASE_PRICE,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
            _make_component(
                "Road Tax / RTO",
                80000.0,
                ComponentCategory.ROAD_TAX,
                optionality=OptionalityStatus.CONFIRMED_MANDATORY,
            ),
        ]

        summary = PotentialCostReductionService.calculate_summary(components)

        assert summary.confirmed_optional_amount == 0.0
        assert summary.potentially_optional_amount == 0.0
        assert summary.unclear_confirmation_amount == 0.0
        assert summary.min_potential_reduction == 0.0
        assert summary.max_potential_reduction == 0.0
        assert summary.potential_range_display == "₹0"
        assert summary.is_range_valid is False

    def test_result_aggregator_integration(self):
        """ResultAggregatorService compiles cost_reduction_summary when document has cost_breakdown."""
        doc_id = uuid4()
        user_id = uuid4()

        comps = [
            _make_component(
                "Extended Warranty",
                24000.0,
                ComponentCategory.EXTENDED_WARRANTY,
                optionality=OptionalityStatus.POTENTIALLY_OPTIONAL,
            ),
            _make_component(
                "Chrome Kit (Optional)",
                12000.0,
                ComponentCategory.ACCESSORY,
                optionality=OptionalityStatus.CONFIRMED_OPTIONAL,
            ),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            total_amount=ExtractedField(
                field_key="total_amount",
                normalized_value=36000.0,
                unit_or_currency="INR",
                confidence=0.99,
                provenance=FieldProvenance(
                    document_id=doc_id,
                    page_id=uuid4(),
                    ocr_line_ids=[uuid4()],
                    bounding_box=BoundingBox(x=0.1, y=0.9, width=0.8, height=0.05),
                    raw_text="Total: ₹36,000",
                ),
            ),
            cost_breakdown=comps,
        )

        aggregator = ResultAggregatorService()
        result = aggregator.compile_result(
            document_id=doc_id,
            user_id=user_id,
            document=doc,
            reasoning_claims=[],
            validation_checks=[],
        )

        assert result.cost_reduction_summary is not None
        assert result.cost_reduction_summary.confirmed_optional_amount == 12000.0
        assert result.cost_reduction_summary.potentially_optional_amount == 24000.0
        assert result.cost_reduction_summary.potential_range_display == "₹12,000–₹36,000"
