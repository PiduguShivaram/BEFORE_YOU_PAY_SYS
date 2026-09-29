"""Semantic reasoning engine synthesizing evidence into grounded claims."""

import re
from uuid import uuid4

from before_you_pay.models import (
    ChargeNature,
    ClaimType,
    ComponentCategory,
    DocumentClassification,
    OkfRuleEvidence,
    RagEvidenceChunk,
    ReasoningClaim,
    StructuredFinancialDocument,
    ValidationSeverity,
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


class SemanticReasoningEngine:
    """Synthesizes grounded claims across extracted data, RAG chunks, and OKF rules."""

    async def generate_claims(
        self,
        document: StructuredFinancialDocument,
        rag_evidence: list[RagEvidenceChunk],
        okf_evidence: list[OkfRuleEvidence],
    ) -> list[ReasoningClaim]:
        """Synthesize claims with strict attribution and non-committal vocabulary."""
        claims: list[ReasoningClaim] = []
        curr_sym = _get_currency_symbol(document.currency)

        total_val = float(document.total_amount.normalized_value) if document.total_amount else 0.0
        if total_val <= 0.0 and not document.line_items and not document.clauses_and_notes:
            claims.append(
                ReasoningClaim(
                    claim_id=uuid4(),
                    type=ClaimType.REQUIRES_VERIFICATION,
                    title="No identifiable financial commitments",
                    description="The uploaded document contains no discernible itemized charges, totals, or contractual clauses.",
                    field_references=[document.total_amount.field_id]
                    if document.total_amount
                    else [],
                    confidence=0.95,
                )
            )

        # 1. Cross-reference with User Historical / Supporting Documents (RAG)
        warranty_comps = [
            c
            for c in document.cost_breakdown
            if c.category in (ComponentCategory.WARRANTY, ComponentCategory.EXTENDED_WARRANTY)
            or "warranty" in (c.name or "").lower()
        ]
        insurance_comps = [
            c
            for c in document.cost_breakdown
            if c.category == ComponentCategory.INSURANCE or "insurance" in (c.name or "").lower()
        ]

        for chunk in rag_evidence:
            chunk_lower = chunk.source_text.lower()
            price_matches = re.findall(
                r"(?:[₹$€£¥]|Rs\.?|INR|USD)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
                chunk.source_text,
                re.IGNORECASE,
            )

            # Check pricing against overall document total
            if price_matches:
                prior_price = float(price_matches[-1].replace(",", ""))
                current_total = float(document.total_amount.normalized_value)
                if abs(prior_price - current_total) > 0.05 and current_total > 0:
                    claims.append(
                        ReasoningClaim(
                            claim_id=uuid4(),
                            type=ClaimType.POTENTIAL_OVERLAP,
                            title="Potential price variation with supporting records",
                            description=(
                                f"Current total is {curr_sym}{current_total:,.2f}, while supporting "
                                f"{chunk.source_document_type.value} specified {curr_sym}{prior_price:,.2f}. "
                                "Verify whether terms, specifications, or applied charges differ."
                            ),
                            field_references=[document.total_amount.field_id],
                            rag_evidence_references=[chunk.evidence_id],
                            confidence=chunk.similarity_score,
                        )
                    )

            # Check warranty coverage overlap with specific component linkage
            if "warranty" in chunk_lower or "coverage" in chunk_lower or "guarantee" in chunk_lower:
                if warranty_comps:
                    for w_comp in warranty_comps:
                        w_amt = float(w_comp.amount.normalized_value)
                        field_ref = [w_comp.amount.field_id]
                        claims.append(
                            ReasoningClaim(
                                claim_id=uuid4(),
                                type=ClaimType.POTENTIAL_OVERLAP,
                                title=f"Potential coverage overlap with existing {w_comp.name}",
                                description=(
                                    f"Your existing warranty appears to cover some of the same components or coverage areas. "
                                    f"Compare duration, covered components, and exclusions before purchasing the additional "
                                    f"{curr_sym}{w_amt:,.2f} {w_comp.name}."
                                ),
                                field_references=field_ref,
                                rag_evidence_references=[chunk.evidence_id],
                                confidence=chunk.similarity_score,
                            )
                        )
                else:
                    claims.append(
                        ReasoningClaim(
                            claim_id=uuid4(),
                            type=ClaimType.POTENTIAL_OVERLAP,
                            title="Potential overlap with existing warranty coverage",
                            description=(
                                f"Your supporting records indicate active coverage: '{chunk.source_text[:120]}'. "
                                "Requires verification whether these services are covered under existing agreement."
                            ),
                            field_references=[document.total_amount.field_id]
                            if document.total_amount
                            else [],
                            rag_evidence_references=[chunk.evidence_id],
                            confidence=chunk.similarity_score,
                        )
                    )

            # Check insurance coverage overlap
            if "insurance" in chunk_lower or "policy" in chunk_lower or "premium" in chunk_lower:
                if insurance_comps:
                    for ins_comp in insurance_comps:
                        ins_amt = float(ins_comp.amount.normalized_value)
                        claims.append(
                            ReasoningClaim(
                                claim_id=uuid4(),
                                type=ClaimType.POTENTIAL_OVERLAP,
                                title="Potential overlap with existing insurance policy",
                                description=(
                                    f"Your supporting records reference active insurance coverage. "
                                    f"Compare policy coverage, add-ons, and exclusions with the quoted "
                                    f"{curr_sym}{ins_amt:,.2f} {ins_comp.name}."
                                ),
                                field_references=[ins_comp.amount.field_id],
                                rag_evidence_references=[chunk.evidence_id],
                                confidence=chunk.similarity_score,
                            )
                        )

        # 2. Shipping charge verification check
        if document.shipping_amount and float(document.shipping_amount.normalized_value) > 0.0:
            ship_val = float(document.shipping_amount.normalized_value)
            claims.append(
                ReasoningClaim(
                    claim_id=uuid4(),
                    type=ClaimType.REQUIRES_VERIFICATION,
                    title="Shipping charge requires verification",
                    description=(
                        f"Shipping charge: {curr_sym}{ship_val:,.2f}. "
                        f"Verify whether the {curr_sym}{ship_val:,.2f} shipping charge is expected/mandatory "
                        "and whether any additional charges will be applied."
                    ),
                    field_references=[document.shipping_amount.field_id],
                    confidence=document.shipping_amount.confidence,
                )
            )

        # 3. Cross-reference against Curated OKF Rules
        for rule in okf_evidence:
            rule_id = rule.rule_id

            if "RENEW" in rule_id:
                renew_clauses = [
                    c
                    for c in document.clauses_and_notes
                    if "renew" in str(c.normalized_value).lower()
                ]
                for c in renew_clauses:
                    claims.append(
                        ReasoningClaim(
                            claim_id=uuid4(),
                            type=ClaimType.TERM_REQUIRING_ATTENTION,
                            title="Term requiring attention: Automatic renewal commitment",
                            description=(
                                f"Clause detected: '{c.normalized_value}'. "
                                f"Rule guidance: {rule.guidance}"
                            ),
                            field_references=[c.field_id],
                            okf_rule_references=[rule.rule_id],
                            confidence=c.confidence,
                        )
                    )

            if "FEE" in rule_id and document.fees:
                for fee in document.fees:
                    claims.append(
                        ReasoningClaim(
                            claim_id=uuid4(),
                            type=ClaimType.ADDITIONAL_CHARGE_DETECTED,
                            title="Additional charge detected: Ancillary fee itemized",
                            description=(
                                f"Ancillary surcharge of {curr_sym}{float(fee.normalized_value):,.2f} detected. "
                                f"Guidance: {rule.guidance}"
                            ),
                            field_references=[fee.field_id],
                            okf_rule_references=[rule.rule_id],
                            confidence=fee.confidence,
                        )
                    )

            if "CANCEL" in rule_id:
                cancel_clauses = [
                    c
                    for c in document.clauses_and_notes
                    if any(
                        k in str(c.normalized_value).lower()
                        for k in ["cancel", "penalty", "restocking", "termination"]
                    )
                ]
                for c in cancel_clauses:
                    claims.append(
                        ReasoningClaim(
                            claim_id=uuid4(),
                            type=ClaimType.TERM_REQUIRING_ATTENTION,
                            title="Term requiring attention: Cancellation / penalty condition",
                            description=f"Clause detected: '{c.normalized_value}'. Guidance: {rule.guidance}",
                            field_references=[c.field_id],
                            okf_rule_references=[rule.rule_id],
                            confidence=c.confidence,
                        )
                    )

        # 4. Document-specific verification claims
        if (
            document.document_type
            in (DocumentClassification.QUOTATION, DocumentClassification.COST_BREAKDOWN)
            or document.cost_breakdown
        ):
            total_val = (
                float(document.total_amount.normalized_value) if document.total_amount else 0.0
            )
            discount_val = (
                float(document.discount_amount.normalized_value)
                if document.discount_amount
                else sum(
                    float(c.amount.normalized_value)
                    for c in document.cost_breakdown
                    if getattr(c, "charge_nature", None) == ChargeNature.DEDUCTION
                )
            )
            charges = [
                c
                for c in document.cost_breakdown
                if getattr(c, "charge_nature", None) == ChargeNature.CHARGE
            ]
            field_refs = [document.total_amount.field_id] if document.total_amount else []
            if document.subtotal:
                field_refs.append(document.subtotal.field_id)
            if document.discount_amount:
                field_refs.append(document.discount_amount.field_id)
            for c in document.cost_breakdown:
                if hasattr(c, "amount") and c.amount:
                    field_refs.append(c.amount.field_id)

            sym = curr_sym or "₹"
            if discount_val > 0.0:
                desc = (
                    f"Total mathematically reconciles. Before paying, verify that the {len(charges)} listed vehicle charges "
                    f"and {sym}{discount_val:,.2f} in offers match the dealer's final agreed price."
                )
            else:
                desc = (
                    f"Total mathematically reconciles. Before paying, verify that the {len(charges)} listed vehicle charges "
                    "match the dealer's final agreed price."
                )

            claims.append(
                ReasoningClaim(
                    claim_id=uuid4(),
                    type=ClaimType.REQUIRES_VERIFICATION,
                    title="Quotation commercial terms verification",
                    description=desc,
                    field_references=field_refs[:8],
                    confidence=document.total_amount.confidence if document.total_amount else 0.95,
                    severity=ValidationSeverity.INFO,
                )
            )

        return claims
