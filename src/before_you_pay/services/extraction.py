"""Structured financial extraction engine parsing OCR lines into normalized fields."""

import re
from uuid import UUID, uuid4

from before_you_pay.core.dates import fallback_extract_date
from before_you_pay.core.errors import ContractViolationException
from before_you_pay.models import (
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    LineItem,
    OcrLine,
    OcrResult,
    StructuredFinancialDocument,
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
    # Short lines with only a number (e.g. page numbers)
    if re.fullmatch(r"\d{1,6}", text_stripped):
        return True
    # Table header line (all header columns, no data)
    if re.search(r"\bitems?\s+hsn\b", text_lower):
        return True
    if any(
        k in text_lower
        for k in ["place of supply:", "vat no", "gstin :", "vehicle no. :", "total amount in words"]
    ):
        return True
    if text_lower.startswith(("phone:", "phone :", "mobile:", "mobile :", "address:")):
        return True
    # Lines that are primarily a date
    if DATE_PATTERN.search(text_stripped):
        remaining = DATE_PATTERN.sub("", text_stripped).strip(":= -/")
        if re.fullmatch(
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
        for page in ocr_result.pages:
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

        # Parse line entries
        for line in all_lines:
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
            if TAX_LABEL_PATTERN.search(text_lower):
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

            # 9. Contractual clauses requiring attention
            if any(
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

            # 10. Candidate itemized line item
            # Skip document metadata lines (invoice numbers, dates, page refs)
            if _is_metadata_line(line.text):
                continue
            amount = self._parse_amount(line.text)
            if amount is not None and amount > 0:
                item = self._build_line_item(document_id, line, amount, doc_currency)
                line_items.append(item)

        # Fallback tax_amount if individual tax components were itemized
        if tax_field is None and taxes:
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

        for line in ocr_result.pages[0].lines[:5]:
            clean_text = line.text.strip()
            if len(clean_text) < 2 or clean_text.lower() in generic_headings:
                continue
            if re.match(r"^(invoice|quote|bill|date|total|page|statement)\b", clean_text.lower()):
                continue

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
        for line in lines:
            text_lower = line.text.lower()
            if TAX_LABEL_PATTERN.search(text_lower):
                amount = self._parse_amount(line.text)
                if amount is not None:
                    return ExtractedField(
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

    def _parse_amount(self, text: str) -> float | None:
        """Extract numeric amount from text line, preserving integers, decimals, and Indian numbering."""
        # 1. Look for explicit currency symbol followed or preceded by amount
        symbol_pattern = re.compile(
            r"(?:[₹$€£¥]|Rs\.?|INR|USD|EUR|GBP|CAD|AUD)\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            re.IGNORECASE,
        )
        sym_matches = symbol_pattern.findall(text)
        if sym_matches:
            val_str = sym_matches[-1].replace(",", "")
            try:
                return float(val_str)
            except ValueError:
                pass

        # 2. Look for assignment or colon: e.g. "= 499" or ": 499" or "= 29,497"
        assign_pattern = re.compile(
            r"[:=]\s*(?:[₹$€£¥]|Rs\.?|INR|USD)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*$",
            re.IGNORECASE,
        )
        assign_match = assign_pattern.search(text.strip())
        if assign_match:
            try:
                return float(assign_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # 3. Look for general numeric values in the line (take the last one)
        general_pattern = re.compile(
            r"\b([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\b"
        )
        all_num_matches = general_pattern.findall(text)
        if all_num_matches:
            val_str = all_num_matches[-1].replace(",", "")
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
