"""LLM-assisted structured financial extraction with Gemini / Groq key failover rotation.

Combines high-speed Gemini inference (qwen/qwen3.8-27b) with spatial OCR line geometry.
If all Groq keys are exhausted or network is offline, it gracefully falls back
to the deterministic regex FinancialExtractionEngine.
"""

import json
import logging
import re
from typing import Any
from uuid import UUID, uuid4

from before_you_pay.core.dates import (
    fallback_extract_date,
    verify_date_grounding,
)
from before_you_pay.models import (
    BoundingBox,
    ChargeNature,
    ComponentCategory,
    CoordinateUnit,
    DocumentClassification,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    LineItem,
    OcrLine,
    OcrResult,
    StructuredFinancialDocument,
)
from before_you_pay.services.extraction import (
    FinancialExtractionEngine,
    detect_document_currency,
)
from before_you_pay.services.llm_pool import (
    AllApiKeysExhaustedError,
    GroqKeyManager,
    get_groq_key_manager,
)

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a rigorous, world-class financial document auditor.
Your job is to extract structured financial data from the document text provided.
You must return a valid JSON object matching the requested schema exactly.
Do NOT hallucinate numbers. If an item, shipping, or fee is not explicitly present, use null or 0.0.
Never invent USD if the document is in INR (₹), EUR (€), GBP (£), or any other currency.
"""

EXTRACTION_SCHEMA_INSTRUCTION = """Extract the document into this JSON format:
{
  "vendor_name": "Company/Entity name or null",
  "document_type": "invoice | quotation | contract | bill | subscription | warranty | other",
  "currency": "INR | USD | EUR | GBP | CAD | AUD | null",
  "issued_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "subtotal": 0.0,
  "tax_amount": 0.0,
  "shipping_amount": 0.0,
  "fee_amount": 0.0,
  "discount_amount": 0.0,
  "amount_paid": 0.0,
  "balance_due": 0.0,
  "total_amount": 0.0,
  "cost_breakdown": [
    {
      "name": "Component name (e.g. Ex-showroom, TCS, Insurance, R.C., Warranty, Temp + MSRP, Offer, Extra Offer)",
      "amount": 0.0,
      "category": "base_price | tax | insurance | registration | warranty | accessory_or_fee | discount | other",
      "charge_nature": "charge | deduction",
      "is_optional": false
    }
  ],
  "line_items": [
    {
      "description": "Item or service description",
      "quantity": 1.0,
      "unit_price": 0.0,
      "mrp": null,
      "discount": 0.0,
      "total_price": 0.0
    }
  ],
  "clauses_and_notes": [
    "Any penalty clause, auto-renewal clause, cancellation terms, or warranty period mentioned"
  ]
}

CRITICAL RULES FOR FINANCIAL AUDIT EXTRACTION:
1. Totals:
   - 'subtotal': Pre-tax subtotal or sum of taxable items before discounts/shipping.
   - 'tax_amount': Total invoice tax amount (sum of CGST, SGST, IGST, or VAT amounts in totals section). If SGST is 0.0 and CGST is 0.0, tax_amount is 0.0. Never use an item percentage rate (e.g. 20%) as the invoice tax amount.
   - 'shipping_amount': Itemized shipping/freight/delivery charge if explicitly present, else 0.0.
   - 'discount_amount': Total invoice-level discount or rebate if explicitly present, else 0.0.
   - 'total_amount': Final net payable amount stated on the document.
   - 'amount_paid': Any advance or payments already made if stated, else 0.0.
   - 'balance_due': Remaining net balance payable.
2. Line Items & Table Column Alignment:
   Match standard table columns: Item description, HSN/SKU, Quantity, MRP, Unit Rate, Discount, Tax, Line Amount.
   - 'total_price': Final line amount payable for the item.
   - 'mrp': Maximum retail price column if explicitly present, else null.
   - 'unit_price': Extract the exact printed numeric value from the RATE/ITEM (unit price) column. Never calculate or invent a unit rate (e.g. do not calculate mrp - discount) — preserve the exact printed number from the document so downstream validation can audit extension errors.
   - 'discount': Itemized line discount. If a line item discount column entry is omitted or OCR-shifted, reconcile line discounts against the document total discount so that the sum of line discounts equals the total invoice discount.
3. Date Integrity (Zero Hallucination):
   - ONLY extract dates explicitly written in document text, normalized to ISO (YYYY-MM-DD). If missing, return null. Never fabricate a date or year.
   - For dates written in DD-MM-YYYY format, normalize consistently to YYYY-MM-DD.
