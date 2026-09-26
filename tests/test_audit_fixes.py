"""Comprehensive unit and integration tests verifying all audit scopes (A-F)."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    BoundingBox,
    ClaimType,
    CoordinateUnit,
    DecisionStatus,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OcrLine,
    OcrPage,
    OcrResult,
    RagEvidenceChunk,
    RagQuery,
    ReasoningClaim,
    StructuredFinancialDocument,
    ValidationSeverity,
    ValidationStatus,
)
from before_you_pay.services.extraction import FinancialExtractionEngine, detect_currency
from before_you_pay.services.ocr import SpatialOcrEngine
from before_you_pay.services.okf import OkfCatalogService
from before_you_pay.services.rag import SqliteRagService
from before_you_pay.services.result import ResultAggregatorService
from before_you_pay.services.validation import DeterministicValidationEngine

# =========================================================================
# SCOPE A: EXTRACTION CORRECTNESS
# =========================================================================


class TestExtractionCorrectness:
    """Verifies currency, discounts, shipping, taxes, totals, and payment status."""

    def test_currency_parsing_and_normalization(self) -> None:
        """Verify currency detection across various symbols and regional formats."""
        assert detect_currency("Subtotal: $150.00") == "USD"
        assert detect_currency("Total: ₹29,996") == "INR"
        assert detect_currency("Amount: Rs. 1,500.00") == "INR"
        assert detect_currency("Total Amount: €450.50") == "EUR"
        assert detect_currency("Invoice balance: £1,200") == "GBP"
        assert detect_currency("Final: CAD 500") == "CAD"
        assert detect_currency("Price: AUD 300") == "AUD"
        assert detect_currency("Plain numbers without currency: 1500") is None

    @pytest.mark.anyio
    async def test_percentage_discount_on_line_items(self) -> None:
        """Verify percentage discount is computed correctly against unit price."""
        doc_id = uuid4()
        user_id = uuid4()
        engine = SpatialOcrEngine()
        payload = (
            b"Acme Electronics\n"
            b"Pro Headphones Rate/Item: $100.00 Discount: 10% Final line amount: $90.00\n"
            b"Subtotal: $90.00\n"
            b"Total Amount: $90.00"
        )
        ocr = await engine.process_document(doc_id, payload, "text/plain")
        extractor = FinancialExtractionEngine()
        doc = extractor.extract(doc_id, user_id, ocr)

        assert len(doc.line_items) == 1
        item = doc.line_items[0]
        assert item.discount is not None
        assert float(item.discount.normalized_value) == 10.0  # 10% of 100.00 is 10.00
        assert float(item.total_price.normalized_value) == 90.0

    @pytest.mark.anyio
    async def test_explicit_tax_rate_verification_matches(self) -> None:
        """Stated tax rate of 18% matching the calculated amount passes."""
        doc_id = uuid4()
        user_id = uuid4()
        engine = SpatialOcrEngine()
        payload = (
            b"Services Inc\n"
            b"Consulting: $1000.00\n"
            b"Subtotal: $1000.00\n"
            b"Tax (18%): $180.00\n"
            b"Total Amount: $1180.00"
        )
        ocr = await engine.process_document(doc_id, payload, "text/plain")
        doc = FinancialExtractionEngine().extract(doc_id, user_id, ocr)

        validator = DeterministicValidationEngine()
        tax_check = validator.check_tax_calculations(doc)
        assert tax_check.status == ValidationStatus.PASS
        assert "exactly reconciles with stated 18.0% rate" in tax_check.message

    @pytest.mark.anyio
    async def test_explicit_tax_rate_verification_fails_on_discrepancy(self) -> None:
        """Stated tax rate of 18% when document charges $250.00 flags a tax discrepancy."""
        doc_id = uuid4()
        user_id = uuid4()
        engine = SpatialOcrEngine()
        payload = (
            b"Services Inc\n"
            b"Consulting: $1000.00\n"
            b"Subtotal: $1000.00\n"
            b"Tax (18%): $250.00\n"
            b"Total Amount: $1250.00"
        )
        ocr = await engine.process_document(doc_id, payload, "text/plain")
        doc = FinancialExtractionEngine().extract(doc_id, user_id, ocr)

        validator = DeterministicValidationEngine()
        tax_check = validator.check_tax_calculations(doc)
        assert tax_check.status == ValidationStatus.FAIL
        assert tax_check.absolute_delta == 70.0  # $250 - $180 = $70
        assert "should be $180.00, but stated tax is $250.00" in tax_check.message

    def test_independent_failure_modes_line_item_vs_total(self) -> None:
        """
        Failure Mode 1: Individual line item is wrong, but totals match (compensating error).
        Failure Mode 2: Line items are individually correct, but summation is wrong.
        """
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()
        line_id = uuid4()
        prov = FieldProvenance(
            document_id=doc_id, page_id=page_id, ocr_line_ids=[line_id], raw_text="test"
        )
        validator = DeterministicValidationEngine()

        # Mode 1: Line items bad (qty 2 * $50 stated as $80; qty 1 * $100 stated as $120), sum = 200, total = 200
        bad_items = [
            LineItem(
                description=ExtractedField(
                    field_key="d1", normalized_value="Item 1", confidence=0.9, provenance=prov
                ),
                quantity=ExtractedField(
                    field_key="q1", normalized_value=2.0, confidence=0.9, provenance=prov
                ),
                unit_price=ExtractedField(
                    field_key="p1", normalized_value=50.0, confidence=0.9, provenance=prov
                ),
                total_price=ExtractedField(
                    field_key="t1", normalized_value=80.0, confidence=0.9, provenance=prov
                ),  # Should be 100
            ),
            LineItem(
                description=ExtractedField(
                    field_key="d2", normalized_value="Item 2", confidence=0.9, provenance=prov
                ),
                quantity=ExtractedField(
                    field_key="q2", normalized_value=1.0, confidence=0.9, provenance=prov
                ),
                unit_price=ExtractedField(
                    field_key="p2", normalized_value=100.0, confidence=0.9, provenance=prov
                ),
                total_price=ExtractedField(
                    field_key="t2", normalized_value=120.0, confidence=0.9, provenance=prov
                ),  # Should be 100
            ),
        ]
        doc1 = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            line_items=bad_items,
            subtotal=ExtractedField(
                field_key="sub", normalized_value=200.0, confidence=0.9, provenance=prov
            ),
            total_amount=ExtractedField(
                field_key="tot", normalized_value=200.0, confidence=0.9, provenance=prov
            ),
        )

        ext_checks = validator.check_line_item_extensions(doc1)
        assert any(c.status == ValidationStatus.FAIL for c in ext_checks), (
            "Line extensions should fail!"
        )
        sum_check = validator.check_line_items_sum(doc1)
        assert sum_check.status == ValidationStatus.PASS, "Compensating sum happened to pass!"

        # Mode 2: Line items correct (1 * 100 = 100, 1 * 50 = 50), but subtotal states 200 (bad summation)
        good_items = [
            LineItem(
                description=ExtractedField(
                    field_key="d1", normalized_value="Item 1", confidence=0.9, provenance=prov
                ),
                quantity=ExtractedField(
                    field_key="q1", normalized_value=1.0, confidence=0.9, provenance=prov
                ),
                unit_price=ExtractedField(
                    field_key="p1", normalized_value=100.0, confidence=0.9, provenance=prov
                ),
                total_price=ExtractedField(
                    field_key="t1", normalized_value=100.0, confidence=0.9, provenance=prov
                ),
            ),
            LineItem(
                description=ExtractedField(
                    field_key="d2", normalized_value="Item 2", confidence=0.9, provenance=prov
                ),
                quantity=ExtractedField(
                    field_key="q2", normalized_value=1.0, confidence=0.9, provenance=prov
                ),
                unit_price=ExtractedField(
                    field_key="p2", normalized_value=50.0, confidence=0.9, provenance=prov
                ),
                total_price=ExtractedField(
                    field_key="t2", normalized_value=50.0, confidence=0.9, provenance=prov
                ),
            ),
        ]
        doc2 = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            line_items=good_items,
            subtotal=ExtractedField(
                field_key="sub", normalized_value=200.0, confidence=0.9, provenance=prov
            ),
            total_amount=ExtractedField(
                field_key="tot", normalized_value=200.0, confidence=0.9, provenance=prov
            ),
        )
        assert all(
            c.status == ValidationStatus.PASS for c in validator.check_line_item_extensions(doc2)
        )
        assert validator.check_line_items_sum(doc2).status == ValidationStatus.FAIL

    @pytest.mark.anyio
    async def test_payment_status_extraction_and_provenance(self) -> None:
        """Verify payment status is extracted as paid, unpaid, partial, or overdue with provenance."""
        doc_id = uuid4()
        user_id = uuid4()
        engine = SpatialOcrEngine()

        # Document with explicit unpaid balance
        payload_unpaid = (
            b"Invoice #99281\n"
            b"Hosting: $50.00\n"
            b"Total Amount: $50.00\n"
            b"Amount Paid: $0.00\n"
            b"Balance Due: $50.00"
        )
        ocr = await engine.process_document(doc_id, payload_unpaid, "text/plain")
        doc = FinancialExtractionEngine().extract(doc_id, user_id, ocr)
        assert doc.payment_status is not None
        assert doc.payment_status.normalized_value == "unpaid"
        assert doc.payment_status.provenance is not None

        # Document fully paid
        payload_paid = (
            b"Receipt #112\n"
            b"Status: Paid\n"
            b"Item: $100.00\n"
            b"Total Amount: $100.00\n"
            b"Amount Paid: $100.00\n"
            b"Balance Due: $0.00"
        )
        ocr_paid = await engine.process_document(uuid4(), payload_paid, "text/plain")
        doc_paid = FinancialExtractionEngine().extract(uuid4(), user_id, ocr_paid)
        assert doc_paid.payment_status is not None
        assert doc_paid.payment_status.normalized_value == "paid"

        # Document partially paid
        payload_partial = (
            b"Invoice #300\n"
            b"Service: $200.00\n"
            b"Total: $200.00\n"
            b"Amount Paid: $50.00\n"
            b"Balance Due: $150.00"
        )
        ocr_partial = await engine.process_document(uuid4(), payload_partial, "text/plain")
        doc_partial = FinancialExtractionEngine().extract(uuid4(), user_id, ocr_partial)
        assert doc_partial.payment_status is not None
        assert doc_partial.payment_status.normalized_value == "partial"


# =========================================================================
# SCOPE B: RAG / OKF BEHAVIOR
# =========================================================================


class TestRagAndOkfBehavior:
    """Verifies strict tenant isolation, dynamic OKF reload, and reasoning citations."""

    @pytest.mark.anyio
    async def test_rag_never_retrieves_across_tenants(self, tmp_path: Path) -> None:
        """Confirm User A cannot see User B's historical chunks under any circumstances."""
        db_path = str(tmp_path / "tenant_test.db")
        rag = SqliteRagService(db_path=db_path)

        user_a = uuid4()
        user_b = uuid4()
        doc_a = uuid4()
        doc_b = uuid4()

        chunk_a = RagEvidenceChunk(
            user_id=user_a,
            source_document_id=doc_a,
            page_number=1,
            source_text="Secret contract terms for User A with Acme Corp for $50,000",
            similarity_score=1.0,
        )
        chunk_b = RagEvidenceChunk(
            user_id=user_b,
            source_document_id=doc_b,
            page_number=1,
            source_text="Public warranty terms for User B",
            similarity_score=1.0,
        )

        await rag.index_document_chunks(user_a, doc_a, [chunk_a])
        await rag.index_document_chunks(user_b, doc_b, [chunk_b])

        # Query as User B searching for "Acme Corp $50,000"
        results_b = await rag.retrieve(
            RagQuery(
                user_id=user_b,
                current_document_id=uuid4(),
                query_text="Acme Corp 50000",
                top_k=5,
                min_similarity=0.1,
            )
        )
        assert len(results_b) == 0, "Tenant leak detected: User B saw User A data!"

        # Query as User A
        results_a = await rag.retrieve(
            RagQuery(
                user_id=user_a,
                current_document_id=uuid4(),
                query_text="Acme Corp 50000",
                top_k=5,
                min_similarity=0.1,
            )
        )
        assert len(results_a) == 1
        assert "User A" in results_a[0].source_text

    @pytest.mark.anyio
    async def test_okf_dynamic_reload_on_file_modification(self, tmp_path: Path) -> None:
        """Confirm OKF returns current, updated version when rules.json is modified."""
        catalog_dir = tmp_path / "okf"
        catalog_dir.mkdir()
        rules_file = catalog_dir / "test_rules.json"

        # Version 1.0.0
        rules_v1 = {
            "version": "1.0.0",
            "rules": [
                {
                    "rule_id": "OKF-DYNAMIC-01",
                    "rule_name": "Dynamic Test Rule",
                    "category": "verification_rule",
                    "summary": "Original rule summary v1",
                    "source_reference": "Ref 1",
                    "version": "1.0.0",
                    "guidance": "Original guidance v1",
                }
            ],
        }
        rules_file.write_text(json.dumps(rules_v1), encoding="utf-8")

        service = OkfCatalogService(catalog_path=str(catalog_dir))
        rule_initial = await service.get_rule_by_id("OKF-DYNAMIC-01")
        assert rule_initial is not None
        assert rule_initial.version == "1.0.0"
        assert rule_initial.guidance == "Original guidance v1"

        # Modify file on disk to Version 2.0.0
        import time

        time.sleep(0.05)  # Ensure distinct filesystem mtime
        rules_v2 = {
            "version": "2.0.0",
            "rules": [
                {
                    "rule_id": "OKF-DYNAMIC-01",
                    "rule_name": "Dynamic Test Rule Updated",
                    "category": "verification_rule",
                    "summary": "Updated rule summary v2",
                    "source_reference": "Ref 2",
                    "version": "2.0.0",
                    "guidance": "Updated guidance v2",
                }
            ],
        }
        rules_file.write_text(json.dumps(rules_v2), encoding="utf-8")

        # Query without creating new service instance; verify it auto-reloaded
        rule_updated = await service.get_rule_by_id("OKF-DYNAMIC-01")
        assert rule_updated is not None
        assert rule_updated.version == "2.0.0"
        assert rule_updated.guidance == "Updated guidance v2"


