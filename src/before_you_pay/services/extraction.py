"""Structured financial extraction engine parsing OCR lines into normalized fields."""

import re
from typing import Any
from uuid import UUID, uuid4

from before_you_pay.core.dates import fallback_extract_date
from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    ChargeNature,
    ComponentCategory,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    LineItem,
    OcrLine,
    OcrResult,
    StructuredFinancialDocument,
)
from before_you_pay.services.financial_taxonomy import (
    classify_component_name,
    clean_component_text,
    normalize_financial_label,
)

# Label patterns for financial parsing
TOTAL_LABEL_PATTERN = re.compile(
    r"\b(grand\s*total|total\s*amount|net\s*total|total\s*payable|amount\s*payable|final\s*amount|total)\b",
    re.IGNORECASE,
)
SUBTOTAL_LABEL_PATTERN = re.compile(
    r"\b(subtotal|sub-total|sub\s*total|taxable\s*amount|net\s*taxable\s*amount|net\s*amount|items\s*subtotal|base\s*amount)\b",
    re.IGNORECASE,
)
TAX_LABEL_PATTERN = re.compile(
    r"\b(total\s*tax|tax\s*amount|cgst|sgst|igst|gst|vat|sales\s*tax|tax)\b",
    re.IGNORECASE,
)
SHIPPING_LABEL_PATTERN = re.compile(
    r"\b(shipping\s*details|shipping\s*charges?|shipping\s*fee|shipping|delivery\s*charges?|delivery\s*fee|delivery|freight\s*charges?|freight\s*charge|freight|handling\s*(?:&|and)\s*delivery|postage)\b",
    re.IGNORECASE,
)
FEE_LABEL_PATTERN = re.compile(
    r"\b(service\s*fees?|service\s*charges?|convenience\s*fees?|convenience\s*charges?|platform\s*fees?|platform\s*charges?|processing\s*fees?|processing\s*charges?|packaging\s*charges?|packaging\s*fees?|insurance|surcharge|fee)\b",
    re.IGNORECASE,
)
DISCOUNT_LABEL_PATTERN = re.compile(
    r"\b(total\s*discount|discount\s*amount|trade\s*discount|promo\s*discount|discount|rebate|coupon)\b",
    re.IGNORECASE,
)
PAID_LABEL_PATTERN = re.compile(
    r"\b(amount\s*paid|total\s*paid|paid\s*amount|paid|advance\s*paid|advance|deposit)\b",
    re.IGNORECASE,
)
BALANCE_LABEL_PATTERN = re.compile(
    r"\b(balance\s*due|amount\s*due|balance\s*payable|net\s*payable|net\s*due|remaining\s*payable)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")

TABLE_HEADER_PATTERN = re.compile(
    r"\b(items?|description|particulars)\b.*\b(hsn|sac|qty|mrp|rate|price|amount)\b",
    re.IGNORECASE,
)
TAX_IDENTIFIER_PATTERN = re.compile(
    r"\b(vat\s*no\.?|vat\s*number|gstin|tin\b|tax\s*id|registration\s*no\.?)\b",
    re.IGNORECASE,
)

# Lines that look like document metadata (invoice numbers, dates, page refs) — NOT line items
METADATA_LINE_PATTERN = re.compile(
    r"^\s*(?:"
    r"(?:invoice|bill|receipt|quotation|quote|estimate|order|ref(?:erence)?|po|purchase\s*order|statement|account)"
    r"\s*(?:#|no\.?|number|num|id)?\s*[:=]?\s*\S+"
    r"|date\s*[:=]\s*\S+"
    r"|page\s*[:=]?\s*\d+"
    r"|sr\.?\s*no\.?"
    r"|s\.?\s*no\.?"
    r"|#\s*\d+"
    r")\s*$",
    re.IGNORECASE,
)


def _is_metadata_line(text: str) -> bool:
    """Return True if the line looks like document metadata, not a purchasable item."""
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    if not text_stripped:
        return True
    # Short lines with only a number (e.g. page numbers)
    if re.fullmatch(r"\d{1,6}", text_stripped):
        return True
    # Table header line (all header columns, no data)
    if re.search(r"\bitems?\s+hsn\b", text_lower) or TABLE_HEADER_PATTERN.search(text_lower):
        return True
    # Tax / registration identifiers
    if TAX_IDENTIFIER_PATTERN.search(text_lower):
        return True
    if any(
        k in text_lower
        for k in [
            "place of supply",
            "vehicle no",
            "total amount in words",
            "powered by",
            "bill from",
            "bill to",
            "sample bill",
            "sample invoice",
            "e-way bill",
            "po no",
            "bill number",
        ]
    ):
        return True
    if any(
        k in text_lower
        for k in [
            "phone:",
            "phone :",
            "mobile:",
            "mobile :",
            "address:",
            "website:",
            "www.",
        ]
    ):
        return True
    if any(
        k in text_lower
        for k in [
            "market street",
            "ngo colony",
            "n.g.o. colony",
            "adambakkam",
            "chennai",
            "tamil nadu",
            "mysore",
            "karnataka",
            "sector 6",
            "12th main",
            "2nd floor",
        ]
    ):
        return True
    # IMEI, product ID, serial, batch
    if re.search(r"\b(imei|product\s*id|serial|batch)\b", text_lower):
        return True
    # Lines that are pure percentage or unit + percentage (e.g. "pcs 5.88%", "4%", "pcs 20%")
    if re.search(r"^\s*([a-zA-Z\s]+)?\d+(?:\.\d+)?\s*%\s*$", text_stripped):
        return True
    # Lines that are primarily a date
    if DATE_PATTERN.search(text_stripped):
        remaining = DATE_PATTERN.sub("", text_stripped).strip(":= -/")
        if not remaining or re.fullmatch(
            r"(?:date|issued|due|inv(?:oice)?|bill|created|order)?\s*", remaining, re.IGNORECASE
        ):
            return True
    if METADATA_LINE_PATTERN.match(text_stripped):
        return True
    return False


