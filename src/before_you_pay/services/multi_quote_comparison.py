"""Phase 1A: N-way multi-document comparison service.

Compares 2–5 quotations for the same purchase by aligning components
across documents and computing per-component and total deltas using
deterministic Python arithmetic.

Design principles:
- Pure deterministic arithmetic for all numerical calculations and deltas.
- Canonical classification alignment using financial taxonomy keywords.
- Strict non-committal, objective language (no advice, recommendations, or accusations).
- Full data provenance preserved for every aligned component cell.
- Never converts MISSING/UNKNOWN amounts to zero.
- Currency mismatch detection and safe handling.
"""

from __future__ import annotations

import re
from uuid import UUID

from before_you_pay.models.document import (
    StructuredFinancialDocument,
)
from before_you_pay.models.multi_quote_comparison import (
    AlignedComponentCell,
    AlignedFinancialComponent,
    InclusionExclusionFinding,
    MultiQuoteComparisonResult,
    QuoteSummary,
)

# Canonical component categories with keyword matchers for vehicle and generic quotes
CANONICAL_CATEGORIES: list[tuple[str, str, list[str]]] = [
    (
        "ex_showroom",
        "Ex-Showroom / Base Price",
        [
            "ex showroom",
            "ex-showroom",
            "exshowroom",
            "base price",
            "vehicle price",
            "unit price",
            "basic cost",
        ],
    ),
    (
        "road_tax",
        "Road Tax / Registration / RTO",
        [
            "road tax",
            "roadtax",
            "rto",
            "registration",
            "mv tax",
            "m.v. tax",
            "motor vehicle tax",
            "one time tax",
            "life time tax",
        ],
    ),
    (
        "insurance",
        "Insurance (Comprehensive / Zero Dep)",
        ["insurance", "insure", "policy", "premium", "zero dep", "nil dep", "1+3", "b2b insurance"],
    ),
    (
        "handling_charges",
        "Handling / Incidental / PDI Charges",
        [
            "handling",
            "incidental",
            "depot",
            "logistic",
            "logistics",
            "pdi",
            "p.d.i",
            "documentation charge",
        ],
    ),
    (
        "extended_warranty",
        "Extended Warranty",
        ["extended warranty", "warranty", "ew", "rsa", "roadside assistance", "shield of trust"],
    ),
    (
        "accessories",
        "Accessories / Basic Kit",
        [
            "accessories",
            "accessory",
            "essential kit",
            "basic kit",
            "mats",
            "mud flaps",
            "body cover",
        ],
    ),
    (
        "fastag_hsrp",
        "Fastag / HSRP / Number Plate",
        ["fastag", "fas tag", "hsrp", "h.s.r.p", "number plate", "smart card"],
    ),
    (
        "tcs_tax",
        "TCS / Statutory Taxes",
        ["tcs", "tax collected at source", "gst", "cess"],
    ),
    (
        "discounts_offers",
        "Discounts / Special Offers",
        [
            "discount",
            "discounts",
            "offer",
            "offers",
            "consumer offer",
            "exchange bonus",
            "cash discount",
            "rebate",
            "concession",
            "disc",
        ],
    ),
    (
        "service_maintenance",
        "Service / Maintenance / AMC Package",
        ["amc", "annual maintenance", "service package", "maintenance package", "care package"],
    ),
]


def _match_category(label: str) -> tuple[str, str]:
    """Match a raw component label to a canonical category ID and display name."""
    norm = label.lower().strip()
    for cat_id, display_name, keywords in CANONICAL_CATEGORIES:
        for kw in keywords:
            if kw in norm:
                return cat_id, display_name
    return "other_charges", "Other / Miscellaneous Charges"