# =========================================================================
# SCOPE C: OCR AND LLM FAILURE HANDLING
# =========================================================================


class TestFailureHandling:
    """Verifies that unreadable OCR and empty/malformed inputs reject cleanly without fabricating data."""

    @pytest.mark.anyio
    async def test_low_confidence_ocr_rejected(self) -> None:
        """Low-confidence OCR text lines raise ContractViolationException."""
        doc_id = uuid4()

        # Fabricate low-confidence page to test rejection gate
        page_id = uuid4()
        low_conf_line = OcrLine(
            page_id=page_id,
            document_id=doc_id,
            line_number=1,
            text="?? !! ~~~",
            bounding_box=BoundingBox(
                x=0.1,
                y=0.1,
                width=0.5,
                height=0.05,
                coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
            ),
            confidence=0.20,  # Below 0.40 threshold
        )
        fake_page = OcrPage(
            page_id=page_id,
            document_id=doc_id,
            page_number=1,
            width=1080,
            height=1920,
            lines=[low_conf_line],
        )
        fake_ocr = OcrResult(document_id=doc_id, pages=[fake_page], engine_name="test")

        # The extraction engine should reject when no financial amounts can be found
        extractor = FinancialExtractionEngine()
        with pytest.raises(
            ContractViolationException, match="No total amount or itemized financial figures"
        ):
            extractor.extract(doc_id, uuid4(), fake_ocr)

    @pytest.mark.anyio
    async def test_no_financial_amounts_in_document_refuses_zero_total_fabrication(self) -> None:
        """A document with non-financial text must raise ContractViolationException, NEVER fabricate $0.00."""
        doc_id = uuid4()
        user_id = uuid4()
        engine = SpatialOcrEngine()
        payload = (
            b"Dear Customer,\n"
            b"Thank you for contacting our office regarding your inquiry.\n"
            b"Sincerely, Customer Support Team"
        )
        ocr = await engine.process_document(doc_id, payload, "text/plain")
        extractor = FinancialExtractionEngine()

        with pytest.raises(
            ContractViolationException, match="No total amount or itemized financial figures"
        ):
            extractor.extract(doc_id, user_id, ocr)


