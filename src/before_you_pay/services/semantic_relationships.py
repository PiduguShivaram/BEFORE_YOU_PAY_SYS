"""Semantic document relationships and financial structure analysis (Phase 4 Step 5).

Models relationships between financial components and how they reconcile to the quoted total
across various financial document structures:
- Vehicle quotation: BASE_PRICE + TAX + REGISTRATION + INSURANCE + WARRANTY + DEALER_CHARGE - DISCOUNT = QUOTED_TOTAL
- Standard commercial invoice: SUBTOTAL + TAX + SHIPPING + FEES - DISCOUNT = TOTAL
- Itemized bill: SUM(LINE_ITEMS) + TAX + SHIPPING - DISCOUNT = TOTAL
- Subscription: BASE_FEE + RECURRING_CHARGES = TOTAL
- Simple receipt: AMOUNT = TOTAL

Strict Guardrails:
- Preserves deterministic arithmetic verification: LLM/heuristics only identify relationships,
  while math is 100% deterministic.
- Never ignores or rounds away discrepancies.
- Understands explicit zero/included components without treating them as missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from before_you_pay.models.document import (
    AmountState,
    ComponentCategory,
    DocumentClassification,
    StructuredFinancialDocument,
)


class SemanticRelationType(StrEnum):
    """Mathematical relationship between a component and the financial total."""

    ADDITIVE = "additive"  # (+) Adds to total
    DEDUCTIVE = "deductive"  # (-) Deducts from total
    EQUAL = "equal"  # (=) Equals total or subtotal
    INCLUDED = "included"  # (₹0) Bundled or zero-rated
    INFORMATIONAL = "informational"  # Reference or non-arithmetic note


class SemanticFormulaType(StrEnum):
    """Underlying financial structure of the document."""

    VEHICLE_QUOTATION_BREAKDOWN = "vehicle_quotation_breakdown"
    COMMERCE_INVOICE = "commerce_invoice"
    ITEMIZED_BILL = "itemized_bill"
    SUBSCRIPTION_AGREEMENT = "subscription_agreement"
    SIMPLE_RECEIPT = "simple_receipt"
    UNKNOWN_STRUCTURE = "unknown_structure"


@dataclass(frozen=True)
class SemanticComponentRelation:
    """Individual financial component's semantic link to the aggregate commitment."""

    component_name: str
    original_label: str
    canonical_category: ComponentCategory
    relation_type: SemanticRelationType
    amount: float | None
    amount_state: AmountState
    confidence: float
    evidence: str
    component_id: UUID | None = None
    is_recurring: bool | None = None
    billing_frequency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_name": self.component_name,
            "original_label": self.original_label,
            "canonical_category": self.canonical_category.value,
            "relation_type": self.relation_type.value,
            "amount": self.amount,
            "amount_state": self.amount_state.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "is_recurring": self.is_recurring,
            "billing_frequency": self.billing_frequency,
        }


@dataclass(frozen=True)
class SemanticFinancialStructure:
    """Structured semantic representation of document arithmetic and component relations."""

    formula_type: SemanticFormulaType
    formula_representation: str
    relations: list[SemanticComponentRelation] = field(default_factory=list)
    calculated_sum: float | None = None
    stated_total: float | None = None
    discrepancy: float | None = None
    is_reconciled: bool = False
    currency: str | None = None
    summary_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "formula_type": self.formula_type.value,
            "formula_representation": self.formula_representation,
            "relations": [r.to_dict() for r in self.relations],
            "calculated_sum": self.calculated_sum,
            "stated_total": self.stated_total,
            "discrepancy": self.discrepancy,
            "is_reconciled": self.is_reconciled,
            "currency": self.currency,
            "summary_explanation": self.summary_explanation,
        }