4. Quotations & Cost Breakdowns:
   - If the document is a cost sheet, price quotation, vehicle quote, or fee breakdown, classify 'document_type' as 'quotation'.
   - Populate 'cost_breakdown' with every constituent charge and deduction:
     * Positive charges ('charge'): Ex-showroom / base price ('base_price'), statutory taxes / TCS / GST ('tax'), Insurance ('insurance'), Registration / R.C. / Road tax ('registration'), Warranty ('warranty'), Documentation / number plate / ancillary fees ('accessory_or_fee').
     * Negative deductions ('deduction'): Itemized discounts, dealer offers, trade concessions ('discount').
   - 'subtotal': Total before offers / sum of positive constituent charges.
   - 'discount_amount': Total of offers / deductions.
   - 'total_amount': Net quoted total payable after discounts and offers.
   - Numerical Consistency: Verify that individual cost component amounts align with the stated subtotal and resolve ambiguous handwritten digits against spatial arithmetic evidence.
   - For quotations where each line is a cost component (not a retail item with qty/rate), 'line_items' can be empty if 'cost_breakdown' is populated.
"""


def _verify_date_grounding(
    raw_date: Any,
    all_lines: list[OcrLine],
    field_name: str = "date",
) -> tuple[str | None, OcrLine | None]:
    """Verify that an extracted date is grounded in the OCR lines text, never fabricated."""
    return verify_date_grounding(raw_date, all_lines, field_type=field_name)


class HybridLlmExtractionEngine:
    """Enterprise-grade hybrid extractor: Groq LLM with automatic key-pool failover + fallback to regex."""

    def __init__(
        self,
        key_manager: GroqKeyManager | None = None,
        fallback_regex_engine: FinancialExtractionEngine | None = None,
    ) -> None:
        self.key_manager = key_manager or get_groq_key_manager()
        self.fallback_engine = fallback_regex_engine or FinancialExtractionEngine()

    def extract(
        self,
        document_id: UUID,
        user_id: UUID,
        ocr_result: OcrResult,
        document_type_hint: DocumentClassification = DocumentClassification.OTHER,
    ) -> tuple[StructuredFinancialDocument, str]:
        """Extract structured document using Groq failover pool or fallback engine.

        Returns:
            tuple: (StructuredFinancialDocument, extraction_provider_label)
        """
        all_lines: list[OcrLine] = []
        for page in ocr_result.pages:
            all_lines.extend(page.lines)

        if not all_lines:
            logger.warning("Empty OCR result, using deterministic fallback.")
            return (
                self.fallback_engine.extract(document_id, user_id, ocr_result, document_type_hint),
                "FALLBACK_REGEX_EMPTY_OCR",
            )

        # Attempt primary provider extraction if keys configured
        if self.key_manager.key_count > 0:
            try:
                extracted_doc, key_label = self._extract_with_groq(
                    document_id=document_id,
                    user_id=user_id,
                    ocr_result=ocr_result,
                    all_lines=all_lines,
                    document_type_hint=document_type_hint,
                )
                provider_prefix = (
                    "GEMINI"
                    if "gemini" in getattr(self.key_manager, "provider", "gemini")
                    else "GROQ"
                )
                return extracted_doc, f"{provider_prefix}_{key_label}"
            except (AllApiKeysExhaustedError, Exception) as exc:
                logger.warning(
                    "%s extraction failed or exhausted all keys (%s). Checking provider fallback...",
                    getattr(self.key_manager, "provider", "LLM").upper(),
                    str(exc),
                )
                # If primary was Gemini, attempt Groq fallback if configured
                if getattr(self.key_manager, "provider", "gemini") == "gemini":
                    from before_you_pay.config import get_settings
                    from before_you_pay.services.llm_pool import LlmKeyManager

                    settings = get_settings()
                    if settings.groq_api_keys:
                        try:
                            logger.info("Attempting Groq fallback extraction...")
                            groq_km = LlmKeyManager(
                                api_keys=settings.groq_api_keys,
                                provider="groq",
                                model=settings.groq_model,
                            )
                            old_km = self.key_manager
                            self.key_manager = groq_km
                            try:
                                extracted_doc, key_label = self._extract_with_groq(
                                    document_id=document_id,
                                    user_id=user_id,
                                    ocr_result=ocr_result,
                                    all_lines=all_lines,
                                    document_type_hint=document_type_hint,
                                )
                                return extracted_doc, f"GROQ_{key_label}"
                            finally:
                                self.key_manager = old_km
                        except Exception as groq_exc:
                            logger.warning(
                                "Groq fallback extraction also failed (%s). Gracefully degrading to deterministic regex.",
                                str(groq_exc),
                            )

        # Graceful degradation fallback
        return (
            self.fallback_engine.extract(document_id, user_id, ocr_result, document_type_hint),
            "FALLBACK_DETERMINISTIC_REGEX",
        )

    def _extract_with_groq(
        self,
        document_id: UUID,
        user_id: UUID,
        ocr_result: OcrResult,
        all_lines: list[OcrLine],
        document_type_hint: DocumentClassification,
    ) -> tuple[StructuredFinancialDocument, str]:
        """Perform structured extraction using Groq chat completion with JSON mode."""
        lines_text = "\n".join([f"[{idx + 1}] {line.text}" for idx, line in enumerate(all_lines)])
        prompt = f"{EXTRACTION_SCHEMA_INSTRUCTION}\n\nDOCUMENT OCR TEXT:\n{lines_text}"

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        def call_fn(client, model):
            if hasattr(client, "generate_content"):
                return client.generate_content(
                    model=model,
                    prompt=prompt,
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.0,
                )
            # Legacy Groq client fallback
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            return completion.choices[0].message.content or "{}"

        response_content, key_used = self.key_manager.execute_with_failover(call_fn)

        parsed = json.loads(response_content)
        first_page = ocr_result.pages[0]
        default_line_ids = [first_page.lines[0].line_id] if first_page.lines else [uuid4()]
        default_bbox = (
            first_page.lines[0].bounding_box
            if first_page.lines
            else BoundingBox(
                x=0.0,
                y=0.0,
                width=1.0,
                height=0.05,
                coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
            )
        )

        # Determine currency: do NOT invent USD
        currency = parsed.get("currency")
        if not currency or str(currency).strip().upper() in ["NULL", "UNKNOWN", "NONE", ""]:
            currency = detect_document_currency(all_lines)

        # 1. Classification
        raw_type = parsed.get("document_type", "other").lower()
        try:
            detected_type = DocumentClassification(raw_type)
        except ValueError:
            detected_type = document_type_hint or DocumentClassification.OTHER

        # 2. Vendor
        header_vendor = self.fallback_engine._extract_vendor(document_id, ocr_result)
        raw_vendor = parsed.get("vendor_name")
        vendor_name_field = None
        if header_vendor:
            vendor_name_field = header_vendor
        elif raw_vendor and str(raw_vendor).strip():
            matched_line = self._find_matching_line(str(raw_vendor), all_lines)
            vendor_name_field = ExtractedField(
                field_key="vendor_name",
                normalized_value=str(raw_vendor).strip(),
                unit_or_currency=None,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_line.page_id if matched_line else first_page.page_id,
                    ocr_line_ids=[matched_line.line_id] if matched_line else default_line_ids,
                    bounding_box=matched_line.bounding_box if matched_line else default_bbox,
                    raw_text=matched_line.text if matched_line else str(raw_vendor),
                ),
            )
        else:
            vendor_name_field = None

        # 3. Dates (with zero-fabrication grounding check & deterministic fallback)
        raw_issued = parsed.get("issued_date")
        verified_issued, issued_line = _verify_date_grounding(
            raw_issued, all_lines, field_name="issued_date"
        )
        issued_date_field = None
        if verified_issued:
            issued_date_field = ExtractedField(
                field_key="issued_date",
                normalized_value=verified_issued,
                unit_or_currency=None,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=issued_line.page_id if issued_line else first_page.page_id,
                    ocr_line_ids=[issued_line.line_id] if issued_line else default_line_ids,
                    bounding_box=issued_line.bounding_box if issued_line else default_bbox,
                    raw_text=issued_line.text if issued_line else verified_issued,
                ),
            )
        elif not raw_issued or str(raw_issued).strip().upper() not in ["NULL", "NONE", "UNKNOWN"]:
            # Fallback scan for issue/bill date across OCR lines
            fb_issued, fb_line = fallback_extract_date(all_lines, field_type="issued_date")
            if fb_issued and fb_line:
                issued_date_field = ExtractedField(
                    field_key="issued_date",
                    normalized_value=fb_issued,
                    unit_or_currency=None,
                    confidence=0.90,
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=fb_line.page_id,
                        ocr_line_ids=[fb_line.line_id],
                        bounding_box=fb_line.bounding_box,
                        raw_text=fb_line.text,
                    ),
                )

        raw_due = parsed.get("due_date")
        verified_due, due_line = _verify_date_grounding(raw_due, all_lines, field_name="due_date")
        due_date_field = None
        if verified_due:
            due_date_field = ExtractedField(
                field_key="due_date",
                normalized_value=verified_due,
                unit_or_currency=None,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=due_line.page_id if due_line else first_page.page_id,
                    ocr_line_ids=[due_line.line_id] if due_line else default_line_ids,
                    bounding_box=due_line.bounding_box if due_line else default_bbox,
                    raw_text=due_line.text if due_line else verified_due,
                ),
            )
        elif not raw_due or str(raw_due).strip().upper() not in ["NULL", "NONE", "UNKNOWN"]:
            # Fallback scan for due date across OCR lines
            fb_due, fb_due_line = fallback_extract_date(all_lines, field_type="due_date")
            if fb_due and fb_due_line:
                due_date_field = ExtractedField(
                    field_key="due_date",
                    normalized_value=fb_due,
                    unit_or_currency=None,
                    confidence=0.90,
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=fb_due_line.page_id,
                        ocr_line_ids=[fb_due_line.line_id],
                        bounding_box=fb_due_line.bounding_box,
                        raw_text=fb_due_line.text,
                    ),
                )

        # 4. Line Items
        raw_items = parsed.get("line_items", [])
        line_items: list[LineItem] = []
        for idx, item in enumerate(raw_items):
            desc = str(item.get("description", f"Line item {idx + 1}")).strip()
            # Clean secondary serial numbers, IMEIs, or accessory descriptions from primary product title
            desc = (
                re.sub(
                    r"[\s(]+(?:IMEI|Product\s*ID|Serial(?:\s*No\.?)?|S/N|Model(?:\s*No\.?)?|Bluetooth\s*Speaker)\b.*$",
                    "",
                    desc,
                    flags=re.IGNORECASE,
                )
                .strip()
                .rstrip("()-: ")
            )
            qty = float(item.get("quantity") or 1.0)
            rate = float(item.get("unit_price") or 0.0)
            item_tot = float(item.get("total_price") or (qty * rate))
            raw_mrp = item.get("mrp")
            mrp_val = float(raw_mrp) if raw_mrp is not None else None
            raw_disc = item.get("discount")
            disc_val = float(raw_disc) if raw_disc is not None else None

            # Reconcile MRP via standard accounting equation if omitted or obstructed in OCR
            if mrp_val is None and rate > 0 and disc_val is not None and disc_val > 0:
                mrp_val = round(rate + disc_val, 2)

            matched_line = self._find_matching_line(desc, all_lines)
            line_prov = FieldProvenance(
                document_id=document_id,
                page_id=matched_line.page_id if matched_line else first_page.page_id,
                ocr_line_ids=[matched_line.line_id] if matched_line else default_line_ids,
                bounding_box=matched_line.bounding_box if matched_line else default_bbox,
                raw_text=matched_line.text if matched_line else desc,
            )

            mrp_field = None
            if mrp_val is not None:
                mrp_field = ExtractedField(
                    field_key=f"line_item_{idx}_mrp",
                    normalized_value=mrp_val,
                    unit_or_currency=currency,
                    confidence=0.90,
                    provenance=line_prov,
                )

            disc_field = None
            item_discounts: list[ExtractedField] = []
            if disc_val is not None:
                disc_field = ExtractedField(
                    field_key=f"line_item_{idx}_discount",
                    normalized_value=disc_val,
                    unit_or_currency=currency,
                    confidence=0.90,
                    provenance=line_prov,
                )
                item_discounts.append(disc_field)

            line_items.append(
                LineItem(
                    description=ExtractedField(
                        field_key=f"line_item_{idx}_desc",
                        normalized_value=desc,
                        confidence=0.90,
                        provenance=line_prov,
                    ),
                    quantity=ExtractedField(
                        field_key=f"line_item_{idx}_qty",
                        normalized_value=qty,
                        confidence=0.90,
                        provenance=line_prov,
                    ),
                    unit_price=ExtractedField(
                        field_key=f"line_item_{idx}_rate",
                        normalized_value=rate,
                        unit_or_currency=currency,
                        confidence=0.90,
                        provenance=line_prov,
                    ),
                    total_price=ExtractedField(
                        field_key=f"line_item_{idx}_total",
                        normalized_value=item_tot,
                        unit_or_currency=currency,
                        confidence=0.90,
                        provenance=line_prov,
                    ),
                    mrp=mrp_field,
                    discount=disc_field,
                    discounts=item_discounts,
                )
            )

        # Parse cost breakdown components for quotations and cost sheets
        raw_components = parsed.get("cost_breakdown", [])
        cost_breakdown: list[FinancialComponent] = []
        for c_idx, comp in enumerate(raw_components):
            raw_comp_name = str(comp.get("name") or "").strip()
            comp_amt = float(comp.get("amount") or 0.0)

            # Match provenance line
            matched_comp_line = (
                self._find_matching_line(raw_comp_name, all_lines) if raw_comp_name else None
            )
            if not matched_comp_line and comp_amt > 0:
                amt_str = str(int(comp_amt)) if comp_amt.is_integer() else f"{comp_amt:.2f}"
                for ln in all_lines:
                    cleaned_line = (
                        ln.text.replace(",", "").replace(" ", "").replace("=", "").replace("-", "")
                    )
                    if amt_str in cleaned_line:
                        matched_comp_line = ln
                        break

            # If name is generic or missing, recover genuine label from matched OCR line
            is_generic = (
                not raw_comp_name
                or raw_comp_name.lower().startswith("component")
                or raw_comp_name.lower().startswith("financial component")
                or raw_comp_name.lower() in ["other charge", "detected amount"]
            )
            if is_generic and matched_comp_line:
                from before_you_pay.services.financial_taxonomy import clean_component_text

                recovered_label = clean_component_text(matched_comp_line.text)
                comp_name = recovered_label or raw_comp_name or "Unclear"
            else:
                comp_name = raw_comp_name or "Unclear"

            comp_cat_raw = str(comp.get("category", "unclear")).lower().strip()
            try:
                comp_cat = ComponentCategory(comp_cat_raw)
            except ValueError:
                comp_cat = ComponentCategory.UNCLEAR

            comp_nature_raw = str(comp.get("charge_nature", "charge")).lower().strip()
            name_lower = comp_name.lower()
            if any(
                term in name_lower
                for term in [
                    "offer",
                    "discount",
                    "rebate",
                    "deduction",
                    "concession",
                    "less",
                    "minus",
                ]
            ):
                comp_nature = ChargeNature.DEDUCTION
            else:
                comp_nature = (
                    ChargeNature.DEDUCTION
                    if comp_nature_raw in ["deduction", "discount", "negative", "minus", "offer"]
                    else ChargeNature.CHARGE
                )
            is_optional = bool(comp.get("is_optional", False))

            comp_prov = FieldProvenance(
                document_id=document_id,
                page_id=matched_comp_line.page_id if matched_comp_line else first_page.page_id,
                ocr_line_ids=[matched_comp_line.line_id] if matched_comp_line else default_line_ids,
                bounding_box=matched_comp_line.bounding_box if matched_comp_line else default_bbox,
                raw_text=matched_comp_line.text
                if matched_comp_line
                else f"{comp_name}: {comp_amt}",
            )

            amt_field = ExtractedField(
                field_key=f"cost_component_{c_idx}_amount",
                normalized_value=comp_amt,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=comp_prov,
            )

            cost_breakdown.append(
                FinancialComponent(
                    component_id=uuid4(),
                    name=comp_name,
                    raw_name=matched_comp_line.text if matched_comp_line else comp_name,
                    raw_label=comp_name,
                    normalized_label=comp.get("normalized_label") or comp.get("normalized_name"),
                    amount=amt_field,
                    category=comp_cat,
                    charge_nature=comp_nature,
                    is_optional=is_optional,
                    source_ocr_line=str(matched_comp_line.line_id)
                    if matched_comp_line
                    else (str(default_line_ids[0]) if default_line_ids else None),
                    bounding_box=matched_comp_line.bounding_box
                    if matched_comp_line
                    else default_bbox,
                    page=first_page.page_number if hasattr(first_page, "page_number") else 1,
                    evidence=matched_comp_line.text
                    if matched_comp_line
                    else f"{comp_name}: {comp_amt}",
                )
            )

        # If LLM returned no line items and no cost breakdown, recover line items from spatial OCR lines
        if not line_items and not cost_breakdown:
            line_items = self.fallback_engine._extract_line_items(document_id, all_lines, currency)

        # 5. Financial Totals (Subtotal, Tax, Shipping, Fees, Discounts, Paid, Balance, Total)
        raw_sub = float(parsed.get("subtotal") or 0.0)
        subtotal_field = None
        if raw_sub > 0.0:
            matched_sub = self._find_matching_pattern(r"subtotal|taxable", all_lines)
            subtotal_field = ExtractedField(
                field_key="subtotal",
                normalized_value=raw_sub,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_sub.page_id if matched_sub else first_page.page_id,
                    ocr_line_ids=[matched_sub.line_id] if matched_sub else default_line_ids,
                    bounding_box=matched_sub.bounding_box if matched_sub else default_bbox,
                    raw_text=matched_sub.text if matched_sub else str(raw_sub),
                ),
            )
        else:
            subtotal_field = self.fallback_engine._extract_subtotal(document_id, all_lines)

        raw_tax = float(parsed.get("tax_amount") or 0.0)
        tax_field = None
        if raw_tax > 0.0 or parsed.get("tax_amount") is not None:
            matched_tax = self._find_matching_pattern(r"tax|cgst|sgst|vat|gst", all_lines)
            tax_field = ExtractedField(
                field_key="tax_amount",
                normalized_value=raw_tax,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_tax.page_id if matched_tax else first_page.page_id,
                    ocr_line_ids=[matched_tax.line_id] if matched_tax else default_line_ids,
                    bounding_box=matched_tax.bounding_box if matched_tax else default_bbox,
                    raw_text=matched_tax.text if matched_tax else str(raw_tax),
                ),
            )
        else:
            tax_field = self.fallback_engine._extract_tax(document_id, all_lines)

        # Shipping
        raw_ship = float(parsed.get("shipping_amount") or 0.0)
        shipping_field = None
        if raw_ship > 0.0:
            matched_ship = self._find_matching_pattern(r"shipping|delivery|freight", all_lines)
            shipping_field = ExtractedField(
                field_key="shipping_amount",
                normalized_value=raw_ship,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_ship.page_id if matched_ship else first_page.page_id,
                    ocr_line_ids=[matched_ship.line_id] if matched_ship else default_line_ids,
                    bounding_box=matched_ship.bounding_box if matched_ship else default_bbox,
                    raw_text=matched_ship.text if matched_ship else str(raw_ship),
                ),
            )
        else:
            shipping_field = self.fallback_engine._extract_shipping(document_id, all_lines)

        # Document-level discount
        raw_disc = float(parsed.get("discount_amount") or 0.0)
        discount_field = None
        if raw_disc > 0.0:
            matched_disc = self._find_matching_pattern(r"discount|rebate", all_lines)
            discount_field = ExtractedField(
                field_key="discount_amount",
                normalized_value=raw_disc,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_disc.page_id if matched_disc else first_page.page_id,
                    ocr_line_ids=[matched_disc.line_id] if matched_disc else default_line_ids,
                    bounding_box=matched_disc.bounding_box if matched_disc else default_bbox,
                    raw_text=matched_disc.text if matched_disc else str(raw_disc),
                ),
            )
        else:
            discount_field = self.fallback_engine._extract_discount(document_id, all_lines)

        # Deterministic reconciliation of unallocated invoice discount across line items:
        # If invoice specifies a total discount amount, but one line item's discount was missed/set to 0 by OCR column misalignment
        if discount_field and float(discount_field.normalized_value or 0.0) > 0:
            tot_inv_disc = float(discount_field.normalized_value)
            explicit_item_disc_sum = sum(
                float(li.discount.normalized_value)
                for li in line_items
                if li.discount and float(li.discount.normalized_value or 0.0) > 0
            )
            unallocated_disc = round(tot_inv_disc - explicit_item_disc_sum, 2)
            if unallocated_disc > 0:
                zero_disc_items = [
                    li
                    for li in line_items
                    if not li.discount or float(li.discount.normalized_value or 0.0) == 0.0
                ]
                if len(zero_disc_items) == 1:
                    target_li = zero_disc_items[0]
                    reconciled_disc_field = ExtractedField(
                        field_key=f"{target_li.description.field_key.replace('_desc', '')}_discount",
                        normalized_value=unallocated_disc,
                        unit_or_currency=currency,
                        confidence=0.90,
                        provenance=target_li.description.provenance,
                    )
                    target_idx = line_items.index(target_li)
                    reconciled_li = target_li.model_copy(
                        update={
                            "discount": reconciled_disc_field,
                            "discounts": [reconciled_disc_field],
                        }
                    )
                    line_items[target_idx] = reconciled_li

        # Amount paid
        raw_paid = parsed.get("amount_paid")
        amount_paid_field = None
        if raw_paid is not None:
            paid_val = float(raw_paid)
            matched_paid = self._find_matching_pattern(r"paid|advance", all_lines)
            amount_paid_field = ExtractedField(
                field_key="amount_paid",
                normalized_value=paid_val,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_paid.page_id if matched_paid else first_page.page_id,
                    ocr_line_ids=[matched_paid.line_id] if matched_paid else default_line_ids,
                    bounding_box=matched_paid.bounding_box if matched_paid else default_bbox,
                    raw_text=matched_paid.text if matched_paid else str(paid_val),
                ),
            )
        else:
            amount_paid_field = self.fallback_engine._extract_amount_paid(document_id, all_lines)

        # Balance due
        raw_bal = parsed.get("balance_due")
        balance_due_field = None
        if raw_bal is not None and float(raw_bal) > 0.0:
            bal_val = float(raw_bal)
            matched_bal = self._find_matching_pattern(r"balance\s*due|net\s*payable", all_lines)
            balance_due_field = ExtractedField(
                field_key="balance_due",
                normalized_value=bal_val,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_bal.page_id if matched_bal else first_page.page_id,
                    ocr_line_ids=[matched_bal.line_id] if matched_bal else default_line_ids,
                    bounding_box=matched_bal.bounding_box if matched_bal else default_bbox,
                    raw_text=matched_bal.text if matched_bal else str(bal_val),
                ),
            )
        else:
            balance_due_field = self.fallback_engine._extract_balance_due(document_id, all_lines)

        # Ancillary fees (for retail invoices; in quotations these are captured in cost_breakdown)
        raw_fee = float(parsed.get("fee_amount") or 0.0)
        fees: list[ExtractedField] = []
        if raw_fee > 0.0 and not cost_breakdown:
            fees.append(
                ExtractedField(
                    field_key="fee_surcharge",
                    normalized_value=raw_fee,
                    unit_or_currency=currency,
                    confidence=0.90,
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=first_page.page_id,
                        ocr_line_ids=default_line_ids,
                        bounding_box=default_bbox,
                        raw_text=str(raw_fee),
                    ),
                )
            )

        # Stated Total Amount
        raw_total = float(parsed.get("total_amount") or 0.0)
        fallback_total_field = self.fallback_engine._extract_total(document_id, all_lines)

        if raw_total > 0.0:
            matched_tot = self._find_matching_pattern(r"total", all_lines)
            total_field = ExtractedField(
                field_key="total_amount",
                normalized_value=raw_total,
                unit_or_currency=currency,
                confidence=0.95,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_tot.page_id if matched_tot else first_page.page_id,
                    ocr_line_ids=[matched_tot.line_id] if matched_tot else default_line_ids,
                    bounding_box=matched_tot.bounding_box if matched_tot else default_bbox,
                    raw_text=matched_tot.text if matched_tot else str(raw_total),
                ),
            )
        elif fallback_total_field is not None:
            total_field = fallback_total_field
        elif balance_due_field is not None:
            total_field = ExtractedField(
                field_key="total_amount",
                normalized_value=float(balance_due_field.normalized_value),
                unit_or_currency=currency,
                confidence=balance_due_field.confidence,
                provenance=balance_due_field.provenance,
            )
        elif cost_breakdown:
            charges = sum(
                float(c.amount.normalized_value or 0.0)
                for c in cost_breakdown
                if getattr(c.charge_nature, "is_additive", c.charge_nature == ChargeNature.CHARGE)
            )
            deductions = sum(
                float(c.amount.normalized_value or 0.0)
                for c in cost_breakdown
                if getattr(
                    c.charge_nature, "is_deduction", c.charge_nature == ChargeNature.DEDUCTION
                )
            )
            net_total = round(charges - deductions, 2)
            total_field = ExtractedField(
                field_key="total_amount",
                normalized_value=net_total,
                unit_or_currency=currency,
                confidence=0.90,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=first_page.page_id,
                    ocr_line_ids=default_line_ids,
                    bounding_box=default_bbox,
                    raw_text=f"Net Quoted Total: {net_total}",
                ),
            )
        else:
            computed_items = sum(float(it.total_price.normalized_value or 0.0) for it in line_items)
            ship_amt = float(shipping_field.normalized_value) if shipping_field else 0.0
            tax_amt = float(tax_field.normalized_value) if tax_field else 0.0
            total_field = ExtractedField(
                field_key="total_amount",
                normalized_value=round(computed_items + ship_amt + tax_amt + raw_fee, 2),
                unit_or_currency=currency,
                confidence=0.90,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=first_page.page_id,
                    ocr_line_ids=default_line_ids,
                    bounding_box=default_bbox,
                    raw_text="Computed Total",
                ),
            )

        # Backfill subtotal / discount_amount if omitted by LLM but present in cost_breakdown
        if (
            subtotal_field is None or float(subtotal_field.normalized_value or 0.0) == 0.0
        ) and cost_breakdown:
            charges_sum = sum(
                float(c.amount.normalized_value or 0.0)
                for c in cost_breakdown
                if getattr(c.charge_nature, "is_additive", c.charge_nature == ChargeNature.CHARGE)
            )
            if charges_sum > 0:
                subtotal_field = ExtractedField(
                    field_key="subtotal",
                    normalized_value=round(charges_sum, 2),
                    unit_or_currency=currency,
                    confidence=0.90,
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=first_page.page_id,
                        ocr_line_ids=default_line_ids,
                        bounding_box=default_bbox,
                        raw_text=f"Subtotal Before Offers: {charges_sum}",
                    ),
                )

        if (
            discount_field is None or float(discount_field.normalized_value or 0.0) == 0.0
        ) and cost_breakdown:
            deductions_sum = sum(
                float(c.amount.normalized_value or 0.0)
                for c in cost_breakdown
                if getattr(
                    c.charge_nature, "is_deduction", c.charge_nature == ChargeNature.DEDUCTION
                )
            )
            if deductions_sum > 0:
                discount_field = ExtractedField(
                    field_key="discount_amount",
                    normalized_value=round(deductions_sum, 2),
                    unit_or_currency=currency,
                    confidence=0.90,
                    provenance=FieldProvenance(
                        document_id=document_id,
                        page_id=first_page.page_id,
                        ocr_line_ids=default_line_ids,
                        bounding_box=default_bbox,
                        raw_text=f"Total Offers: {deductions_sum}",
                    ),
                )

        # 6. Clauses and Notes
        clauses_list = parsed.get("clauses_and_notes", [])
        extracted_clauses: list[ExtractedField] = []
        for c_idx, clause in enumerate(clauses_list):
            if clause and str(clause).strip():
                extracted_clauses.append(
                    ExtractedField(
                        field_key=f"clause_{c_idx}",
                        normalized_value=str(clause).strip(),
                        confidence=0.90,
                        provenance=FieldProvenance(
                            document_id=document_id,
                            page_id=first_page.page_id,
                            ocr_line_ids=default_line_ids,
                            bounding_box=default_bbox,
                            raw_text=str(clause),
                        ),
                    )
                )

        # Determine payment status
        payment_status_field = None
        raw_status = parsed.get("payment_status")
        if raw_status and str(raw_status).strip():
            matched_stat = self._find_matching_pattern(r"status|paid|unpaid|due", all_lines)
            payment_status_field = ExtractedField(
                field_key="payment_status",
                normalized_value=str(raw_status).lower().strip(),
                confidence=0.90,
                provenance=FieldProvenance(
                    document_id=document_id,
                    page_id=matched_stat.page_id if matched_stat else first_page.page_id,
                    ocr_line_ids=[matched_stat.line_id] if matched_stat else default_line_ids,
                    bounding_box=matched_stat.bounding_box if matched_stat else default_bbox,
                    raw_text=matched_stat.text if matched_stat else str(raw_status),
                ),
            )
        elif balance_due_field is not None and float(balance_due_field.normalized_value) == 0.0:
            payment_status_field = ExtractedField(
                field_key="payment_status",
                normalized_value="paid",
                confidence=balance_due_field.confidence,
                provenance=balance_due_field.provenance,
            )
        elif (
            amount_paid_field is not None
            and float(amount_paid_field.normalized_value) > 0.0
            and (balance_due_field is None or float(balance_due_field.normalized_value) > 0.0)
        ):
            payment_status_field = ExtractedField(
                field_key="payment_status",
                normalized_value="partial",
                confidence=amount_paid_field.confidence,
                provenance=amount_paid_field.provenance,
            )
        elif balance_due_field is not None and float(balance_due_field.normalized_value) > 0.0:
            payment_status_field = ExtractedField(
                field_key="payment_status",
                normalized_value="unpaid",
                confidence=balance_due_field.confidence,
                provenance=balance_due_field.provenance,
            )
        elif total_field is not None and float(total_field.normalized_value) > 0.0:
            payment_status_field = ExtractedField(
                field_key="payment_status",
                normalized_value="unpaid",
                confidence=total_field.confidence,
                provenance=total_field.provenance,
            )
        else:
            payment_status_field = None

        doc = StructuredFinancialDocument(
            document_id=document_id,
            user_id=user_id,
            document_type=detected_type,
            currency=currency,
            vendor_name=vendor_name_field,
            vendor_tax_id=None,
            issued_date=issued_date_field,
            due_date=due_date_field,
            period_start=None,
            period_end=None,
            line_items=line_items,
            cost_breakdown=cost_breakdown,
            subtotal=subtotal_field,
            tax_amount=tax_field,
            shipping_amount=shipping_field,
            discount_amount=discount_field,
            amount_paid=amount_paid_field,
            balance_due=balance_due_field,
            payment_status=payment_status_field,
            fees=fees,
            total_amount=total_field,
            clauses_and_notes=extracted_clauses,
        )
        return doc, key_used

    def _find_matching_line(self, target_text: str, lines: list[OcrLine]) -> OcrLine | None:
        """Find the OCR line that most closely contains or matches the target text."""
        target_lower = target_text.lower()
        for line in lines:
            if target_lower in line.text.lower() or line.text.lower() in target_lower:
                return line
        return None

    def _find_matching_pattern(self, pattern_str: str, lines: list[OcrLine]) -> OcrLine | None:
        """Find the OCR line that matches a regular expression pattern."""
        pat = re.compile(pattern_str, re.IGNORECASE)
        for line in lines:
            if pat.search(line.text):
                return line
        return None