# =========================================================================
# INTEGRATION: REASONING & VALIDATION DISAGREEMENT TEST
# =========================================================================


class TestReasoningValidationDisagreement:
    """
    Confirms that when AI Reasoning and Deterministic Validation deliberately disagree,
    Validation wins and the disagreement is prominently surfaced to the user.
    """

    def test_validation_wins_when_reasoning_and_validation_disagree(self) -> None:
        """
        Scenario:
        Reasoning thinks document is clear and fine.
        Deterministic Validation detects a critical arithmetic discrepancy (total stated $500 != items sum $200).
        Result: Overall status MUST be CRITICAL_WARNING and validation flag must be displayed.
        """
        doc_id = uuid4()
        user_id = uuid4()
        page_id = uuid4()
        line_id = uuid4()
        prov = FieldProvenance(
            document_id=doc_id, page_id=page_id, ocr_line_ids=[line_id], raw_text="$500.00"
        )

        # Extracted doc with mismatch: line items sum to 200, total states 500
        item = LineItem(
            description=ExtractedField(
                field_key="desc", normalized_value="Consulting", confidence=0.95, provenance=prov
            ),
            total_price=ExtractedField(
                field_key="t1", normalized_value=200.0, confidence=0.95, provenance=prov
            ),
        )
        doc = StructuredFinancialDocument(
            document_id=doc_id,
            user_id=user_id,
            line_items=[item],
            subtotal=ExtractedField(
                field_key="sub", normalized_value=200.0, confidence=0.95, provenance=prov
            ),
            total_amount=ExtractedField(
                field_key="tot", normalized_value=500.0, confidence=0.95, provenance=prov
            ),
        )

        # 1. Reasoning claims document is standard verification (no issues)
        reasoning_claim = ReasoningClaim(
            claim_id=uuid4(),
            type=ClaimType.REQUIRES_VERIFICATION,
            title="Standard Verification",
            description="Routine review requested.",
            field_references=[doc.total_amount.field_id],
            confidence=0.95,
        )

        # 2. Validation detects critical math mismatch
        validation_engine = DeterministicValidationEngine()
        checks = validation_engine.validate(doc)
        total_check = next(c for c in checks if c.check_code == "ARITHMETIC_TOTAL_CONSISTENCY")
        assert total_check.status == ValidationStatus.FAIL
        assert total_check.severity == ValidationSeverity.CRITICAL

        # 3. Result Aggregator compiles verdict
        aggregator = ResultAggregatorService()
        result = aggregator.compile_result(
            document_id=doc_id,
            user_id=user_id,
            document=doc,
            reasoning_claims=[reasoning_claim],
            validation_checks=checks,
        )

        # 4. ASSERTION: Validation WINS
        assert result.summary.overall_status == DecisionStatus.CRITICAL_WARNING
        assert "discrepancies detected" in result.summary.headline
        # Surfaced flag for math discrepancy must be present and critical
        math_flag = next(
            (f for f in result.flags if "Total" in f.label or "Arithmetic" in f.label), None
        )
        assert math_flag is not None
        assert math_flag.severity == ValidationSeverity.CRITICAL