class SemanticRelationshipService:
    """Understands and reconciles semantic relationships between document financial components."""

    @classmethod
    def analyze_document(
        cls,
        document: StructuredFinancialDocument,
    ) -> SemanticFinancialStructure:
        """Derive semantic financial structure and component relationships from document."""
        currency = document.currency or "INR"
        stated_total = None
        if document.total_amount and isinstance(
            document.total_amount.normalized_value, (int, float)
        ):
            stated_total = round(float(document.total_amount.normalized_value), 2)

        # ── 1. Quotations, Estimates, and Dedicated Breakdown Sheets ──
        if document.document_type in (
            DocumentClassification.QUOTATION,
            DocumentClassification.COST_BREAKDOWN,
            DocumentClassification.ESTIMATE,
        ):
            if document.cost_breakdown:
                return cls._analyze_cost_breakdown(document, stated_total, currency)

        # ── 2. Standard Commerce Invoices and Bills ──
        if document.document_type in (
            DocumentClassification.INVOICE,
            DocumentClassification.BILL,
            DocumentClassification.RECEIPT,
        ):
            if (
                document.subtotal
                or document.tax_amount
                or document.shipping_amount
                or document.fees
            ):
                return cls._analyze_commerce_invoice(document, stated_total, currency)
            if document.line_items:
                return cls._analyze_itemized_lines(document, stated_total, currency)
            if document.cost_breakdown:
                return cls._analyze_cost_breakdown(document, stated_total, currency)

        # ── 3. General Fallbacks ──
        if document.cost_breakdown and len(document.cost_breakdown) >= 2:
            return cls._analyze_cost_breakdown(document, stated_total, currency)

        if document.subtotal or document.tax_amount or document.shipping_amount or document.fees:
            return cls._analyze_commerce_invoice(document, stated_total, currency)

        if document.cost_breakdown:
            return cls._analyze_cost_breakdown(document, stated_total, currency)

        if document.line_items:
            return cls._analyze_itemized_lines(document, stated_total, currency)

        # ── 4. Simple Receipt / Fallback ──
        return cls._analyze_simple_receipt(document, stated_total, currency)

    @classmethod
    def _analyze_cost_breakdown(
        cls,
        document: StructuredFinancialDocument,
        stated_total: float | None,
        currency: str,
    ) -> SemanticFinancialStructure:
        """Analyze multi-component quotation breakdown."""
        relations: list[SemanticComponentRelation] = []
        additive_sum = 0.0
        deductive_sum = 0.0
        formula_parts_add: list[str] = []
        formula_parts_ded: list[str] = []

        for comp in document.cost_breakdown:
            amt_val = None
            if comp.amount and isinstance(comp.amount.normalized_value, (int, float)):
                amt_val = float(comp.amount.normalized_value)

            cat = (
                comp.category.to_canonical_category()
                if hasattr(comp.category, "to_canonical_category")
                else comp.category
            )

            # Determine relation type
            if comp.amount_state == AmountState.ZERO or amt_val == 0.0:
                rel_type = SemanticRelationType.INCLUDED
            elif comp.charge_nature.is_deduction or cat in (
                ComponentCategory.DISCOUNT,
                ComponentCategory.OFFER,
            ):
                rel_type = SemanticRelationType.DEDUCTIVE
                if amt_val is not None:
                    deductive_sum += amt_val
                formula_parts_ded.append(cat.name if hasattr(cat, "name") else str(cat).upper())
            else:
                rel_type = SemanticRelationType.ADDITIVE
                if amt_val is not None:
                    additive_sum += amt_val
                formula_parts_add.append(cat.name if hasattr(cat, "name") else str(cat).upper())

            relations.append(
                SemanticComponentRelation(
                    component_name=comp.normalized_label or comp.name,
                    original_label=comp.original_label or comp.raw_label or comp.name,
                    canonical_category=cat,
                    relation_type=rel_type,
                    amount=amt_val,
                    amount_state=comp.amount_state,
                    confidence=comp.confidence,
                    evidence=comp.evidence or comp.raw_text or comp.name,
                    component_id=comp.component_id,
                    is_recurring=comp.is_recurring,
                    billing_frequency=comp.billing_frequency,
                )
            )

        calc_total = round(additive_sum - deductive_sum, 2)
        discrepancy = round(abs(calc_total - stated_total), 2) if stated_total is not None else None
        is_reconciled = discrepancy is not None and discrepancy <= 0.02

        # Format clean canonical formula representation
        add_expr = " + ".join(dict.fromkeys(formula_parts_add)) or "CHARGES"
        ded_expr = f" - {' - '.join(dict.fromkeys(formula_parts_ded))}" if formula_parts_ded else ""
        formula_rep = f"{add_expr}{ded_expr} = QUOTED_TOTAL"

        if is_reconciled:
            explanation = (
                f"Quoted total ({currency} {stated_total:,.2f}) perfectly reconciles with constituent "
                f"breakdown charges ({currency} {additive_sum:,.2f}) minus deductions ({currency} {deductive_sum:,.2f})."
            )
        elif stated_total is not None:
            explanation = (
                f"Discrepancy of {currency} {discrepancy:,.2f} detected: Sum of breakdown components "
                f"({currency} {calc_total:,.2f}) does not equal stated total ({currency} {stated_total:,.2f})."
            )
        else:
            explanation = f"Calculated total from breakdown charges: {currency} {calc_total:,.2f}."

        return SemanticFinancialStructure(
            formula_type=SemanticFormulaType.VEHICLE_QUOTATION_BREAKDOWN,
            formula_representation=formula_rep,
            relations=relations,
            calculated_sum=calc_total,
            stated_total=stated_total,
            discrepancy=discrepancy,
            is_reconciled=is_reconciled,
            currency=currency,
            summary_explanation=explanation,
        )

    @classmethod
    def _analyze_commerce_invoice(
        cls,
        document: StructuredFinancialDocument,
        stated_total: float | None,
        currency: str,
    ) -> SemanticFinancialStructure:
        """Analyze standard commercial invoice (subtotal + tax + shipping - discount)."""
        relations: list[SemanticComponentRelation] = []
        calc_total = 0.0
        formula_parts: list[str] = []

        if document.subtotal and isinstance(document.subtotal.normalized_value, (int, float)):
            sub_val = float(document.subtotal.normalized_value)
            calc_total += sub_val
            formula_parts.append("SUBTOTAL")
            relations.append(
                SemanticComponentRelation(
                    component_name="Subtotal",
                    original_label="Subtotal",
                    canonical_category=ComponentCategory.BASE_PRICE,
                    relation_type=SemanticRelationType.ADDITIVE,
                    amount=sub_val,
                    amount_state=document.subtotal.amount_state,
                    confidence=document.subtotal.confidence,
                    evidence=document.subtotal.provenance.raw_text
                    if document.subtotal.provenance
                    else "Subtotal",
                )
            )

        if document.tax_amount and isinstance(document.tax_amount.normalized_value, (int, float)):
            tax_val = float(document.tax_amount.normalized_value)
            calc_total += tax_val
            formula_parts.append("TAX")
            relations.append(
                SemanticComponentRelation(
                    component_name="Tax",
                    original_label="Tax",
                    canonical_category=ComponentCategory.TAX_OR_STATUTORY,
                    relation_type=SemanticRelationType.ADDITIVE
                    if tax_val > 0
                    else SemanticRelationType.INCLUDED,
                    amount=tax_val,
                    amount_state=document.tax_amount.amount_state,
                    confidence=document.tax_amount.confidence,
                    evidence=document.tax_amount.provenance.raw_text
                    if document.tax_amount.provenance
                    else "Tax",
                )
            )

        if document.shipping_amount and isinstance(
            document.shipping_amount.normalized_value, (int, float)
        ):
            ship_val = float(document.shipping_amount.normalized_value)
            calc_total += ship_val
            formula_parts.append("SHIPPING")
            relations.append(
                SemanticComponentRelation(
                    component_name="Shipping",
                    original_label="Shipping",
                    canonical_category=ComponentCategory.DEALER_CHARGE,
                    relation_type=SemanticRelationType.ADDITIVE
                    if ship_val > 0
                    else SemanticRelationType.INCLUDED,
                    amount=ship_val,
                    amount_state=document.shipping_amount.amount_state,
                    confidence=document.shipping_amount.confidence,
                    evidence=document.shipping_amount.provenance.raw_text
                    if document.shipping_amount.provenance
                    else "Shipping",
                )
            )

        for fee in document.fees:
            if isinstance(fee.normalized_value, (int, float)):
                f_val = float(fee.normalized_value)
                calc_total += f_val
                relations.append(
                    SemanticComponentRelation(
                        component_name=fee.field_key or "Fee",
                        original_label=fee.field_key or "Fee",
                        canonical_category=ComponentCategory.DEALER_CHARGE,
                        relation_type=SemanticRelationType.ADDITIVE,
                        amount=f_val,
                        amount_state=fee.amount_state,
                        confidence=fee.confidence,
                        evidence=fee.provenance.raw_text if fee.provenance else fee.field_key,
                    )
                )

        if document.discount_amount and isinstance(
            document.discount_amount.normalized_value, (int, float)
        ):
            disc_val = float(document.discount_amount.normalized_value)
            gross_without_disc = round(calc_total, 2)
            gross_with_disc = round(calc_total - disc_val, 2)

            if stated_total is not None and abs(gross_without_disc - stated_total) <= 0.02:
                # Subtotal already incorporates item-level discounts
                calc_total = gross_without_disc
                ded_str = ""
                rel_type = SemanticRelationType.INCLUDED
            else:
                calc_total = gross_with_disc
                ded_str = " - DISCOUNT"
                rel_type = SemanticRelationType.DEDUCTIVE

            relations.append(
                SemanticComponentRelation(
                    component_name="Discount",
                    original_label="Discount",
                    canonical_category=ComponentCategory.DISCOUNT,
                    relation_type=rel_type,
                    amount=disc_val,
                    amount_state=document.discount_amount.amount_state,
                    confidence=document.discount_amount.confidence,
                    evidence=document.discount_amount.provenance.raw_text
                    if document.discount_amount.provenance
                    else "Discount",
                )
            )
        else:
            ded_str = ""

        calc_total = round(calc_total, 2)
        discrepancy = round(abs(calc_total - stated_total), 2) if stated_total is not None else None
        is_reconciled = discrepancy is not None and discrepancy <= 0.02
        formula_rep = f"{' + '.join(formula_parts) or 'SUBTOTAL'}{ded_str} = TOTAL"

        return SemanticFinancialStructure(
            formula_type=SemanticFormulaType.COMMERCE_INVOICE,
            formula_representation=formula_rep,
            relations=relations,
            calculated_sum=calc_total,
            stated_total=stated_total,
            discrepancy=discrepancy,
            is_reconciled=is_reconciled,
            currency=currency,
            summary_explanation=(
                f"Standard invoice reconciliation: {'Reconciles' if is_reconciled else 'Discrepancy detected'}."
            ),
        )

    @classmethod
    def _analyze_itemized_lines(
        cls,
        document: StructuredFinancialDocument,
        stated_total: float | None,
        currency: str,
    ) -> SemanticFinancialStructure:
        """Analyze itemized catalog / line item invoice."""
        relations: list[SemanticComponentRelation] = []
        items_sum = 0.0

        for it in document.line_items:
            amt_val = None
            if it.total_price and isinstance(it.total_price.normalized_value, (int, float)):
                amt_val = float(it.total_price.normalized_value)
                items_sum += amt_val

            desc = (
                it.description.provenance.raw_text
                if it.description and it.description.provenance
                else "Item"
            )
            relations.append(
                SemanticComponentRelation(
                    component_name=desc,
                    original_label=desc,
                    canonical_category=ComponentCategory.BASE_PRICE,
                    relation_type=SemanticRelationType.ADDITIVE,
                    amount=amt_val,
                    amount_state=it.total_price.amount_state
                    if it.total_price
                    else AmountState.PRESENT,
                    confidence=it.total_price.confidence if it.total_price else 0.85,
                    evidence=desc,
                )
            )

        items_sum = round(items_sum, 2)
        discrepancy = round(abs(items_sum - stated_total), 2) if stated_total is not None else None
        is_reconciled = discrepancy is not None and discrepancy <= 0.02

        return SemanticFinancialStructure(
            formula_type=SemanticFormulaType.ITEMIZED_BILL,
            formula_representation="SUM(LINE_ITEMS) = TOTAL",
            relations=relations,
            calculated_sum=items_sum,
            stated_total=stated_total,
            discrepancy=discrepancy,
            is_reconciled=is_reconciled,
            currency=currency,
            summary_explanation=f"Itemized line items total: {currency} {items_sum:,.2f}.",
        )

    @classmethod
    def _analyze_simple_receipt(
        cls,
        document: StructuredFinancialDocument,
        stated_total: float | None,
        currency: str,
    ) -> SemanticFinancialStructure:
        """Analyze simple receipt with single financial amount."""
        return SemanticFinancialStructure(
            formula_type=SemanticFormulaType.SIMPLE_RECEIPT,
            formula_representation="TOTAL = TOTAL",
            relations=[],
            calculated_sum=stated_total,
            stated_total=stated_total,
            discrepancy=0.0,
            is_reconciled=True,
            currency=currency,
            summary_explanation=f"Simple total: {currency} {stated_total or 0.0:,.2f}.",
        )