def detect_currency(text: str) -> str | None:
    """Detect currency code from text or return None if undetermined."""
    text_lower = text.lower()
    if "₹" in text or "inr" in text_lower or re.search(r"\brs\.?\b", text_lower):
        return "INR"
    if "$" in text or "usd" in text_lower:
        return "USD"
    if "€" in text or "eur" in text_lower:
        return "EUR"
    if "£" in text or "gbp" in text_lower:
        return "GBP"
    if "¥" in text or "jpy" in text_lower:
        return "JPY"
    if "c$" in text_lower or "cad" in text_lower:
        return "CAD"
    if "a$" in text_lower or "aud" in text_lower:
        return "AUD"
    return None


def detect_document_currency(lines: list[OcrLine]) -> str | None:
    """Determine currency across entire document lines."""
    for line in lines:
        curr = detect_currency(line.text)
        if curr:
            return curr
    return None


class FinancialExtractionEngine:
    """Extracts typed financial entities and line items from spatial OCR lines."""

    def extract(
        self,
        document_id: UUID,
        user_id: UUID,
        ocr_result: OcrResult,
        document_type_hint: DocumentClassification = DocumentClassification.OTHER,
    ) -> StructuredFinancialDocument:
        """Parse OCR result into StructuredFinancialDocument with strict field provenance."""
        all_lines: list[OcrLine] = []
        page_id_to_num: dict[UUID, int] = {}
        for page in ocr_result.pages:
            page_id_to_num[page.page_id] = page.page_number
            all_lines.extend(page.lines)

        doc_currency = detect_document_currency(all_lines)
        detected_type = self._classify_document(all_lines, document_type_hint)
        vendor_name_field = self._extract_vendor(document_id, ocr_result)
        issued_date_field = self._extract_date(document_id, all_lines)
        due_date_field = self._extract_due_date(document_id, all_lines)

        line_items: list[LineItem] = []
        subtotal_field: ExtractedField | None = None
        tax_field: ExtractedField | None = None
        taxes: list[ExtractedField] = []
        shipping_field: ExtractedField | None = None
        discount_field: ExtractedField | None = None
        fee_fields: list[ExtractedField] = []
        amount_paid_field: ExtractedField | None = None
        balance_due_field: ExtractedField | None = None
        total_field: ExtractedField | None = None
        clauses: list[ExtractedField] = []
        cost_breakdown: list[FinancialComponent] = []

        # Detect structured table layout if present
        table_header_idx = -1
        table_footer_idx = len(all_lines)
        for idx, line in enumerate(all_lines):
            t_low = line.text.lower()
            if TABLE_HEADER_PATTERN.search(t_low):
                table_header_idx = idx
                break

        if table_header_idx >= 0:
            for idx in range(table_header_idx + 1, len(all_lines)):
                t_low = all_lines[idx].text.lower()
                if (
                    SUBTOTAL_LABEL_PATTERN.search(t_low)
                    or TOTAL_LABEL_PATTERN.search(t_low)
                    or SHIPPING_LABEL_PATTERN.search(t_low)
                    or BALANCE_LABEL_PATTERN.search(t_low)
                    or PAID_LABEL_PATTERN.search(t_low)
                    or re.search(
                        r"\b(taxable\s*amount|cgst|sgst|shipping\s*details|balance\s*due)\b", t_low
                    )
                ):
                    table_footer_idx = idx
                    break

        # Parse line entries
        for line_idx, line in enumerate(all_lines):
            # If line is inside structured table, defer to table line item parser
            if table_header_idx >= 0 and table_header_idx <= line_idx < table_footer_idx:
                continue

            text_lower = line.text.lower()
            line_curr = detect_currency(line.text) or doc_currency

            # 1. Amount Paid check
            if PAID_LABEL_PATTERN.search(text_lower) and not BALANCE_LABEL_PATTERN.search(
                text_lower
            ):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    amount_paid_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="amount_paid",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 2. Balance Due check
            if BALANCE_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    balance_due_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="balance_due",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 3. Total line check
            if TOTAL_LABEL_PATTERN.search(text_lower) and not SUBTOTAL_LABEL_PATTERN.search(
                text_lower
            ):
                amount = self._parse_amount(line.text)
                if amount is not None and (
                    total_field is None or amount > float(total_field.normalized_value)
                ):
                    total_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="total_amount",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 4. Subtotal / Taxable amount check
            if SUBTOTAL_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    subtotal_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="subtotal",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 5. Shipping / Delivery check
            if SHIPPING_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    shipping_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="shipping_amount",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 6. Document-level discount check
            if DISCOUNT_LABEL_PATTERN.search(text_lower) and not any(
                k in text_lower for k in ["rate", "mrp", "item"]
            ):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    discount_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="discount_amount",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    continue

            # 7. Tax line check
            if TAX_LABEL_PATTERN.search(text_lower) and not TAX_IDENTIFIER_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    tax_ext = ExtractedField(
                        field_id=uuid4(),
                        field_key="tax_amount",
                        normalized_value=amount,
                        unit_or_currency=line_curr,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                    taxes.append(tax_ext)
                    if tax_field is None or "total" in text_lower:
                        tax_field = tax_ext
                    continue

            # 8. Ancillary Fee check
            if FEE_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    fee_fields.append(
                        ExtractedField(
                            field_id=uuid4(),
                            field_key="fee",
                            normalized_value=amount,
                            unit_or_currency=line_curr,
                            confidence=(line.confidence or 0.85),
                            provenance=FieldProvenance(
                                document_id=document_id,
                                page_id=line.page_id,
                                ocr_line_ids=[line.line_id],
                                bounding_box=line.bounding_box,
                                raw_text=line.text,
                            ),
                        )
                    )
                    continue

            # 9. Contractual clauses requiring attention (only for text terms without monetary amounts)
            if self._parse_amount(line.text) is None and any(
                k in text_lower
                for k in ["auto-renew", "cancellation", "penalty", "warranty", "restocking"]
            ):
                clauses.append(
                    ExtractedField(
                        field_id=uuid4(),
                        field_key="clause_term",
                        normalized_value=line.text,
                        unit_or_currency=None,
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
                )
                continue

            # 9b. Financial component check (quotations, cost breakdowns, fee schedules)
            comp_cat, comp_norm_name, comp_nature, comp_opt, comp_exp = classify_component_name(line.text)
            is_quote_doc = detected_type in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN)
            is_distinct_quote_charge = comp_cat in (
                ComponentCategory.EX_SHOWROOM_PRICE,
                ComponentCategory.ROAD_TAX,
                ComponentCategory.RC,
                ComponentCategory.HSRP,
                ComponentCategory.FASTAG,
                ComponentCategory.EXTENDED_WARRANTY,
                ComponentCategory.ACCESSORY_PACKAGE,
                ComponentCategory.HANDLING_FEE,
                ComponentCategory.LOGISTICS_FEE,
                ComponentCategory.PROCESSING_FEE,
                ComponentCategory.DEALER_PACKAGE,
                ComponentCategory.SERVICE_PACKAGE,
            )
            if (is_quote_doc or is_distinct_quote_charge) and comp_cat not in (
                ComponentCategory.TOTAL,
                ComponentCategory.SUBTOTAL,
            ):
                if not is_quote_doc and comp_cat in (
                    ComponentCategory.UNKNOWN,
                    ComponentCategory.UNCLEAR,
                    ComponentCategory.OTHER,
                ):
                    pass
                else:
                    amount = self._parse_amount(line.text)
                    if amount is not None and amount > 0:
                        cleaned_name = clean_component_text(line.text)
                        comp_amt_field = ExtractedField(
                            field_id=uuid4(),
                            field_key=f"cost_comp_{len(cost_breakdown)}_amount",
                            normalized_value=amount,
                            unit_or_currency=line_curr,
                            confidence=(line.confidence or 0.85),
                            provenance=FieldProvenance(
                                document_id=document_id,
                                page_id=line.page_id,
                                ocr_line_ids=[line.line_id],
                                bounding_box=line.bounding_box,
                                raw_text=line.text,
                            ),
                        )
                        norm_label = normalize_financial_label(cleaned_name or line.text)
                        cost_breakdown.append(
                            FinancialComponent(
                                component_id=uuid4(),
                                name=cleaned_name or comp_norm_name,
                                raw_text=line.text.strip(),
                                raw_name=line.text.strip(),
                                raw_label=cleaned_name or line.text.strip(),
                                normalized_name=comp_norm_name,
                                normalized_label=norm_label or comp_norm_name,
                                amount=comp_amt_field,
                                category=comp_cat,
                                vehicle_category=comp_cat.to_vehicle_category(),
                                charge_nature=comp_nature,
                                charge_or_deduction=comp_nature.value,
                                confidence=(line.confidence or 0.85),
                                evidence=line.text,
                                source_ocr_line=str(line.line_id),
                                bounding_box=line.bounding_box,
                                page=page_id_to_num.get(line.page_id, 1),
                                explanation=comp_exp,
                            )
                        )
                        if detected_type in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN):
                            continue

            # 10. Candidate itemized line item (only if no structured table was found)
            if table_header_idx < 0:
                if _is_metadata_line(line.text):
                    continue
                amount = self._parse_amount(line.text)
                if amount is not None and amount > 0:
                    item = self._build_line_item(document_id, line, amount, doc_currency)
                    line_items.append(item)

        # Fallback or aggregate tax_amount if individual tax components were itemized
        if taxes:
            has_explicit_total = any("total" in (t.provenance.raw_text or "").lower() for t in taxes)
            if not has_explicit_total or tax_field is None:
                sum_tax = round(sum(float(t.normalized_value) for t in taxes), 2)
                first_t = taxes[0]
                tax_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="tax_amount",
                    normalized_value=sum_tax,
                    unit_or_currency=first_t.unit_or_currency,
                    confidence=first_t.confidence,
                    provenance=first_t.provenance,
                )

        # If structured table was found, extract table line items with column context
        if table_header_idx >= 0:
            table_lines = all_lines[table_header_idx + 1 : table_footer_idx]
            disc_amt_val = float(discount_field.normalized_value) if discount_field else None
            line_items = self._extract_table_line_items(
                document_id=document_id,
                table_lines=table_lines,
                currency=doc_currency,
                total_discount=disc_amt_val,
            )

        # Fallback subtotal from cost_breakdown if missing
        if subtotal_field is None and cost_breakdown:
            charges_sum = round(sum(float(c.amount.normalized_value) for c in cost_breakdown if c.charge_nature == ChargeNature.CHARGE), 2)
            if charges_sum > 0:
                first_c = cost_breakdown[0]
                subtotal_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="subtotal",
                    normalized_value=charges_sum,
                    unit_or_currency=doc_currency,
                    confidence=first_c.amount.confidence,
                    provenance=first_c.amount.provenance,
                )

        # Fallback discount_amount from cost_breakdown if missing
        if discount_field is None and cost_breakdown:
            deductions_sum = round(sum(float(c.amount.normalized_value) for c in cost_breakdown if c.charge_nature == ChargeNature.DEDUCTION), 2)
            if deductions_sum > 0:
                first_d = [c for c in cost_breakdown if c.charge_nature == ChargeNature.DEDUCTION][0]
                discount_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="discount_amount",
                    normalized_value=deductions_sum,
                    unit_or_currency=doc_currency,
                    confidence=first_d.amount.confidence,
                    provenance=first_d.amount.provenance,
                )

        # Fallback total if no explicit total label was matched
        if total_field is None:
            if balance_due_field is not None and (
                amount_paid_field is None or float(amount_paid_field.normalized_value) == 0.0
            ):
                total_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="total_amount",
                    normalized_value=float(balance_due_field.normalized_value),
                    unit_or_currency=balance_due_field.unit_or_currency,
                    confidence=balance_due_field.confidence,
                    provenance=balance_due_field.provenance,
                )
            elif cost_breakdown:
                charges_sum = sum(float(c.amount.normalized_value) for c in cost_breakdown if c.charge_nature == ChargeNature.CHARGE)
                deductions_sum = sum(float(c.amount.normalized_value) for c in cost_breakdown if c.charge_nature == ChargeNature.DEDUCTION)
                computed_sum = round(charges_sum - deductions_sum, 2)
                first_line = all_lines[-1] if all_lines else ocr_result.pages[0].lines[0]
                total_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="total_amount",
                    normalized_value=computed_sum,
                    unit_or_currency=doc_currency,
                    confidence=(first_line.confidence or 0.85),
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=first_line.page_id,
                        ocr_line_ids=[first_line.line_id],
                        bounding_box=first_line.bounding_box,
                        raw_text=first_line.text,
                    ),
                )
            elif line_items:
                base_sum = sum(float(it.total_price.normalized_value) for it in line_items)
                ship_amt = float(shipping_field.normalized_value) if shipping_field else 0.0
                tax_amt = float(tax_field.normalized_value) if tax_field else 0.0
                fee_amt = sum(float(f.normalized_value) for f in fee_fields)
                computed_sum = round(base_sum + ship_amt + tax_amt + fee_amt, 2)
                first_line = all_lines[-1] if all_lines else ocr_result.pages[0].lines[0]
                total_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="total_amount",
                    normalized_value=computed_sum,
                    unit_or_currency=doc_currency,
                    confidence=(first_line.confidence or 0.85),
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=first_line.page_id,
                        ocr_line_ids=[first_line.line_id],
                        bounding_box=first_line.bounding_box,
                        raw_text=first_line.text,
                    ),
                )
            else:
                raise ContractViolationException(
                    "No total amount or itemized financial figures could be identified in the document.",
                    details={"document_id": str(document_id)},
                )

        # Determine payment status with traceable field provenance
        payment_status_field = None
        for line in all_lines:
            text_lower = line.text.lower()
            status_match = re.search(
                r"\b(?:payment\s*)?status\b\s*[:=]\s*(paid|unpaid|partial(?:ly\s*paid)?|overdue|due|pending)",
                text_lower,
            )
            if status_match:
                raw_stat = status_match.group(1).strip()
                norm_stat = (
                    "paid"
                    if "paid" in raw_stat and "partial" not in raw_stat
                    else (
                        "partial"
                        if "partial" in raw_stat
                        else ("overdue" if "overdue" in raw_stat else "unpaid")
                    )
                )
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value=norm_stat,
                    unit_or_currency=None,
                    confidence=(line.confidence or 0.85),
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=line.page_id,
                        ocr_line_ids=[line.line_id],
                        bounding_box=line.bounding_box,
                        raw_text=line.text,
                    ),
                )
                break

        if payment_status_field is None:
            if balance_due_field is not None and float(balance_due_field.normalized_value) == 0.0:
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value="paid",
                    unit_or_currency=None,
                    confidence=balance_due_field.confidence,
                    provenance=balance_due_field.provenance,
                )
            elif (
                amount_paid_field is not None
                and total_field is not None
                and float(amount_paid_field.normalized_value) >= float(total_field.normalized_value)
            ):
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value="paid",
                    unit_or_currency=None,
                    confidence=amount_paid_field.confidence,
                    provenance=amount_paid_field.provenance,
                )
            elif (
                amount_paid_field is not None
                and float(amount_paid_field.normalized_value) > 0.0
                and (balance_due_field is None or float(balance_due_field.normalized_value) > 0.0)
            ):
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value="partial",
                    unit_or_currency=None,
                    confidence=amount_paid_field.confidence,
                    provenance=amount_paid_field.provenance,
                )
            elif balance_due_field is not None and float(balance_due_field.normalized_value) > 0.0:
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value="unpaid",
                    unit_or_currency=None,
                    confidence=balance_due_field.confidence,
                    provenance=balance_due_field.provenance,
                )
            elif total_field is not None and float(total_field.normalized_value) > 0.0:
                payment_status_field = ExtractedField(
                    field_id=uuid4(),
                    field_key="payment_status",
                    normalized_value="unpaid",
                    unit_or_currency=None,
                    confidence=total_field.confidence,
                    provenance=total_field.provenance,
                )
            else:
                payment_status_field = None

        return StructuredFinancialDocument(
            document_id=document_id,
            user_id=user_id,
            document_type=detected_type,
            currency=doc_currency,
            vendor_name=vendor_name_field,
            issued_date=issued_date_field,
            due_date=due_date_field,
            line_items=line_items,
            subtotal=subtotal_field,
            tax_amount=tax_field,
            taxes=taxes,
            shipping_amount=shipping_field,
            discount_amount=discount_field,
            fees=fee_fields,
            amount_paid=amount_paid_field,
            balance_due=balance_due_field,
            payment_status=payment_status_field,
            total_amount=total_field,
            cost_breakdown=cost_breakdown,
            clauses_and_notes=clauses,
        )

    def _classify_document(
        self,
        lines: list[OcrLine],
        hint: DocumentClassification,
    ) -> DocumentClassification:
        """Infer document category from header lines and keywords."""
        if hint != DocumentClassification.OTHER:
            return hint

        full_text = " ".join([ln.text.lower() for ln in lines[:10]])
        if "quotation" in full_text or "estimate" in full_text:
            return DocumentClassification.QUOTATION
        if "invoice" in full_text:
            return DocumentClassification.INVOICE
        if "warranty" in full_text or "coverage" in full_text:
            return DocumentClassification.WARRANTY
        if "subscription" in full_text or "recurring" in full_text:
            return DocumentClassification.SUBSCRIPTION
        if "contract" in full_text or "agreement" in full_text:
            return DocumentClassification.CONTRACT
        if "bill" in full_text:
            return DocumentClassification.BILL
        return DocumentClassification.OTHER

    def _extract_vendor(self, document_id: UUID, ocr_result: OcrResult) -> ExtractedField | None:
        """Identify vendor name from header lines, skipping generic document headings."""
        if not ocr_result.pages or not ocr_result.pages[0].lines:
            return None

        generic_headings = {
            "sample bill",
            "sample invoice",
            "invoice",
            "tax invoice",
            "quotation",
            "quote",
            "bill",
            "billing statement",
            "receipt",
            "contract",
            "agreement",
            "subscription",
            "estimate",
            "order",
        }

        for line in ocr_result.pages[0].lines[:10]:
            clean_text = line.text.strip().rstrip(" ,;:-")
            if len(clean_text) < 2 or clean_text.lower() in generic_headings:
                continue
            if re.match(r"^(invoice|quote|bill|date|total|page|statement)\b", clean_text.lower()):
                continue
            if any(k in clean_text.lower() for k in ["address:", "phone:", "mobile:", "website:", "www.", "street", "road", "colony", "place of supply"]):
                continue
            # Clean trailing OCR artifacts: duplicated logo/brand fragments and non-alphanumeric garbage
            # e.g. "Zetran Technologies Pvt., Ltd., zetran ☐" → "Zetran Technologies Pvt., Ltd."
            # Remove trailing comma + lowercase fragment that repeats a word already in the name
            words_lower = set(w.lower() for w in re.findall(r'[a-zA-Z]{2,}', clean_text))
            trailing_m = re.search(r',\s+([a-z]+(?:\s+[a-z]+)?)\s*[^\w,]*\s*$', clean_text)
            if trailing_m:
                trailing_word = trailing_m.group(1).lower().split()[0]
                if trailing_word in words_lower:
                    clean_text = clean_text[:trailing_m.start()].rstrip(' ,;:-')
            # Strip trailing non-alphanumeric garbage (unicode boxes, stray symbols)
            clean_text = re.sub(r'[^\w.,&\'"()\-/]+\s*$', '', clean_text).rstrip(' ,;:-')

            return ExtractedField(
                field_id=uuid4(),
                field_key="vendor_name",
                normalized_value=clean_text,
                unit_or_currency=None,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
        return None

    def _extract_date(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for date pattern across top lines and normalize to ISO YYYY-MM-DD."""
        iso_val, line = fallback_extract_date(lines, field_type="issued_date")
        if iso_val and line:
            return ExtractedField(
                field_id=uuid4(),
                field_key="issued_date",
                normalized_value=iso_val,
                unit_or_currency=None,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
        return None

    def _extract_due_date(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for explicit due date pattern across lines and normalize to ISO YYYY-MM-DD."""
        iso_val, line = fallback_extract_date(lines, field_type="due_date")
        if iso_val and line:
            return ExtractedField(
                field_id=uuid4(),
                field_key="due_date",
                normalized_value=iso_val,
                unit_or_currency=None,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
        return None

    def _extract_total(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for total amount across lines."""
        best_field: ExtractedField | None = None
        for line in lines:
            text_lower = line.text.lower()
            if TOTAL_LABEL_PATTERN.search(text_lower) and not SUBTOTAL_LABEL_PATTERN.search(
                text_lower
            ):
                amount = self._parse_amount(line.text)
                if amount is not None and (
                    best_field is None or amount > float(best_field.normalized_value)
                ):
                    best_field = ExtractedField(
                        field_id=uuid4(),
                        field_key="total_amount",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return best_field

    def _extract_subtotal(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for subtotal amount across lines."""
        for line in lines:
            text_lower = line.text.lower()
            if SUBTOTAL_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
                        field_id=uuid4(),
                        field_key="subtotal",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return None

    def _extract_tax(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for tax amount across lines."""
        taxes: list[ExtractedField] = []
        for line in lines:
            text_lower = line.text.lower()
            if TAX_IDENTIFIER_PATTERN.search(text_lower):
                continue
            if TAX_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    taxes.append(
                        ExtractedField(
                            field_id=uuid4(),
                            field_key="tax_amount",
                            normalized_value=amount,
                            unit_or_currency=detect_currency(line.text),
                            confidence=(line.confidence or 0.85),
                            provenance=FieldProvenance(
                                document_id=document_id,
                                page_id=line.page_id,
                                ocr_line_ids=[line.line_id],
                                bounding_box=line.bounding_box,
                                raw_text=line.text,
                            ),
                        )
                    )
        if taxes:
            for t in taxes:
                if "total" in (t.provenance.raw_text or "").lower():
                    return t
            sum_tax = round(sum(float(t.normalized_value) for t in taxes), 2)
            first_t = taxes[0]
            return ExtractedField(
                field_id=uuid4(),
                field_key="tax_amount",
                normalized_value=sum_tax,
                unit_or_currency=first_t.unit_or_currency,
                confidence=first_t.confidence,
                provenance=first_t.provenance,
            )
        return None

    def _extract_shipping(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for shipping amount across lines."""
        for line in lines:
            text_lower = line.text.lower()
            if SHIPPING_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
                        field_id=uuid4(),
                        field_key="shipping_amount",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return None

    def _extract_discount(self, document_id: UUID, lines: list[OcrLine]) -> ExtractedField | None:
        """Search for document-level discount across lines."""
        for line in lines:
            text_lower = line.text.lower()
            if DISCOUNT_LABEL_PATTERN.search(text_lower) and not any(
                k in text_lower for k in ["rate", "mrp", "item"]
            ):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
                        field_id=uuid4(),
                        field_key="discount_amount",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return None

    def _extract_amount_paid(
        self, document_id: UUID, lines: list[OcrLine]
    ) -> ExtractedField | None:
        """Search for amount paid across lines."""
        for line in lines:
            text_lower = line.text.lower()
            if PAID_LABEL_PATTERN.search(text_lower) and not BALANCE_LABEL_PATTERN.search(
                text_lower
            ):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
                        field_id=uuid4(),
                        field_key="amount_paid",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return None

    def _extract_balance_due(
        self, document_id: UUID, lines: list[OcrLine]
    ) -> ExtractedField | None:
        """Search for balance due across lines."""
        for line in lines:
            text_lower = line.text.lower()
            if BALANCE_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
                        field_id=uuid4(),
                        field_key="balance_due",
                        normalized_value=amount,
                        unit_or_currency=detect_currency(line.text),
                        confidence=(line.confidence or 0.85),
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=line.page_id,
                            ocr_line_ids=[line.line_id],
                            bounding_box=line.bounding_box,
                            raw_text=line.text,
                        ),
                    )
        return None

    def _extract_line_items(
        self, document_id: UUID, lines: list[OcrLine], currency: str | None
    ) -> list[LineItem]:
        """Extract itemized line items when LLM does not return any."""
        items: list[LineItem] = []
        for line in lines:
            text_lower = line.text.lower()
            if any(
                p.search(text_lower)
                for p in [
                    TOTAL_LABEL_PATTERN,
                    SUBTOTAL_LABEL_PATTERN,
                    TAX_LABEL_PATTERN,
                    SHIPPING_LABEL_PATTERN,
                    FEE_LABEL_PATTERN,
                    DISCOUNT_LABEL_PATTERN,
                    PAID_LABEL_PATTERN,
                    BALANCE_LABEL_PATTERN,
                ]
            ):
                continue
            # Skip document metadata lines (invoice numbers, dates, page refs)
            if _is_metadata_line(line.text):
                continue
            amt = self._parse_amount(line.text)
            if amt is not None and amt > 0:
                item = self._build_line_item(document_id, line, amt, currency)
                items.append(item)
        return items

    def _extract_line_items(
        self,
        document_id: UUID,
        lines: list[OcrLine],
        currency: str | None,
        total_discount: float | None = None,
    ) -> list[LineItem]:
        """Extract itemized line items using spatial table boundaries if present, or deterministic fallback."""
        table_header_idx = -1
        table_footer_idx = len(lines)
        for idx, line in enumerate(lines):
            t_low = line.text.lower()
            if TABLE_HEADER_PATTERN.search(t_low):
                table_header_idx = idx
                break

        if table_header_idx >= 0:
            for idx in range(table_header_idx + 1, len(lines)):
                t_low = lines[idx].text.lower()
                if (
                    SUBTOTAL_LABEL_PATTERN.search(t_low)
                    or TOTAL_LABEL_PATTERN.search(t_low)
                    or SHIPPING_LABEL_PATTERN.search(t_low)
                    or BALANCE_LABEL_PATTERN.search(t_low)
                    or PAID_LABEL_PATTERN.search(t_low)
                    or re.search(
                        r"\b(taxable\s*amount|cgst|sgst|shipping\s*details|balance\s*due)\b", t_low
                    )
                ):
                    table_footer_idx = idx
                    break

            table_lines = lines[table_header_idx + 1 : table_footer_idx]
            return self._extract_table_line_items(
                document_id=document_id,
                table_lines=table_lines,
                currency=currency,
                total_discount=total_discount,
            )

        items: list[LineItem] = []
        for line in lines:
            text_lower = line.text.lower()
            if any(
                p.search(text_lower)
                for p in [
                    TOTAL_LABEL_PATTERN,
                    SUBTOTAL_LABEL_PATTERN,
                    TAX_LABEL_PATTERN,
                    SHIPPING_LABEL_PATTERN,
                    FEE_LABEL_PATTERN,
                    DISCOUNT_LABEL_PATTERN,
                    PAID_LABEL_PATTERN,
                    BALANCE_LABEL_PATTERN,
                ]
            ):
                continue
            # Skip document metadata lines (invoice numbers, dates, page refs, addresses)
            if _is_metadata_line(line.text):
                continue
            amt = self._parse_amount(line.text)
            if amt is not None and amt > 0:
                item = self._build_line_item(document_id, line, amt, currency)
                items.append(item)
        return items

    def _extract_table_line_items(
        self,
        document_id: UUID,
        table_lines: list[OcrLine],
        currency: str | None,
        total_discount: float | None = None,
    ) -> list[LineItem]:
        """Parse structured table rows into verified LineItems with column alignment."""
        items: list[LineItem] = []
        num_pattern = re.compile(
            r"\b[0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?\b|\b[0-9]+(?:\.[0-9]+)?\b"
        )

        pending_items_data: list[dict[str, Any]] = []
        current_data: dict[str, Any] | None = None

        for line in table_lines:
            txt = line.text.strip()
            # 1. Check if line is secondary/subtext (IMEI, Product ID, category, or ends with percentage)
            is_sub = (
                re.search(r"\b(imei|product\s*id|serial|batch)\b", txt, re.IGNORECASE)
                or re.search(r"%\s*$", txt)
                or ("pcs" in txt.lower() and not re.search(r"\b[0-9]{4,8}\b", txt))
            )
            if is_sub:
                pct_m = re.search(r"(\d+(?:\.\d+)?)\s*%", txt)
                if pct_m and current_data:
                    pct = float(pct_m.group(1))
                    if current_data.get("discount") is None or current_data.get("discount") == 0.0:
                        base = (
                            current_data.get("mrp")
                            or current_data.get("rate")
                            or current_data.get("amount")
                            or 0.0
                        )
                        calc_val = base * (pct / 100.0)
                        if abs(calc_val - round(calc_val)) < 0.25:
                            calc_val = float(round(calc_val))
                        else:
                            calc_val = round(calc_val, 2)
                        current_data["discount"] = calc_val
                continue

            # 2. Match product row: find HSN code and extract description + numeric columns
            # Flexible approach: identify the 4-8 digit HSN, text before it is description,
            # then parse all numbers from the remainder regardless of OCR noise
            hsn_match = re.search(r'\b(\d{4,8})\b', txt)
            if hsn_match and not _is_metadata_line(txt):
                desc = txt[:hsn_match.start()].strip()
                after_hsn = txt[hsn_match.end():]
                hsn = hsn_match.group(1)

                # Clean OCR artifacts from numeric section: 'e' (misread ₹/1), '*' (bullet)
                after_clean = re.sub(r'\be\b', '', after_hsn)
                after_clean = after_clean.replace('*', '')
                nums = [float(x.replace(",", "")) for x in num_pattern.findall(after_clean)]

                # Need at least 1 number (the amount) to consider this a valid row
                if desc and nums:
                    # Assign numbers right-to-left: amount is always last
                    amt = nums[-1]
                    tax = 0.0
                    disc = None
                    rate = None
                    mrp = None
                    qty_val = 1.0

                    if len(nums) >= 5:
                        # qty, mrp, rate/disc, tax, amount  OR  mrp, rate, disc, tax, amount
                        mrp, rate, disc, tax, amt = nums[-5], nums[-4], nums[-3], nums[-2], nums[-1]
                        if len(nums) >= 6:
                            qty_val = nums[0]
                    elif len(nums) == 4:
                        # 4 numbers: likely [MRP, rate_or_disc, tax, amount] or [disc, tax, amount, ?]
                        if nums[-2] == 0.0:
                            # tax=0 case: [A, B, 0.0, amount]
                            if nums[0] > nums[-1]:
                                # First number > amount → likely MRP
                                mrp = nums[0]
                                rate = nums[1]
                                disc = nums[1]  # rate and disc may be same value
                            elif nums[0] <= 10:
                                qty_val = nums[0]
                                disc = nums[1]
                            else:
                                disc = nums[1]
                                rate = nums[0]
                            tax = nums[-2]
                            amt = nums[-1]
                        else:
                            mrp, disc, tax, amt = nums[-4], nums[-3], nums[-2], nums[-1]
                    elif len(nums) == 3:
                        # Common: disc, tax, amount  or  rate, tax, amount
                        if nums[-2] == 0.0:
                            disc, tax, amt = nums[-3], nums[-2], nums[-1]
                        else:
                            rate, tax, amt = nums[-3], nums[-2], nums[-1]
                    elif len(nums) == 2:
                        rate, amt = nums[-2], nums[-1]
                    # else: single number = amount only

                    current_data = {
                        "line": line,
                        "desc": desc,
                        "hsn": hsn,
                        "qty": qty_val,
                        "mrp": mrp,
                        "rate": rate,
                        "discount": disc,
                        "tax": tax,
                        "amount": amt,
                    }
                    pending_items_data.append(current_data)
                    continue

            # Fallback for table lines without a recognizable HSN code
            if not _is_metadata_line(txt):
                amt = self._parse_amount(txt)
                if amt is not None and amt > 0:
                    cleaned_desc = re.sub(
                        r"(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*$",
                        "",
                        txt,
                    ).strip(":= -|\t")
                    current_data = {
                        "line": line,
                        "desc": cleaned_desc or f"Item (line {line.line_number})",
                        "hsn": None,
                        "qty": 1.0,
                        "mrp": None,
                        "rate": amt,
                        "discount": None,
                        "tax": 0.0,
                        "amount": amt,
                    }
                    pending_items_data.append(current_data)

        # Reconcile discount for any item missing explicit discount if total document discount is known
        if total_discount and total_discount > 0:
            known_disc = sum(
                it["discount"] for it in pending_items_data if it.get("discount") is not None
            )
            missing = [it for it in pending_items_data if it.get("discount") is None]
            if len(missing) == 1 and total_discount > known_disc:
                missing[0]["discount"] = round(total_discount - known_disc, 2)

        # Build LineItem objects
        for it in pending_items_data:
            item_obj = self._build_table_line_item(
                document_id=document_id,
                line=it["line"],
                desc_text=it["desc"],
                qty=it["qty"],
                mrp=it["mrp"],
                rate=it["rate"],
                discount=it["discount"],
                amount=it["amount"],
                tax=it["tax"],
                currency=currency,
            )
            items.append(item_obj)

        return items

    def _build_table_line_item(
        self,
        document_id: UUID,
        line: OcrLine,
        desc_text: str,
        qty: float,
        mrp: float | None,
        rate: float | None,
        discount: float | None,
        amount: float,
        tax: float | None,
        currency: str | None,
    ) -> LineItem:
        """Construct LineItem from extracted table fields with strict field provenance."""
        item_curr = detect_currency(line.text) or currency
        desc_field = ExtractedField(
            field_id=uuid4(),
            field_key="item_description",
            normalized_value=desc_text,
            unit_or_currency=None,
            confidence=(line.confidence or 0.85),
            provenance=FieldProvenance(
                document_id=document_id,
                page_id=line.page_id,
                ocr_line_ids=[line.line_id],
                bounding_box=line.bounding_box,
                raw_text=line.text,
            ),
        )
        qty_field = ExtractedField(
            field_id=uuid4(),
            field_key="item_quantity",
            normalized_value=qty,
            unit_or_currency=None,
            confidence=(line.confidence or 0.85),
            provenance=FieldProvenance(
                document_id=document_id,
                page_id=line.page_id,
                ocr_line_ids=[line.line_id],
                bounding_box=line.bounding_box,
                raw_text=line.text,
            ),
        )
        unit_price_field = None
        if rate is not None:
            unit_price_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_unit_price",
                normalized_value=rate,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
        total_price_field = ExtractedField(
            field_id=uuid4(),
            field_key="item_total",
            normalized_value=amount,
            unit_or_currency=item_curr,
            confidence=(line.confidence or 0.85),
            provenance=FieldProvenance(
                document_id=document_id,
                page_id=line.page_id,
                ocr_line_ids=[line.line_id],
                bounding_box=line.bounding_box,
                raw_text=line.text,
            ),
        )
        mrp_field = None
        if mrp is not None:
            mrp_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_mrp",
                normalized_value=mrp,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
        disc_field = None
        item_discounts: list[ExtractedField] = []
        if discount is not None and discount > 0:
            disc_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_discount",
                normalized_value=discount,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
            item_discounts.append(disc_field)

        taxes_list: list[ExtractedField] = []
        if tax is not None:
            taxes_list.append(
                ExtractedField(
                    field_id=uuid4(),
                    field_key="item_tax",
                    normalized_value=tax,
                    unit_or_currency=item_curr,
                    confidence=(line.confidence or 0.85),
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=line.page_id,
                        ocr_line_ids=[line.line_id],
                        bounding_box=line.bounding_box,
                        raw_text=line.text,
                    ),
                )
            )

        return LineItem(
            item_id=uuid4(),
            description=desc_field,
            quantity=qty_field,
            unit_price=unit_price_field,
            total_price=total_price_field,
            mrp=mrp_field,
            discount=disc_field,
            discounts=item_discounts,
            taxes=taxes_list,
        )

    def _parse_amount(self, text: str) -> float | None:
        """Extract numeric amount from text line, preserving integers, decimals, and Indian numbering."""
        text_clean = text.strip()
        # Pre-clean OCR noise: double periods ("29,497..0" → "29,497.0"), stray '*' before digits
        text_clean = re.sub(r'\.{2,}', '.', text_clean)
        text_clean = re.sub(r'\*(\d)', r'\1', text_clean)
        text_lower = text_clean.lower()

        # Reject pure percentage or token ending with %
        if re.search(r"^\s*([a-zA-Z\s]+)?\d+(?:\.\d+)?\s*%\s*$", text_clean):
            return None

        # Reject tax identifiers
        if TAX_IDENTIFIER_PATTERN.search(text_lower):
            return None

        # Reject addresses, phone, mobile, vehicle, dates unless explicit currency symbol is present
        has_curr_sym = bool(re.search(r"[₹$€£¥]|Rs\.?|INR|USD", text_clean, re.IGNORECASE))
        if not has_curr_sym:
            if any(
                k in text_lower
                for k in [
                    "address:",
                    "phone",
                    "mobile",
                    "street",
                    "colony",
                    "adambakkam",
                    "chennai",
                    "mysore",
                    "karnataka",
                    "tamil nadu",
                    "sector 6",
                    "12th main",
                    "2nd floor",
                    "vehicle no",
                    "e-way",
                    "po no",
                    "bill number",
                    "bill no",
                    "place of supply",
                ]
            ):
                return None
            if re.search(r"\b(imei|product\s*id|serial|batch)\b", text_lower):
                return None
            if DATE_PATTERN.search(text_clean) and any(
                k in text_lower for k in ["date", "bill", "due", "inv"]
            ):
                return None

        # 1. Look for explicit currency symbol followed or preceded by amount
        symbol_pattern = re.compile(
            r"(?:[₹$€£¥]|Rs\.?|INR|USD|EUR|GBP|CAD|AUD)\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?:\s*\/\s*[-–—]?)?",
            re.IGNORECASE,
        )
        sym_matches = symbol_pattern.findall(text_clean)
        if sym_matches:
            val_str = sym_matches[-1].replace(",", "").rstrip(".")
            try:
                return float(val_str)
            except ValueError:
                pass

        # 2. Look for assignment or colon: e.g. "= 499" or ": 499" or "= 29,497" or "₹11,49,900/-"
        assign_pattern = re.compile(
            r"[:=]\s*(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?:\s*\/\s*[-–—]?)?\s*$",
            re.IGNORECASE,
        )
        assign_match = assign_pattern.search(text_clean)
        if assign_match:
            try:
                return float(assign_match.group(1).replace(",", "").rstrip("."))
            except ValueError:
                pass

        # 3. Look for general numeric values in the line (take the last one, supporting Indian numbering)
        general_pattern = re.compile(
            r"\b([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?:\s*\/\s*[-–—]?)?\b"
        )
        all_num_matches = general_pattern.findall(text_clean)
        if all_num_matches:
            # Filter out numbers followed immediately by %
            filtered_matches = []
            for m in all_num_matches:
                escaped = re.escape(m)
                if not re.search(rf"{escaped}\s*%", text_clean):
                    filtered_matches.append(m)
            if filtered_matches:
                val_str = filtered_matches[-1].replace(",", "").rstrip(".")
                try:
                    return float(val_str)
                except ValueError:
                    pass

        return None

    def _build_line_item(
        self, document_id: UUID, line: OcrLine, amount: float, currency: str | None
    ) -> LineItem:
        """Construct LineItem from line text and extracted amount, extracting MRP and discounts if available."""
        text = line.text.strip()
        item_curr = detect_currency(text) or currency

        # Extract item name
        if ":" in text and any(
            k in text.lower() for k in ["mrp", "rate", "discount", "amount", "price"]
        ):
            desc_text = text.split(":", 1)[0].strip()
        elif any(k in text.lower() for k in ["mrp", "rate", "discount", "final line"]):
            desc_text = re.sub(
                r"[:=]?\s*\b(?:MRP|Rate(?:/Item)?|Unit\s*Price|Discount|Final\s*line\s*amount)\b.*$",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip(":= -|\t")
        else:
            desc_text = re.sub(
                r"(?:[₹$€£¥]|Rs\.?|INR|USD|EUR|GBP)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*$",
                "",
                text,
            ).strip(":= -|\t")
        if not desc_text:
            desc_text = f"Item (line {line.line_number})"

        # Check for embedded MRP, Rate/Item, Discount
        mrp_match = re.search(
            r"\bMRP\b\s*[:=]\s*(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            text,
            re.IGNORECASE,
        )
        rate_match = re.search(
            r"\b(?:Rate(?:/Item)?|Unit\s*Price)\b\s*[:=]\s*(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            text,
            re.IGNORECASE,
        )
        disc_match = re.search(
            r"\bDiscount\b\s*[:=]\s*(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            text,
            re.IGNORECASE,
        )
        disc_pct_match = re.search(
            r"\bDiscount\b\s*[:=]?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*%",
            text,
            re.IGNORECASE,
        )

        mrp_field = None
        if mrp_match:
            mrp_val = float(mrp_match.group(1).replace(",", ""))
            mrp_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_mrp",
                normalized_value=mrp_val,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )

        unit_price_field = None
        if rate_match:
            rate_val = float(rate_match.group(1).replace(",", ""))
            unit_price_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_unit_price",
                normalized_value=rate_val,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )

        disc_field = None
        item_discounts: list[ExtractedField] = []
        if disc_match:
            disc_val = float(disc_match.group(1).replace(",", ""))
            disc_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_discount",
                normalized_value=disc_val,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
            item_discounts.append(disc_field)
        elif disc_pct_match:
            pct = float(disc_pct_match.group(1))
            base_disc = rate_val if rate_match else (mrp_val if mrp_match else amount)
            disc_val = round(base_disc * (pct / 100.0), 2)
            disc_field = ExtractedField(
                field_id=uuid4(),
                field_key="item_discount",
                normalized_value=disc_val,
                unit_or_currency=item_curr,
                confidence=(line.confidence or 0.85),
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=line.page_id,
                    ocr_line_ids=[line.line_id],
                    bounding_box=line.bounding_box,
                    raw_text=line.text,
                ),
            )
            item_discounts.append(disc_field)

        desc_field = ExtractedField(
            field_id=uuid4(),
            field_key="item_description",
            normalized_value=desc_text,
            unit_or_currency=None,
            confidence=(line.confidence or 0.85),
            provenance=FieldProvenance(
                document_id=document_id,
                page_id=line.page_id,
                ocr_line_ids=[line.line_id],
                bounding_box=line.bounding_box,
                raw_text=line.text,
            ),
        )
        total_price_field = ExtractedField(
            field_id=uuid4(),
            field_key="item_total",
            normalized_value=amount,
            unit_or_currency=item_curr,
            confidence=(line.confidence or 0.85),
            provenance=FieldProvenance(
                document_id=document_id,
                page_id=line.page_id,
                ocr_line_ids=[line.line_id],
                bounding_box=line.bounding_box,
                raw_text=line.text,
            ),
        )

        return LineItem(
            item_id=uuid4(),
            description=desc_field,
            unit_price=unit_price_field,
            total_price=total_price_field,
            mrp=mrp_field,
            discount=disc_field,
            discounts=item_discounts,
        )