class MultiQuoteComparisonService:
    """Service to compare 2 to 5 quotations simultaneously."""

    def compare(
        self,
        documents: list[StructuredFinancialDocument],
        user_id: UUID,
    ) -> MultiQuoteComparisonResult:
        """Perform N-way quotation alignment and deterministic variance analysis."""
        if len(documents) < 2:
            raise ValueError(
                f"At least 2 documents required for multi-quote comparison, got {len(documents)}"
            )
        if len(documents) > 5:
            raise ValueError(
                f"Maximum of 5 documents supported for multi-quote comparison, got {len(documents)}"
            )

        # 1. Build Quote Summaries and Currency Validation
        quotes: list[QuoteSummary] = []
        currencies: set[str] = set()
        totals_by_doc_id: dict[str, float | None] = {}

        for doc in documents:
            doc_id_str = str(doc.document_id)
            doc_curr = (doc.currency or "INR").upper()
            currencies.add(doc_curr)

            vendor = "Unknown Vendor"
            if doc.vendor_name:
                if doc.vendor_name.normalized_value:
                    vendor = str(doc.vendor_name.normalized_value)
                elif doc.vendor_name.raw_value:
                    vendor = str(doc.vendor_name.raw_value)

            doc_date = None
            if doc.issued_date:
                if doc.issued_date.normalized_value:
                    doc_date = str(doc.issued_date.normalized_value)
                elif doc.issued_date.raw_value:
                    doc_date = str(doc.issued_date.raw_value)

            total_val = None
            if doc.total_amount:
                if doc.total_amount.normalized_value is not None:
                    try:
                        total_val = float(doc.total_amount.normalized_value)
                    except (ValueError, TypeError):
                        total_val = None
                elif doc.total_amount.raw_value:
                    try:
                        clean_num = re.sub(r"[^\d.]", "", str(doc.total_amount.raw_value))
                        total_val = float(clean_num) if clean_num else None
                    except (ValueError, TypeError):
                        total_val = None

            totals_by_doc_id[doc_id_str] = total_val
            item_count = len(doc.cost_breakdown) if doc.cost_breakdown else len(doc.line_items)

            quotes.append(
                QuoteSummary(
                    document_id=doc.document_id,
                    vendor_name=vendor,
                    document_date=doc_date,
                    currency=doc_curr,
                    total_amount=total_val,
                    item_count=item_count,
                    filename=None,
                )
            )

        currency_mismatch = len(currencies) > 1
        primary_curr = quotes[0].currency

        # 2. Extract and Align Financial Components
        category_components: dict[str, dict[str, AlignedComponentCell]] = {}
        category_display_names: dict[str, str] = {}

        for doc in documents:
            doc_id_str = str(doc.document_id)
            components = doc.cost_breakdown if doc.cost_breakdown else []

            # If cost_breakdown is empty, fallback to line_items
            if not components and doc.line_items:
                for li in doc.line_items:
                    raw_label = (
                        li.description.raw_value
                        if (li.description and li.description.raw_value)
                        else "Line Item"
                    )
                    cat_id, disp_name = _match_category(raw_label)
                    category_display_names[cat_id] = disp_name

                    amt_val = None
                    amt_state = "UNKNOWN"
                    if li.total_amount:
                        if hasattr(li.total_amount, "state"):
                            amt_state = (
                                li.total_amount.state.value
                                if hasattr(li.total_amount.state, "value")
                                else str(li.total_amount.state)
                            )
                        if li.total_amount.normalized_value is not None:
                            try:
                                amt_val = float(li.total_amount.normalized_value)
                            except (ValueError, TypeError):
                                amt_val = None

                    cell = AlignedComponentCell(
                        document_id=doc.document_id,
                        is_present=True,
                        raw_label=raw_label,
                        amount=amt_val,
                        amount_state=amt_state,
                        is_included_in_total=True,
                    )
                    if cat_id not in category_components:
                        category_components[cat_id] = {}
                    category_components[cat_id][doc_id_str] = cell

            for comp in components:
                raw_label = comp.raw_label or comp.raw_text or comp.name or "Item"
                cat_id, disp_name = _match_category(raw_label)
                category_display_names[cat_id] = disp_name

                amt_val = None
                amt_state = "UNKNOWN"
                if comp.amount is not None:
                    if hasattr(comp.amount, "state"):
                        amt_state = (
                            comp.amount.state.value
                            if hasattr(comp.amount.state, "value")
                            else str(comp.amount.state)
                        )
                    if (
                        hasattr(comp.amount, "normalized_value")
                        and comp.amount.normalized_value is not None
                    ):
                        try:
                            amt_val = float(comp.amount.normalized_value)
                        except (ValueError, TypeError):
                            amt_val = None
                    elif isinstance(comp.amount, (int, float)):
                        amt_val = float(comp.amount)
                        amt_state = "PRESENT"

                cell = AlignedComponentCell(
                    document_id=doc.document_id,
                    is_present=True,
                    raw_label=raw_label,
                    amount=amt_val,
                    amount_state=amt_state,
                    is_included_in_total=True,
                    page_number=comp.page or 1,
                    bounding_box=comp.bounding_box,
                )

                if cat_id not in category_components:
                    category_components[cat_id] = {}

                # If already present for this doc, aggregate amount if numeric
                if doc_id_str in category_components[cat_id]:
                    existing = category_components[cat_id][doc_id_str]
                    if existing.amount is not None and amt_val is not None:
                        new_amt = round(existing.amount + amt_val, 2)
                        category_components[cat_id][doc_id_str] = AlignedComponentCell(
                            document_id=doc.document_id,
                            is_present=True,
                            raw_label=f"{existing.raw_label} + {raw_label}",
                            amount=new_amt,
                            amount_state="PRESENT",
                            is_included_in_total=True,
                            page_number=comp.page or existing.page_number,
                            bounding_box=comp.bounding_box or existing.bounding_box,
                        )
                else:
                    category_components[cat_id][doc_id_str] = cell

        # 3. Build AlignedFinancialComponent list with deterministic min/max/delta
        aligned_list: list[AlignedFinancialComponent] = []
        inclusions_exclusions: list[InclusionExclusionFinding] = []

        # Order categories by CANONICAL_CATEGORIES priority
        ordered_cat_ids = [c[0] for c in CANONICAL_CATEGORIES]
        for extra_cat in category_components:
            if extra_cat not in ordered_cat_ids:
                ordered_cat_ids.append(extra_cat)

        for cat_id in ordered_cat_ids:
            if cat_id not in category_components:
                continue

            doc_cells = category_components[cat_id]
            disp_name = category_display_names.get(cat_id, cat_id.replace("_", " ").title())

            cells_map: dict[str, AlignedComponentCell] = {}
            numeric_amounts: list[float] = []
            present_doc_ids: list[UUID] = []
            absent_doc_ids: list[UUID] = []

            for doc in documents:
                d_id_str = str(doc.document_id)
                if d_id_str in doc_cells:
                    c = doc_cells[d_id_str]
                    cells_map[d_id_str] = c
                    present_doc_ids.append(doc.document_id)
                    if c.amount is not None:
                        numeric_amounts.append(c.amount)
                else:
                    cells_map[d_id_str] = AlignedComponentCell(
                        document_id=doc.document_id,
                        is_present=False,
                        raw_label=None,
                        amount=None,
                        amount_state="NOT_APPLICABLE",
                        is_included_in_total=False,
                    )
                    absent_doc_ids.append(doc.document_id)

            min_amt = min(numeric_amounts) if numeric_amounts else None
            max_amt = max(numeric_amounts) if numeric_amounts else None
            delta_amt = (
                round(max_amt - min_amt, 2)
                if (min_amt is not None and max_amt is not None)
                else None
            )
            has_presence_var = len(present_doc_ids) > 0 and len(absent_doc_ids) > 0

            aligned = AlignedFinancialComponent(
                canonical_category=cat_id,
                display_name=disp_name,
                cells=cells_map,
                min_amount=min_amt,
                max_amount=max_amt,
                delta_amount=delta_amt,
                presence_variance=has_presence_var,
            )
            aligned_list.append(aligned)

            # Inclusion / Exclusion findings
            if has_presence_var:
                present_names = [q.vendor_name for q in quotes if q.document_id in present_doc_ids]
                absent_names = [q.vendor_name for q in quotes if q.document_id in absent_doc_ids]
                cost_diff = max_amt if max_amt is not None else None
                diff_str = f" ({primary_curr} {cost_diff:,.2f})" if cost_diff is not None else ""

                desc = (
                    f"Component '{disp_name}'{diff_str} is present in {', '.join(present_names)} "
                    f"but not listed in {', '.join(absent_names)}."
                )
                inclusions_exclusions.append(
                    InclusionExclusionFinding(
                        component_category=cat_id,
                        component_name=disp_name,
                        description=desc,
                        present_in_document_ids=present_doc_ids,
                        absent_in_document_ids=absent_doc_ids,
                        potential_cost_difference=cost_diff,
                    )
                )

        # 4. Total calculation
        valid_totals = [t for t in totals_by_doc_id.values() if t is not None]
        min_tot = min(valid_totals) if valid_totals else None
        max_tot = max(valid_totals) if valid_totals else None
        tot_delta = (
            round(max_tot - min_tot, 2) if (min_tot is not None and max_tot is not None) else None
        )

        # 5. Suggested Objective Questions
        questions: list[str] = []
        vendor_names_map = {q.document_id: q.vendor_name for q in quotes}

        # Handling charges variance
        for aligned in aligned_list:
            if aligned.canonical_category == "handling_charges" and aligned.presence_variance:
                charged_vendors = [
                    vendor_names_map[UUID(d_id)]
                    for d_id, c in aligned.cells.items()
                    if c.is_present and c.amount
                ]
                not_charged_vendors = [
                    vendor_names_map[UUID(d_id)]
                    for d_id, c in aligned.cells.items()
                    if not c.is_present or c.amount == 0
                ]
                if charged_vendors and not_charged_vendors:
                    amt_str = (
                        f" of {primary_curr} {aligned.max_amount:,.2f}"
                        if aligned.max_amount
                        else ""
                    )
                    q_text = (
                        f"{', '.join(charged_vendors)} has listed Handling / Incidental charges{amt_str}, "
                        f"which is not listed by {', '.join(not_charged_vendors)}. "
                        f"Inquire whether this charge is mandatory or can be waived."
                    )
                    questions.append(q_text)

            # Insurance variance
            if (
                aligned.canonical_category == "insurance"
                and aligned.delta_amount
                and aligned.delta_amount > 1000
            ):
                q_text = (
                    f"Insurance pricing varies by {primary_curr} {aligned.delta_amount:,.2f} across quotations. "
                    f"Request an itemized breakdown of insurance add-ons (such as Zero Depreciation, Engine Protect, and RTI) from each provider to compare coverage terms."
                )
                questions.append(q_text)

            # Accessories variance
            if aligned.canonical_category == "accessories" and aligned.presence_variance:
                q_text = (
                    "Accessories package is included in some quotations but omitted in others. "
                    "Verify whether all listed accessories are mandatory or optional user selections."
                )
                questions.append(q_text)

        # Fallback question if none generated
        if not questions and tot_delta and tot_delta > 0:
            questions.append(
                f"Total quotation prices differ by {primary_curr} {tot_delta:,.2f}. "
                f"Request an itemized reconciliation of price components from each vendor."
            )

        # 6. Neutral Summary Text
        doc_count = len(documents)
        vendor_list_str = ", ".join([q.vendor_name for q in quotes])
        if tot_delta is not None and min_tot is not None and max_tot is not None:
            summary = (
                f"Comparison of {doc_count} quotations ({vendor_list_str}). "
                f"Total amounts range from {primary_curr} {min_tot:,.2f} to {primary_curr} {max_tot:,.2f} "
                f"(total delta: {primary_curr} {tot_delta:,.2f}). "
                f"{len(aligned_list)} financial component categories were aligned across all documents."
            )
        else:
            summary = (
                f"Comparison of {doc_count} quotations ({vendor_list_str}). "
                f"{len(aligned_list)} financial component categories were aligned across documents."
            )

        if currency_mismatch:
            summary += (
                " Note: Currency mismatch detected across documents. Compare figures with caution."
            )

        return MultiQuoteComparisonResult(
            user_id=user_id,
            quotes=quotes,
            primary_currency=primary_curr,
            currency_mismatch=currency_mismatch,
            aligned_components=aligned_list,
            totals_by_document_id=totals_by_doc_id,
            min_total=min_tot,
            max_total=max_tot,
            total_delta=tot_delta,
            inclusions_and_exclusions=inclusions_exclusions,
            suggested_negotiation_questions=questions,
            summary_text=summary,
        )
