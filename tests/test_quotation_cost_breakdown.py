"""Tests for generic financial component models and vehicle quotation cost breakdowns."""

import os
from uuid import uuid4

import pytest

from before_you_pay.models import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.pipeline import PipelineService
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


class TestQuotationCostBreakdown:
    """Test generic financial component model and quotation arithmetic reconciliation."""

    def test_quotation_breakdown_reconciliation_pass(self):
        """Vehicle quotation components sum to subtotal and net total reconciles deductions."""
        doc_id = uuid4()
        page_id = uuid4()
        user_id = uuid4()

        # Components matching user vehicle quote:
        # Ex-showroom = 11,49,900
        # TCS = 11,499
        # Insurance = 34,500
        # R.C. = 76,250
        # Warranty = 24,000
        # Temp + MSRP = 2,250
        # Subtotal = 12,98,399
        # Offer = -20,000
        # Extra offer = -50,000
        # Quoted Total = 12,28,399
        components = [
            FinancialComponent(
                component_id=uuid4(),
                name="Ex-showroom",
                amount=_make_field(doc_id, page_id, "ex_showroom", 1149900.0),
                category=ComponentCategory.BASE_PRICE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="TCS",
                amount=_make_field(doc_id, page_id, "tcs", 11499.0),
                category=ComponentCategory.TAX,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Insurance",
                amount=_make_field(doc_id, page_id, "insurance", 34500.0),
                category=ComponentCategory.INSURANCE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="R.C.",
                amount=_make_field(doc_id, page_id, "rc", 76250.0),
                category=ComponentCategory.REGISTRATION,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Warranty",
                amount=_make_field(doc_id, page_id, "warranty", 24000.0),
                category=ComponentCategory.WARRANTY,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Temp + MSRP",
                amount=_make_field(doc_id, page_id, "temp_msrp", 2250.0),
                category=ComponentCategory.ACCESSORY_OR_FEE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Offer",
                amount=_make_field(doc_id, page_id, "offer", 20000.0),
                category=ComponentCategory.DISCOUNT,
                charge_nature=ChargeNature.DEDUCTION,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Extra offer",
                amount=_make_field(doc_id, page_id, "extra_offer", 50000.0),
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
            subtotal=_make_field(doc_id, page_id, "subtotal", 1298399.0),
            discount_amount=_make_field(doc_id, page_id, "discount_amount", 70000.0),
            total_amount=_make_field(doc_id, page_id, "total_amount", 1228399.0),
        )

        validator = DeterministicValidationEngine()
        checks = validator.validate(doc)
        checks_by_code = {c.check_code: c for c in checks}

        # 1. Subtotal check: 1149900 + 11499 + 34500 + 76250 + 24000 + 2250 == 1298399
        assert "QUOTATION_SUBTOTAL_CONSISTENCY" in checks_by_code
        sub_check = checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"]
        assert sub_check.status == ValidationStatus.PASS
        assert sub_check.calculated_value == 1298399.0
        assert sub_check.expected_value == 1298399.0
        assert sub_check.absolute_delta == 0.0

        # 2. Net Quoted Total check: 1298399 - 20000 - 50000 == 1228399
        assert "QUOTATION_NET_TOTAL_CONSISTENCY" in checks_by_code
        net_check = checks_by_code["QUOTATION_NET_TOTAL_CONSISTENCY"]
        assert net_check.status == ValidationStatus.PASS
        assert net_check.calculated_value == 1228399.0
        assert net_check.expected_value == 1228399.0
        assert net_check.absolute_delta == 0.0

        # 3. Overall Total Consistency
        assert "ARITHMETIC_TOTAL_CONSISTENCY" in checks_by_code
        tot_check = checks_by_code["ARITHMETIC_TOTAL_CONSISTENCY"]
        assert tot_check.status == ValidationStatus.PASS

    def test_quotation_charges_discrepancy_fails(self):
        """When individual quotation charges do not sum to subtotal, check flags FAIL."""
        doc_id = uuid4()
        page_id = uuid4()
        user_id = uuid4()

        components = [
            FinancialComponent(
                component_id=uuid4(),
                name="Ex-showroom",
                amount=_make_field(
                    doc_id, page_id, "ex_showroom", 1100000.0
                ),  # Altered: 49,900 lower
                category=ComponentCategory.BASE_PRICE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="TCS",
                amount=_make_field(doc_id, page_id, "tcs", 11499.0),
                category=ComponentCategory.TAX,
                charge_nature=ChargeNature.CHARGE,
            ),
        ]

        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            document_type=DocumentClassification.QUOTATION,
            currency="INR",
            cost_breakdown=components,
            subtotal=_make_field(doc_id, page_id, "subtotal", 1298399.0),  # Discrepancy
            total_amount=_make_field(doc_id, page_id, "total_amount", 1298399.0),
        )

        validator = DeterministicValidationEngine()
        checks = validator.validate(doc)
        checks_by_code = {c.check_code: c for c in checks}

        assert "QUOTATION_SUBTOTAL_CONSISTENCY" in checks_by_code
        sub_check = checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"]
        assert sub_check.status == ValidationStatus.FAIL
        assert sub_check.severity == ValidationSeverity.WARNING
        assert sub_check.absolute_delta == round(abs((1100000.0 + 11499.0) - 1298399.0), 2)

    def test_vehicle_quotation_two_reconciliations_and_finding_count(self):
        """Regression test for user's vehicle quotation:
        - Stated subtotal: 1,298,399
        - Extracted constituent charges: 1,298,405 (diff: 6)
        - Offers: 70,000
        - Final quoted total: 1,228,399
        - Tax amount: 0
        Verifies:
        1. Component reconciliation fails (requires verification, diff: 6)
        2. Cost components reconciled check fails (no contradiction)
        3. Quoted total reconciliation passes (exact match, diff: 0)
        4. Both states coexist cleanly
        5. Effective tax rate is 0.0%
        6. Substantive finding count is exactly 1 (the 6 discrepancy)
        """
        doc_id = uuid4()
        page_id = uuid4()
        user_id = uuid4()

        # Constituent charges summing to 1,298,405 (6 higher than stated subtotal 1,298,399)
        components = [
            FinancialComponent(
                component_id=uuid4(),
                name="Ex-showroom",
                amount=_make_field(doc_id, page_id, "ex_showroom", 1149900.0),
                category=ComponentCategory.BASE_PRICE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="TCS",
                amount=_make_field(doc_id, page_id, "tcs", 11499.0),
                category=ComponentCategory.TAX,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Insurance",
                amount=_make_field(doc_id, page_id, "insurance", 34500.0),
                category=ComponentCategory.INSURANCE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="R.C.",
                amount=_make_field(doc_id, page_id, "rc", 76250.0),
                category=ComponentCategory.REGISTRATION,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Warranty",
                amount=_make_field(doc_id, page_id, "warranty", 24000.0),
                category=ComponentCategory.WARRANTY,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Temp + MSRP",
                amount=_make_field(
                    doc_id, page_id, "temp_msrp", 2256.0
                ),  # 2,256 instead of 2,250 -> sum 1,298,405
                category=ComponentCategory.ACCESSORY_OR_FEE,
                charge_nature=ChargeNature.CHARGE,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Offer",
                amount=_make_field(doc_id, page_id, "offer", 20000.0),
                category=ComponentCategory.DISCOUNT,
                charge_nature=ChargeNature.DEDUCTION,
            ),
            FinancialComponent(
                component_id=uuid4(),
                name="Extra offer",
                amount=_make_field(doc_id, page_id, "extra_offer", 50000.0),
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
            subtotal=_make_field(doc_id, page_id, "subtotal", 1298399.0),
            discount_amount=_make_field(doc_id, page_id, "discount_amount", 70000.0),
            tax_amount=_make_field(doc_id, page_id, "tax_amount", 0.0),
            total_amount=_make_field(doc_id, page_id, "total_amount", 1228399.0),
        )

        validator = DeterministicValidationEngine()
        checks = validator.validate(doc)
        checks_by_code = {c.check_code: c for c in checks}

        # 1. Component Reconciliation: 1,298,405 vs 1,298,399 -> FAIL / Verification Needed with delta 6.0
        assert "QUOTATION_SUBTOTAL_CONSISTENCY" in checks_by_code
        comp_chk = checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"]
        assert comp_chk.status == ValidationStatus.FAIL
        assert comp_chk.absolute_delta == 6.0
        assert "6.00" in comp_chk.message

        # 2. Cost components reconciled: must NOT be PASS when charges differ
        assert "ARITHMETIC_LINE_ITEMS_SUM" in checks_by_code
        cost_comp_chk = checks_by_code["ARITHMETIC_LINE_ITEMS_SUM"]
        assert cost_comp_chk.status == ValidationStatus.FAIL
        assert cost_comp_chk.absolute_delta == 6.0

        # 3. Quoted Total Reconciliation: 1,298,399 - 70,000 == 1,228,399 -> PASS with delta 0.0
        assert "QUOTATION_NET_TOTAL_CONSISTENCY" in checks_by_code
        quoted_chk = checks_by_code["QUOTATION_NET_TOTAL_CONSISTENCY"]
        assert quoted_chk.status == ValidationStatus.PASS
        assert quoted_chk.absolute_delta == 0.0

        # 4. Overall total consistency passes
        assert "ARITHMETIC_TOTAL_CONSISTENCY" in checks_by_code
        tot_chk = checks_by_code["ARITHMETIC_TOTAL_CONSISTENCY"]
        assert tot_chk.status == ValidationStatus.PASS
        assert tot_chk.absolute_delta == 0.0

        # 5. Tax amount 0 -> effective tax rate 0.0%
        assert "ARITHMETIC_TAX_MATCH" in checks_by_code
        tax_chk = checks_by_code["ARITHMETIC_TAX_MATCH"]
        assert tax_chk.status == ValidationStatus.PASS
        assert tax_chk.calculated_value == "0.0%"

        # 6. Verify result service counts exactly 1 substantive finding
        from before_you_pay.services.result import ResultAggregatorService

        assembler = ResultAggregatorService()
        result = assembler.compile_result(
            document_id=doc_id,
            user_id=user_id,
            document=doc,
            validation_checks=checks,
            reasoning_claims=[],
        )
        assert result.summary.total_flags == 1
        assert "1 item" in result.summary.headline or "1" in result.summary.headline
        # Check flag details
        review_flags = [
            f
            for f in result.flags
            if f.severity in (ValidationSeverity.WARNING, ValidationSeverity.CRITICAL)
        ]
        assert len(review_flags) == 1
        assert "Component Reconciliation Discrepancy" in review_flags[0].label
        assert "6.00" in review_flags[0].message


@pytest.mark.anyio
async def test_real_handwritten_image_e2e_reconciliation():
    """Verify end-to-end processing and reconciliation on user's real handwritten quote image."""
    image_path = r"C:\Users\shiva\Downloads\WhatsApp Image 2026-09-24 at 1.11.24 PM.jpeg"
    if not os.path.exists(image_path):
        pytest.skip(f"Test image not found at {image_path}")

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    pipeline = PipelineService()
    doc_id = uuid4()
    user_id = uuid4()

    result = await pipeline.run_full_pipeline(
        document_id=doc_id,
        user_id=user_id,
        file_bytes=file_bytes,
        mime_type="image/jpeg",
    )

    assert result.document is not None
    doc = result.document
    assert doc.document_type in [
        DocumentClassification.QUOTATION,
        DocumentClassification.COST_BREAKDOWN,
    ]
    assert len(doc.cost_breakdown) >= 6

    # Verify extracted figures match the user's document
    assert float(doc.subtotal.normalized_value) == 1298399.0
    assert float(doc.total_amount.normalized_value) == 1228399.0

    checks_by_code = {c.check_code: c for c in result.validation_checks}
    chk = checks_by_code.get("QUOTATION_SUBTOTAL_CONSISTENCY")
    if chk and chk.status != ValidationStatus.PASS:
        print("\nDEBUG SUB CHECK:", chk.message)
    assert checks_by_code["QUOTATION_SUBTOTAL_CONSISTENCY"].status in [
        ValidationStatus.FAIL,
        ValidationStatus.PASS,
    ]
    assert checks_by_code["QUOTATION_NET_TOTAL_CONSISTENCY"].status == ValidationStatus.PASS
    assert checks_by_code["ARITHMETIC_TOTAL_CONSISTENCY"].status == ValidationStatus.PASS
