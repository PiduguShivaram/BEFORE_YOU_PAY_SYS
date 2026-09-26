"""Deterministic financial validation engine executing pure Python arithmetic checks."""

from datetime import date
from uuid import uuid4

from before_you_pay.core.dates import normalize_date_to_iso
from before_you_pay.models import (
    ChargeNature,
    ComponentCategory,
    DocumentClassification,
    StructuredFinancialDocument,
    ValidationCheck,
    ValidationSeverity,
    ValidationStatus,
)


def _get_currency_symbol(currency: str | None) -> str:
    if not currency:
        return ""
    c = currency.upper().strip()
    if c in ["INR", "₹"]:
        return "₹"
    if c in ["USD", "$"]:
        return "$"
    if c in ["EUR", "€"]:
        return "€"
    if c in ["GBP", "£"]:
        return "£"
    return f"{currency} "


class DeterministicValidationEngine:
    """Executes transparent, zero-hallucination arithmetic and logical validation checks."""

    def validate(
        self,
        document: StructuredFinancialDocument,
    ) -> list[ValidationCheck]:
        """Execute complete suite of deterministic financial integrity checks."""
        checks: list[ValidationCheck] = []
        checks.append(self.check_financial_content(document))
        if document.cost_breakdown or document.document_type in (
            DocumentClassification.QUOTATION,
            DocumentClassification.COST_BREAKDOWN,
        ):
            checks.extend(self.check_quotation_breakdown_consistency(document))
        checks.extend(self.check_line_item_extensions(document))
        checks.append(self.check_line_items_sum(document))
        checks.append(self.check_total_consistency(document))
        checks.append(self.check_tax_calculations(document))
        checks.append(self.check_date_consistency(document))
        checks.append(self.check_payment_status(document))
        return checks

    def run_all_validations(
        self,
        document: StructuredFinancialDocument,
    ) -> list[ValidationCheck]:
        return self.validate(document)

    def check_arithmetic_sums(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Alias for check_line_items_sum."""
        return self.check_line_items_sum(document)

    def check_financial_content(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify that document contains discernible financial commitments or line items."""
        total_val = float(document.total_amount.normalized_value) if document.total_amount else 0.0
        subtotal_val = float(document.subtotal.normalized_value) if document.subtotal else 0.0
        has_items = len(document.line_items) > 0
        has_clauses = len(document.clauses_and_notes) > 0
        has_fees = len(document.fees) > 0

        input_ids = [document.total_amount.field_id] if document.total_amount else []

        if total_val <= 0.0 and subtotal_val <= 0.0 and not has_items and not has_fees:
            if has_clauses and document.document_type in [
                DocumentClassification.CONTRACT,
                DocumentClassification.WARRANTY,
            ]:
                return ValidationCheck(
                    validation_id=uuid4(),
                    check_code="FINANCIAL_CONTENT_VERIFICATION",
                    status=ValidationStatus.PASS,
                    input_field_ids=input_ids,
                    severity=ValidationSeverity.INFO,
                    message="Non-monetary legal or warranty document verified without financial payable obligations.",
                )
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR",
                status=ValidationStatus.FAIL,
                input_field_ids=input_ids,
                expected_value="Identifiable financial commitments or line items",
                calculated_value="0.00",
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message="No financial amounts, itemized line items, or monetary commitments detected after reliable OCR.",
            )

        return ValidationCheck(
            validation_id=uuid4(),
            check_code="FINANCIAL_CONTENT_VERIFICATION",
            status=ValidationStatus.PASS,
            input_field_ids=input_ids,
            calculated_value=total_val,
            severity=ValidationSeverity.INFO,
            message="Document contains identifiable financial figures and commitments.",
        )

    def check_line_item_extensions(
        self,
        document: StructuredFinancialDocument,
    ) -> list[ValidationCheck]:
        """Verify for each line item that quantity * unit_price == total_price."""
        results: list[ValidationCheck] = []
        curr_sym = _get_currency_symbol(document.currency)

        for item in document.line_items:
            input_ids = [item.description.field_id, item.total_price.field_id]
            if item.quantity:
                input_ids.append(item.quantity.field_id)
            if item.unit_price:
                input_ids.append(item.unit_price.field_id)

            if item.quantity is None or item.unit_price is None:
                continue

            qty = float(item.quantity.normalized_value)
            price = float(item.unit_price.normalized_value)
            stated_total = float(item.total_price.normalized_value)
            expected_total = round(qty * price, 2)
            delta = round(abs(expected_total - stated_total), 2)

            item_disc = float(item.discount.normalized_value) if item.discount else 0.0
            gross_total = round(qty * price, 2)
            net_total = round(gross_total - item_disc, 2)

            is_match = False
            expected_total = gross_total

            if abs(gross_total - stated_total) <= 0.02:
                is_match = True
                expected_total = gross_total
                delta = 0.0
            elif item_disc > 0.0 and abs(net_total - stated_total) <= 0.02:
                is_match = True
                expected_total = net_total
                delta = 0.0
            else:
                is_match = False
                expected_total = net_total if item_disc > 0.0 else gross_total
                delta = round(abs(expected_total - stated_total), 2)

            if is_match:
                results.append(
                    ValidationCheck(
                        validation_id=uuid4(),
                        check_code="LINE_ITEM_EXTENSION_MATCH",
                        status=ValidationStatus.PASS,
                        input_field_ids=input_ids,
                        expected_value=stated_total,
                        calculated_value=expected_total,
                        absolute_delta=delta,
                        severity=ValidationSeverity.INFO,
                        message=(
                            f"Line item '{item.description.normalized_value}' arithmetic extends correctly: "
                            f"{qty} * {curr_sym}{price:,.2f} == {curr_sym}{stated_total:,.2f}."
                        ),
                    )
                )
            else:
                results.append(
                    ValidationCheck(
                        validation_id=uuid4(),
                        check_code="LINE_ITEM_EXTENSION_MATCH",
                        status=ValidationStatus.FAIL,
                        input_field_ids=input_ids,
                        expected_value=stated_total,
                        calculated_value=expected_total,
                        absolute_delta=delta,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Line item '{item.description.normalized_value}' arithmetic discrepancy: "
                            f"Rate {curr_sym}{price:,.2f} * {qty}"
                            + (f" - discount {curr_sym}{item_disc:,.2f}" if item_disc > 0 else "")
                            + f" yields expected {curr_sym}{expected_total:,.2f}, but stated final amount is {curr_sym}{stated_total:,.2f} "
                            f"(difference: {curr_sym}{delta:,.2f})."
                        ),
                    )
                )
        return results

    def check_quotation_breakdown_consistency(
        self,
        document: StructuredFinancialDocument,
    ) -> list[ValidationCheck]:
        """Verify internal consistency of quotation charges, subtotal, offers/deductions, and net total."""
        results: list[ValidationCheck] = []
        curr_sym = _get_currency_symbol(document.currency)

        if not document.cost_breakdown:
            return results

        charges = [c for c in document.cost_breakdown if c.charge_nature == ChargeNature.CHARGE]
        deductions = [c for c in document.cost_breakdown if c.charge_nature == ChargeNature.DEDUCTION]

        sum_charges = round(sum(float(c.amount.normalized_value) for c in charges), 2)
        sum_deductions = round(sum(float(c.amount.normalized_value) for c in deductions), 2)

        # Check 1: Charges Sum == Stated Subtotal (or Total Before Offers)
        if document.subtotal:
            stated_sub = round(float(document.subtotal.normalized_value), 2)
            input_ids = [c.amount.field_id for c in charges] + [document.subtotal.field_id]
            delta_sub = round(abs(sum_charges - stated_sub), 2)

            if delta_sub <= 0.02:
                results.append(
                    ValidationCheck(
                        validation_id=uuid4(),
                        check_code="QUOTATION_SUBTOTAL_CONSISTENCY",
                        status=ValidationStatus.PASS,
                        input_field_ids=input_ids,
                        expected_value=stated_sub,
                        calculated_value=sum_charges,
                        absolute_delta=delta_sub,
                        severity=ValidationSeverity.INFO,
                        message=(
                            f"Sum of quotation cost components ({curr_sym}{sum_charges:,.2f}) matches stated "
                            f"subtotal / total before offers ({curr_sym}{stated_sub:,.2f})."
                        ),
                    )
                )
            else:
                results.append(
                    ValidationCheck(
                        validation_id=uuid4(),
                        check_code="QUOTATION_SUBTOTAL_CONSISTENCY",
                        status=ValidationStatus.FAIL,
                        input_field_ids=input_ids,
                        expected_value=stated_sub,
                        calculated_value=sum_charges,
                        absolute_delta=delta_sub,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Component reconciliation discrepancy: Stated subtotal is {curr_sym}{stated_sub:,.2f}, "
                            f"but listed components sum to {curr_sym}{sum_charges:,.2f} "
                            f"(difference: {curr_sym}{delta_sub:,.2f}). Ask the dealer to clarify."
                        ),
                    )
                )

        # Check 2: Net Quoted Total == Subtotal - Deductions
        base_for_total = float(document.subtotal.normalized_value) if document.subtotal else sum_charges
        expected_net = round(base_for_total - sum_deductions, 2)
        stated_net = round(float(document.total_amount.normalized_value), 2)
        delta_net = round(abs(expected_net - stated_net), 2)
        net_input_ids = [c.amount.field_id for c in document.cost_breakdown] + [document.total_amount.field_id]

        if delta_net <= 0.02:
            results.append(
                ValidationCheck(
                    validation_id=uuid4(),
                    check_code="QUOTATION_NET_TOTAL_CONSISTENCY",
                    status=ValidationStatus.PASS,
                    input_field_ids=net_input_ids,
                    expected_value=stated_net,
                    calculated_value=expected_net,
                    absolute_delta=delta_net,
                    severity=ValidationSeverity.INFO,
                    message=(
                        f"Quoted total ({curr_sym}{stated_net:,.2f}) reconciles mathematically: "
                        f"subtotal ({curr_sym}{base_for_total:,.2f}) minus offers/deductions ({curr_sym}{sum_deductions:,.2f})."
                    ),
                )
            )
        else:
            results.append(
                ValidationCheck(
                    validation_id=uuid4(),
                    check_code="QUOTATION_NET_TOTAL_CONSISTENCY",
                    status=ValidationStatus.FAIL,
                    input_field_ids=net_input_ids,
                    expected_value=stated_net,
                    calculated_value=expected_net,
                    absolute_delta=delta_net,
                    severity=ValidationSeverity.CRITICAL,
                    message=(
                        f"Quoted total arithmetic discrepancy: Stated total is {curr_sym}{stated_net:,.2f}, "
                        f"but calculated net total (subtotal {curr_sym}{base_for_total:,.2f} - offers {curr_sym}{sum_deductions:,.2f}) "
                        f"is {curr_sym}{expected_net:,.2f} (difference: {curr_sym}{delta_net:,.2f}). Requires verification."
                    ),
                )
            )

        return results

    def check_line_items_sum(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify sum(line_items.total_price) == subtotal (or total_amount if no subtotal)."""
        input_ids = [it.total_price.field_id for it in document.line_items]
        curr_sym = _get_currency_symbol(document.currency)

        if not document.line_items:
            if document.cost_breakdown:
                charges = [c for c in document.cost_breakdown if c.charge_nature == ChargeNature.CHARGE]
                sum_charges = round(sum(float(c.amount.normalized_value) for c in charges), 2)
                stated_sub = (
                    round(float(document.subtotal.normalized_value), 2)
                    if document.subtotal
                    else sum_charges
                )
                delta = round(abs(sum_charges - stated_sub), 2)
                cost_ids = [c.amount.field_id for c in charges]
                if document.subtotal:
                    cost_ids.append(document.subtotal.field_id)

                if delta <= 0.02:
                    return ValidationCheck(
                        validation_id=uuid4(),
                        check_code="ARITHMETIC_LINE_ITEMS_SUM",
                        status=ValidationStatus.PASS,
                        input_field_ids=cost_ids,
                        expected_value=stated_sub,
                        calculated_value=sum_charges,
                        absolute_delta=delta,
                        severity=ValidationSeverity.INFO,
                        message=f"Cost components sum ({curr_sym}{sum_charges:,.2f}) matches stated subtotal ({curr_sym}{stated_sub:,.2f}).",
                    )
                else:
                    return ValidationCheck(
                        validation_id=uuid4(),
                        check_code="ARITHMETIC_LINE_ITEMS_SUM",
                        status=ValidationStatus.FAIL,
                        input_field_ids=cost_ids,
                        expected_value=stated_sub,
                        calculated_value=sum_charges,
                        absolute_delta=delta,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Cost components sum discrepancy: Stated subtotal is {curr_sym}{stated_sub:,.2f}, "
                            f"but constituent charges sum to {curr_sym}{sum_charges:,.2f} "
                            f"(difference: {curr_sym}{delta:,.2f}). Requires verification."
                        ),
                    )
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_LINE_ITEMS_SUM",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=[document.total_amount.field_id] if document.total_amount else [],
                severity=ValidationSeverity.INFO,
                message="No itemized lines present to perform extension sum reconciliation.",
            )

        calc_sum = round(
            sum(float(it.total_price.normalized_value) for it in document.line_items), 2
        )
        target_field = document.subtotal or document.total_amount
        expected_val = round(float(target_field.normalized_value), 2)
        input_ids.append(target_field.field_id)

        delta = round(abs(calc_sum - expected_val), 2)

        if delta <= 0.02:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_LINE_ITEMS_SUM",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                expected_value=expected_val,
                calculated_value=calc_sum,
                absolute_delta=delta,
                severity=ValidationSeverity.INFO,
                message=f"Sum of itemized components ({curr_sym}{calc_sum:,.2f}) matches stated {target_field.field_key} ({curr_sym}{expected_val:,.2f}).",
            )

        return ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_LINE_ITEMS_SUM",
            status=ValidationStatus.FAIL,
            input_field_ids=input_ids,
            expected_value=expected_val,
            calculated_value=calc_sum,
            absolute_delta=delta,
            severity=ValidationSeverity.CRITICAL,
            message=(
                f"Line item arithmetic discrepancy: Itemized components sum to {curr_sym}{calc_sum:,.2f}, "
                f"but stated {target_field.field_key} is {curr_sym}{expected_val:,.2f} (unaccounted difference: {curr_sym}{delta:,.2f})."
            ),
        )

    def check_total_consistency(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify subtotal/base + taxes + shipping + fees - discounts == total_amount."""
        input_ids = [document.total_amount.field_id]
        curr_sym = _get_currency_symbol(document.currency)

        subtotal_val = float(document.subtotal.normalized_value) if document.subtotal else None
        items_sum = (
            round(sum(float(it.total_price.normalized_value) for it in document.line_items), 2)
            if document.line_items
            else None
        )
        charges_sum = (
            round(sum(float(c.amount.normalized_value) for c in document.cost_breakdown if c.charge_nature == ChargeNature.CHARGE), 2)
            if document.cost_breakdown
            else None
        )
        tax_val = float(document.tax_amount.normalized_value) if document.tax_amount else 0.0
        shipping_val = (
            float(document.shipping_amount.normalized_value) if document.shipping_amount else 0.0
        )
        fees_val = sum(float(f.normalized_value) for f in document.fees)
        discount_val = (
            float(document.discount_amount.normalized_value) if document.discount_amount else 0.0
        )
        if discount_val == 0.0 and document.cost_breakdown:
            ded_sum = sum(float(c.amount.normalized_value) for c in document.cost_breakdown if c.charge_nature == ChargeNature.DEDUCTION)
            if ded_sum > 0:
                discount_val = ded_sum
        total_val = round(float(document.total_amount.normalized_value), 2)

        if document.subtotal:
            input_ids.append(document.subtotal.field_id)
        if document.tax_amount:
            input_ids.append(document.tax_amount.field_id)
        if document.shipping_amount:
            input_ids.append(document.shipping_amount.field_id)
        if document.discount_amount:
            input_ids.append(document.discount_amount.field_id)
        for f in document.fees:
            input_ids.append(f.field_id)

        base = subtotal_val if subtotal_val is not None else (charges_sum if charges_sum is not None else items_sum)

        if base is None:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TOTAL_CONSISTENCY",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=input_ids,
                expected_value=total_val,
                severity=ValidationSeverity.INFO,
                message="Subtotal or itemized lines not explicitly stated; cannot perform total consistency check.",
            )

        if document.cost_breakdown:
            cand_breakdown = round(base - discount_val, 2)
            if abs(cand_breakdown - total_val) <= 0.02:
                expected_calc = cand_breakdown
                discount_note = f" (deducting offers/deductions of {curr_sym}{discount_val:,.2f} from pre-offer subtotal)" if discount_val > 0 else ""
                return ValidationCheck(
                    validation_id=uuid4(),
                    check_code="ARITHMETIC_TOTAL_CONSISTENCY",
                    status=ValidationStatus.PASS,
                    input_field_ids=input_ids,
                    expected_value=total_val,
                    calculated_value=expected_calc,
                    absolute_delta=0.0,
                    severity=ValidationSeverity.INFO,
                    message=(
                        f"Quoted total ({curr_sym}{total_val:,.2f}) matches subtotal ({curr_sym}{base:,.2f}){discount_note}."
                    ),
                )

        # Distinguish whether document-level discount is already incorporated or needs to be subtracted
        discount_note = ""
        if discount_val > 0.0:
            cand_a = round(base + tax_val + shipping_val + fees_val, 2)
            cand_b = round(base - discount_val + tax_val + shipping_val + fees_val, 2)

            if abs(cand_a - total_val) <= 0.02:
                expected_calc = cand_a
                discount_note = f" (stated discount of {curr_sym}{discount_val:,.2f} already incorporated into line amounts)"
            elif abs(cand_b - total_val) <= 0.02:
                expected_calc = cand_b
                discount_note = f" (deducting document discount of {curr_sym}{discount_val:,.2f})"
            else:
                # Neither matches within 0.02; choose the closer candidate
                expected_calc = (
                    cand_b if abs(cand_b - total_val) < abs(cand_a - total_val) else cand_a
                )
                discount_note = f" (factoring discount of {curr_sym}{discount_val:,.2f})"
        else:
            expected_calc = round(base + tax_val + shipping_val + fees_val, 2)

        delta = round(abs(expected_calc - total_val), 2)

        if delta <= 0.02:
            charges_breakdown = []
            if shipping_val > 0:
                charges_breakdown.append(f"shipping ({curr_sym}{shipping_val:,.2f})")
            if tax_val > 0:
                charges_breakdown.append(f"taxes ({curr_sym}{tax_val:,.2f})")
            if fees_val > 0:
                charges_breakdown.append(f"fees ({curr_sym}{fees_val:,.2f})")

            breakdown_str = f" + {' + '.join(charges_breakdown)}" if charges_breakdown else ""

            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TOTAL_CONSISTENCY",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                expected_value=total_val,
                calculated_value=expected_calc,
                absolute_delta=delta,
                severity=ValidationSeverity.INFO,
                message=(
                    f"Total amount ({curr_sym}{total_val:,.2f}) mathematically matches "
                    f"subtotal ({curr_sym}{base:,.2f}){breakdown_str}{discount_note}."
                ),
            )

        return ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_TOTAL_CONSISTENCY",
            status=ValidationStatus.FAIL,
            input_field_ids=input_ids,
            expected_value=total_val,
            calculated_value=expected_calc,
            absolute_delta=delta,
            severity=ValidationSeverity.CRITICAL,
            message=(
                f"Grand total mismatch: Subtotal ({curr_sym}{base:,.2f}) + shipping ({curr_sym}{shipping_val:,.2f}) "
                f"+ taxes ({curr_sym}{tax_val:,.2f}) + fees ({curr_sym}{fees_val:,.2f}){discount_note} "
                f"equals {curr_sym}{expected_calc:,.2f}, but stated total is {curr_sym}{total_val:,.2f} "
                f"(unaccounted difference: {curr_sym}{delta:,.2f})."
            ),
        )

    def check_tax_calculations(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify that stated tax amount is within plausible statutory limits."""
        curr_sym = _get_currency_symbol(document.currency)

        # In vehicle quotations or cost breakdowns with 0 or unstated separate tax line:
        if (
            document.subtotal
            and (document.cost_breakdown or document.document_type in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN))
            and (not document.tax_amount or float(document.tax_amount.normalized_value) == 0.0)
        ):
            input_ids = [document.subtotal.field_id]
            if document.tax_amount:
                input_ids.append(document.tax_amount.field_id)
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                calculated_value="0.0%",
                severity=ValidationSeverity.INFO,
                message=f"Stated tax is {curr_sym}0.00 (effective tax rate 0.0%).",
            )

        if not document.tax_amount or not document.subtotal:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=[document.total_amount.field_id] if document.total_amount else [],
                severity=ValidationSeverity.INFO,
                message="Tax amount or subtotal not itemized for tax rate verification.",
            )

        tax_val = float(document.tax_amount.normalized_value)
        sub_val = float(document.subtotal.normalized_value)
        input_ids = [document.tax_amount.field_id, document.subtotal.field_id]

        if tax_val == 0.0:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                calculated_value="0.0%",
                severity=ValidationSeverity.INFO,
                message=f"Stated tax is {curr_sym}0.00 (effective tax rate 0.0%).",
            )

        if sub_val <= 0:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=input_ids,
                severity=ValidationSeverity.INFO,
                message="Subtotal is zero; tax calculation rate cannot be calculated.",
            )

        effective_rate = round((tax_val / sub_val) * 100, 2)
        curr_sym = _get_currency_symbol(document.currency)
        import re

        tax_text = document.tax_amount.provenance.raw_text if document.tax_amount.provenance else ""
        stated_rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", tax_text)
        if stated_rate_match:
            stated_rate = float(stated_rate_match.group(1))
            expected_tax = round(sub_val * (stated_rate / 100.0), 2)
            delta = round(abs(expected_tax - tax_val), 2)
            if delta > 0.02:
                return ValidationCheck(
                    validation_id=uuid4(),
                    check_code="ARITHMETIC_TAX_MATCH",
                    status=ValidationStatus.FAIL,
                    input_field_ids=input_ids,
                    expected_value=f"{curr_sym}{expected_tax:,.2f} ({stated_rate}%)",
                    calculated_value=f"{curr_sym}{tax_val:,.2f}",
                    absolute_delta=delta,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Stated tax rate of {stated_rate}% on taxable subtotal ({curr_sym}{sub_val:,.2f}) "
                        f"should be {curr_sym}{expected_tax:,.2f}, but stated tax is {curr_sym}{tax_val:,.2f} "
                        f"(discrepancy: {curr_sym}{delta:,.2f})."
                    ),
                )
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                calculated_value=f"{curr_sym}{tax_val:,.2f}",
                severity=ValidationSeverity.INFO,
                message=f"Stated tax ({curr_sym}{tax_val:,.2f}) exactly reconciles with stated {stated_rate}% rate on taxable base {curr_sym}{sub_val:,.2f}.",
            )

        if effective_rate > 35.0:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="ARITHMETIC_TAX_MATCH",
                status=ValidationStatus.FAIL,
                input_field_ids=input_ids,
                expected_value="<= 35.0%",
                calculated_value=f"{effective_rate:.1f}%",
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Effective tax rate is unusually high ({effective_rate:.1f}%). "
                    "Requires verification of applicable local sales tax laws."
                ),
            )

        return ValidationCheck(
            validation_id=uuid4(),
            check_code="ARITHMETIC_TAX_MATCH",
            status=ValidationStatus.PASS,
            input_field_ids=input_ids,
            calculated_value=f"{effective_rate:.1f}%",
            severity=ValidationSeverity.INFO,
            message=f"Effective tax rate ({effective_rate:.1f}%) is within expected range.",
        )

    def check_date_consistency(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify chronological ordering between issued_date and due_date without fabricated defaults."""
        issued_val = (
            str(document.issued_date.normalized_value).strip()
            if document.issued_date and document.issued_date.normalized_value
            else None
        )
        due_val = (
            str(document.due_date.normalized_value).strip()
            if document.due_date and document.due_date.normalized_value
            else None
        )

        if (
            not issued_val
            or not due_val
            or issued_val.upper() in ["NULL", "NONE", "UNKNOWN", ""]
            or due_val.upper() in ["NULL", "NONE", "UNKNOWN", ""]
        ):
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="DATE_SEQUENCE_CHECK",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=[document.total_amount.field_id] if document.total_amount else [],
                expected_value=None,
                calculated_value=None,
                absolute_delta=None,
                severity=ValidationSeverity.INFO,
                message="Issue date or due date not explicitly present in document; chronological sequence check is inconclusive.",
            )

        input_ids = []
        if document.issued_date:
            input_ids.append(document.issued_date.field_id)
        if document.due_date:
            input_ids.append(document.due_date.field_id)

        try:
            issued_iso = normalize_date_to_iso(issued_val)
            due_iso = normalize_date_to_iso(due_val)
            if not issued_iso or not due_iso:
                return ValidationCheck(
                    validation_id=uuid4(),
                    check_code="DATE_SEQUENCE_CHECK",
                    status=ValidationStatus.INCONCLUSIVE,
                    input_field_ids=input_ids,
                    expected_value=None,
                    calculated_value=None,
                    absolute_delta=None,
                    severity=ValidationSeverity.INFO,
                    message="Date formats could not be parsed for chronological ordering check.",
                )

            issued_d = date.fromisoformat(issued_iso)
            due_d = date.fromisoformat(due_iso)

            if due_d < issued_d:
                return ValidationCheck(
                    validation_id=uuid4(),
                    check_code="DATE_SEQUENCE_CHECK",
                    status=ValidationStatus.FAIL,
                    input_field_ids=input_ids,
                    expected_value=f">= {issued_d}",
                    calculated_value=str(due_d),
                    absolute_delta=None,
                    severity=ValidationSeverity.WARNING,
                    message=f"Due date ({due_d}) precedes issue date ({issued_d}).",
                )

            return ValidationCheck(
                validation_id=uuid4(),
                check_code="DATE_SEQUENCE_CHECK",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                expected_value=f">= {issued_d}",
                calculated_value=str(due_d),
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message=f"Date sequence is valid: Due date ({due_d}) is on or after issue date ({issued_d}).",
            )
        except Exception:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="DATE_SEQUENCE_CHECK",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=input_ids,
                expected_value=None,
                calculated_value=None,
                absolute_delta=None,
                severity=ValidationSeverity.INFO,
                message="Date formats could not be parsed for chronological ordering check.",
            )

    def check_payment_status(
        self,
        document: StructuredFinancialDocument,
    ) -> ValidationCheck:
        """Verify payment reconciliation: amount_paid + balance_due == total_amount."""
        input_ids = [document.total_amount.field_id] if document.total_amount else []
        curr_sym = _get_currency_symbol(document.currency)
        total_val = (
            round(float(document.total_amount.normalized_value), 2)
            if document.total_amount
            else 0.0
        )

        if (
            total_val <= 0.0
            and not document.line_items
            and document.amount_paid is None
            and document.balance_due is None
        ):
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="PAYMENT_STATUS_RECONCILIATION",
                status=ValidationStatus.INCONCLUSIVE,
                input_field_ids=input_ids,
                expected_value=total_val,
                calculated_value=total_val,
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message="No payment balance applicable (zero financial total detected).",
            )

        if document.amount_paid is None and document.balance_due is None:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="PAYMENT_STATUS_RECONCILIATION",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                expected_value=total_val,
                calculated_value=total_val,
                absolute_delta=0.0,
                severity=ValidationSeverity.INFO,
                message=f"Payment status: {curr_sym}{total_val:,.2f} remains payable.",
            )

        paid_val = float(document.amount_paid.normalized_value) if document.amount_paid else 0.0
        balance_val = (
            float(document.balance_due.normalized_value)
            if document.balance_due
            else round(total_val - paid_val, 2)
        )

        if document.amount_paid:
            input_ids.append(document.amount_paid.field_id)
        if document.balance_due:
            input_ids.append(document.balance_due.field_id)

        expected_total = round(paid_val + balance_val, 2)
        delta = round(abs(expected_total - total_val), 2)

        if delta <= 0.02:
            return ValidationCheck(
                validation_id=uuid4(),
                check_code="PAYMENT_STATUS_RECONCILIATION",
                status=ValidationStatus.PASS,
                input_field_ids=input_ids,
                expected_value=total_val,
                calculated_value=balance_val,
                absolute_delta=delta,
                severity=ValidationSeverity.INFO,
                message=(
                    f"Payment status reconciled: Amount paid {curr_sym}{paid_val:,.2f}, "
                    f"Balance due {curr_sym}{balance_val:,.2f}. {curr_sym}{balance_val:,.2f} remains payable."
                ),
            )

        return ValidationCheck(
            validation_id=uuid4(),
            check_code="PAYMENT_STATUS_RECONCILIATION",
            status=ValidationStatus.FAIL,
            input_field_ids=input_ids,
            expected_value=total_val,
            calculated_value=expected_total,
            absolute_delta=delta,
            severity=ValidationSeverity.WARNING,
            message=(
                f"Payment balance discrepancy: Paid ({curr_sym}{paid_val:,.2f}) + "
                f"Balance due ({curr_sym}{balance_val:,.2f}) equals {curr_sym}{expected_total:,.2f}, "
                f"differing from stated total of {curr_sym}{total_val:,.2f}."
            ),
        )


DeterministicValidationService = DeterministicValidationEngine
