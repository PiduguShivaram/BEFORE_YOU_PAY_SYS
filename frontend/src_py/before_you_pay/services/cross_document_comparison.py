"""Phase 2: Cross-document contextual comparison service.

Compares primary document financial data against retrieved supporting document
RAG chunks to produce typed ContextualFinding objects.

Design principles:
- Deterministic arithmetic for numeric comparisons (delta, price variance).
- Keyword-semantic matching for conceptual labels (warranty, insurance, coverage).
- Uncertainty-aware language: "potential overlap", "appears related", "requires verification".
- Full provenance: every finding traces to specific primary and supporting evidence.
- User isolation enforced upstream by SqliteRagService (user_id filter).
- Never converts MISSING/UNKNOWN amounts to zero.
"""

from __future__ import annotations

import re
from uuid import UUID

from before_you_pay.models.analysis import (
    ContextualEvidence,
    ContextualFinding,
    ContextualFindingType,
    RagEvidenceChunk,
    ValidationSeverity,
)
from before_you_pay.models.document import (
    DocumentClassification,
    FinancialComponent,
    StructuredFinancialDocument,
)

# Conceptual label groupings for semantic similarity matching
_WARRANTY_KEYWORDS = frozenset(
    ["warranty", "warrantee", "guarantee", "waranty", "coverage", "covered", "protect"]
)
_INSURANCE_KEYWORDS = frozenset(
    ["insurance", "insure", "insured", "policy", "premium", "coverage", "insurer"]
)
_PRICE_KEYWORDS = frozenset(
    ["price", "rate", "amount", "total", "cost", "ex-showroom", "exshowroom"]
)


def _extract_amounts(text: str) -> list[float]:
    """Extract all currency amounts from raw text. Does not return zero for absence."""
    pattern = re.compile(
        r"(?:[₹$€£¥]|Rs\.?|INR|USD)\s*((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )
    amounts: list[float] = []
    for m in pattern.finditer(text):
        try:
            amounts.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return amounts


def _keyword_overlap(text: str, keywords: frozenset[str]) -> float:
    """Word-level recall: fraction of keywords found in text. Returns 0.0 to 1.0."""
    text_words = set(re.findall(r"[a-z]+", text.lower()))
    hits = keywords.intersection(text_words)
    return round(len(hits) / max(len(keywords), 1), 2)


def _format_currency(amount: float, currency: str | None = None) -> str:
    """Format an amount using the document's currency symbol."""
    sym = "₹" if (currency or "").upper() in ("INR", "₹") else (currency or "")
    return f"{sym}{amount:,.2f}"


def _build_supporting_evidence(
    chunk: RagEvidenceChunk,
    amount: float | None = None,
    label: str | None = None,
) -> ContextualEvidence:
    """Build a ContextualEvidence from a RAG chunk."""
    return ContextualEvidence(
        document_role="supporting",
        document_id=chunk.source_document_id,
        source_document_type=chunk.source_document_type.value,
        raw_text=chunk.source_text[:400],
        page_number=chunk.page_number,
        bounding_box=chunk.bounding_box,
        amount=amount,
        label=label,
    )


def _build_primary_evidence(
    comp: FinancialComponent,
    document_id: UUID,
    document_type: str,
) -> ContextualEvidence:
    """Build a ContextualEvidence from a FinancialComponent."""
    amount_val = None
    try:
        if comp.amount and comp.amount.normalized_value is not None:
            amount_val = float(comp.amount.normalized_value)
    except (TypeError, ValueError):
        pass

    return ContextualEvidence(
        document_role="primary",
        document_id=document_id,
        source_document_type=document_type,
        raw_text=comp.evidence or comp.source_ocr_line or comp.name,
        page_number=comp.page or 1,
        bounding_box=comp.bounding_box,
        amount=amount_val,
        label=comp.normalized_label or comp.name,
    )


class CrossDocumentComparisonService:
    """Produces typed ContextualFinding objects from primary document vs supporting RAG chunks.

    This service is purely deterministic and keyword-based. It does not call an LLM.
    LLM/semantic reasoning for overlap detection is handled by SemanticReasoningEngine.
    """

    def compare(
        self,
        document: StructuredFinancialDocument,
        supporting_chunks: list[RagEvidenceChunk],
        supporting_doc_id: UUID,
        supporting_doc_type: DocumentClassification,
    ) -> list[ContextualFinding]:
        """Run all comparison passes and return the union of ContextualFinding results."""
        if not supporting_chunks:
            return []

        findings: list[ContextualFinding] = []
        currency = document.currency

        # 1. Warranty overlap check
        findings.extend(
            self._check_component_overlap(
                document=document,
                supporting_chunks=supporting_chunks,
                supporting_doc_id=supporting_doc_id,
                supporting_doc_type=supporting_doc_type,
                category_keywords=_WARRANTY_KEYWORDS,
                component_categories={"warranty", "extended_warranty"},
                finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
                label="warranty",
                currency=currency,
            )
        )

        # 2. Insurance overlap check
        findings.extend(
            self._check_component_overlap(
                document=document,
                supporting_chunks=supporting_chunks,
                supporting_doc_id=supporting_doc_id,
                supporting_doc_type=supporting_doc_type,
                category_keywords=_INSURANCE_KEYWORDS,
                component_categories={"insurance"},
                finding_type=ContextualFindingType.POTENTIAL_OVERLAP,
                label="insurance",
                currency=currency,
            )
        )

        # 3. Price variance check (when supporting doc has a total/price)
        findings.extend(
            self._check_price_variance(
                document=document,
                supporting_chunks=supporting_chunks,
                supporting_doc_id=supporting_doc_id,
                supporting_doc_type=supporting_doc_type,
                currency=currency,
            )
        )

        # 4. Arbitrary charge comparison (find any matching component by label similarity)
        findings.extend(
            self._check_label_similarity(
                document=document,
                supporting_chunks=supporting_chunks,
                supporting_doc_id=supporting_doc_id,
                supporting_doc_type=supporting_doc_type,
                currency=currency,
            )
        )

        # Deduplicate: remove findings where primary+supporting evidence IDs are identical
        seen: set[tuple] = set()
        deduped: list[ContextualFinding] = []
        for f in findings:
            key = (f.finding_type, f.title[:60])
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        return deduped

    def _check_component_overlap(
        self,
        document: StructuredFinancialDocument,
        supporting_chunks: list[RagEvidenceChunk],
        supporting_doc_id: UUID,
        supporting_doc_type: DocumentClassification,
        category_keywords: frozenset[str],
        component_categories: set[str],
        finding_type: ContextualFindingType,
        label: str,
        currency: str | None,
    ) -> list[ContextualFinding]:
        """Check if any primary document component overlaps with supporting document chunks."""
        findings: list[ContextualFinding] = []

        # Find matching primary components
        primary_comps = [
            c
            for c in document.cost_breakdown
            if (c.category or "").lower() in component_categories
            or any(kw in (c.name or "").lower() for kw in category_keywords)
        ]
        if not primary_comps:
            return []

        # Find supporting chunks that mention the label category
        relevant_chunks = [
            chunk
            for chunk in supporting_chunks
            if _keyword_overlap(chunk.source_text, category_keywords) >= 0.15
        ]
        if not relevant_chunks:
            return []

        for comp in primary_comps:
            primary_amount: float | None = None
            try:
                if comp.amount and comp.amount.normalized_value is not None:
                    primary_amount = float(comp.amount.normalized_value)
            except (TypeError, ValueError):
                pass

            for chunk in relevant_chunks[:3]:  # cap at 3 supporting chunks per component
                supp_amounts = _extract_amounts(chunk.source_text)
                supp_amount = supp_amounts[0] if supp_amounts else None

                # Build uncertainty-aware description
                label_str = comp.normalized_label or comp.name
                primary_str = (
                    _format_currency(primary_amount, currency)
                    if primary_amount is not None
                    else "an amount not readable from the document"
                )
                supp_str = (
                    _format_currency(supp_amount, currency)
                    if supp_amount is not None
                    else "an amount not readable from the supporting document"
                )

                description = (
                    f"The primary document includes a {label} charge ({label_str}"
                    f"{': ' + primary_str if primary_amount else ''}). "
                    f"The supporting document appears to reference {label} coverage "
                    f"({supp_str if supp_amount else 'amount not determinable from available text'}). "
                    f"Verify whether both refer to the same coverage period, provider, and scope before paying."
                )

                what_to_verify = [
                    f"Confirm whether the {label_str} covers the same period as any existing {label} in the supporting document.",
                    "Verify whether coverage described in the supporting document remains active.",
                    f"Check if the quoted {label_str} adds coverage beyond what the supporting document provides.",
                ]

                questions_to_ask = [
                    f"Does the {primary_str + ' ' if primary_amount else ''}{label_str} provide coverage that is not already present in the existing {label} policy?",
                    f"What is the coverage period, provider, and exclusions for the {label_str}?",
                ]
                if primary_amount and supp_amount:
                    questions_to_ask.append(
                        f"The supporting document shows {supp_str}. Is the quoted {primary_str} for the same scope?"
                    )

                severity = (
                    ValidationSeverity.WARNING
                    if primary_amount and primary_amount > 1000
                    else ValidationSeverity.INFO
                )

                try:
                    finding = ContextualFinding(
                        finding_type=finding_type,
                        title=f"Potential {label} coverage overlap",
                        description=description,
                        primary_evidence=[
                            _build_primary_evidence(
                                comp, document.document_id, document.document_type.value
                            )
                        ],
                        supporting_evidence=[_build_supporting_evidence(chunk, supp_amount, label)],
                        what_to_verify=what_to_verify,
                        questions_to_ask=questions_to_ask,
                        confidence=round(chunk.similarity_score, 2),
                        severity=severity,
                        primary_amount=primary_amount,
                        supporting_amount=supp_amount,
                        delta_amount=(
                            round(abs(primary_amount - supp_amount), 2)
                            if primary_amount is not None and supp_amount is not None
                            else None
                        ),
                    )
                    findings.append(finding)
                except ValueError:
                    # Skip if language guardrail triggers
                    pass

        return findings

    def _check_price_variance(
        self,
        document: StructuredFinancialDocument,
        supporting_chunks: list[RagEvidenceChunk],
        supporting_doc_id: UUID,
        supporting_doc_type: DocumentClassification,
        currency: str | None,
    ) -> list[ContextualFinding]:
        """Detect when supporting document has a total that differs from the primary total."""
        if not document.total_amount or document.total_amount.normalized_value is None:
            return []

        try:
            primary_total = float(document.total_amount.normalized_value)
        except (TypeError, ValueError):
            return []

        if primary_total <= 0:
            return []

        findings: list[ContextualFinding] = []

        for chunk in supporting_chunks:
            chunk_overlap = _keyword_overlap(chunk.source_text, _PRICE_KEYWORDS)
            if chunk_overlap < 0.10:
                continue

            supp_amounts = _extract_amounts(chunk.source_text)
            if not supp_amounts:
                continue

            # Consider the largest amount in the supporting chunk as its "total"
            supp_total = max(supp_amounts)

            delta = round(abs(primary_total - supp_total), 2)
            # Only surface if meaningful delta (> 1% of primary total or > 100 units)
            if delta < max(primary_total * 0.01, 100.0):
                continue

            primary_str = _format_currency(primary_total, currency)
            supp_str = _format_currency(supp_total, currency)
            delta_str = _format_currency(delta, currency)

            # Direction
            direction = "higher" if primary_total > supp_total else "lower"

            description = (
                f"The current document total is {primary_str}, while the supporting document "
                f"appears to reference {supp_str} (difference: {delta_str}). "
                f"The current amount is {direction} than what appears in the supporting document. "
                "Verify whether the difference is explained by updated terms, additional charges, "
                "changed specifications, or a different scope."
            )

            what_to_verify = [
                f"Confirm what explains the {delta_str} difference between {primary_str} and {supp_str}.",
                "Check if different items, quantities, or charges are included.",
                "Verify whether any discounts, promotions, or negotiated terms changed.",
            ]

            questions_to_ask = [
                f"The supporting document shows {supp_str} while the current quote is {primary_str}. What accounts for the {delta_str} difference?",
                "Are the specifications, quantities, and included charges the same between both documents?",
            ]

            try:
                finding = ContextualFinding(
                    finding_type=ContextualFindingType.PRICE_VARIANCE,
                    title=f"Price variance vs supporting document ({delta_str} difference)",
                    description=description,
                    primary_evidence=[
                        ContextualEvidence(
                            document_role="primary",
                            document_id=document.document_id,
                            source_document_type=document.document_type.value,
                            raw_text=document.total_amount.provenance.raw_text,
                            page_number=1,
                            bounding_box=document.total_amount.provenance.bounding_box,
                            amount=primary_total,
                            label="Total amount",
                        )
                    ],
                    supporting_evidence=[_build_supporting_evidence(chunk, supp_total, "Total")],
                    what_to_verify=what_to_verify,
                    questions_to_ask=questions_to_ask,
                    confidence=round(chunk.similarity_score, 2),
                    severity=ValidationSeverity.WARNING,
                    primary_amount=primary_total,
                    supporting_amount=supp_total,
                    delta_amount=delta,
                )
                findings.append(finding)
            except ValueError:
                pass

        return findings

    def _check_label_similarity(
        self,
        document: StructuredFinancialDocument,
        supporting_chunks: list[RagEvidenceChunk],
        supporting_doc_id: UUID,
        supporting_doc_type: DocumentClassification,
        currency: str | None,
    ) -> list[ContextualFinding]:
        """Find primary charges whose label appears in supporting document text."""
        findings: list[ContextualFinding] = []

        # Only consider charges above a minimum meaningful threshold
        significant_comps = [
            c
            for c in document.cost_breakdown
            if c.charge_nature
            and c.charge_nature.value == "charge"
            and c.amount
            and c.amount.normalized_value is not None
            and float(c.amount.normalized_value or 0) > 500
        ]

        # Skip if these are already handled by warranty/insurance checks
        already_handled = {"warranty", "extended_warranty", "insurance"}

        for comp in significant_comps:
            if (comp.category or "").lower() in already_handled:
                continue
            comp_name_lower = (comp.normalized_label or comp.name or "").lower()
            comp_words = set(re.findall(r"[a-z]{3,}", comp_name_lower))
            if not comp_words:
                continue

            for chunk in supporting_chunks:
                chunk_words = set(re.findall(r"[a-z]{3,}", chunk.source_text.lower()))
                overlap = comp_words.intersection(chunk_words)
                # Require at least 2 meaningful shared words or 40% label word recall
                recall = round(len(overlap) / max(len(comp_words), 1), 2)
                if len(overlap) < 1 or recall < 0.4:
                    continue

                primary_amount: float | None = None
                try:
                    primary_amount = float(comp.amount.normalized_value)
                except (TypeError, ValueError):
                    pass

                supp_amounts = _extract_amounts(chunk.source_text)
                supp_amount = supp_amounts[0] if supp_amounts else None

                label_str = comp.normalized_label or comp.name
                primary_str = (
                    _format_currency(primary_amount, currency) if primary_amount is not None else ""
                )

                description = (
                    f"The primary document includes '{label_str}'"
                    f"{' (' + primary_str + ')' if primary_str else ''}. "
                    f"The supporting document appears to reference related terms: "
                    f"'{chunk.source_text[:120]}...'. "
                    "Verify whether these refer to the same service, charge, or obligation."
                )

                what_to_verify = [
                    f"Confirm whether '{label_str}' in the current document and the reference in the supporting document refer to the same service.",
                    "Check if this charge was previously agreed or is a new addition.",
                ]

                questions_to_ask = [
                    f"The supporting document mentions similar terms. Is '{label_str}' the same as referenced previously?",
                ]
                if primary_amount and supp_amount:
                    delta = round(abs(primary_amount - supp_amount), 2)
                    questions_to_ask.append(
                        f"The supporting document shows {_format_currency(supp_amount, currency)} vs the current {primary_str} for a similar charge. What explains the {_format_currency(delta, currency)} difference?"
                    )

                try:
                    finding = ContextualFinding(
                        finding_type=ContextualFindingType.COVERAGE_COMPARISON,
                        title=f"'{label_str}' appears in supporting document",
                        description=description,
                        primary_evidence=[
                            _build_primary_evidence(
                                comp, document.document_id, document.document_type.value
                            )
                        ],
                        supporting_evidence=[
                            _build_supporting_evidence(chunk, supp_amount, label_str)
                        ],
                        what_to_verify=what_to_verify,
                        questions_to_ask=questions_to_ask,
                        confidence=round(recall, 2),
                        severity=ValidationSeverity.INFO,
                        primary_amount=primary_amount,
                        supporting_amount=supp_amount,
                        delta_amount=(
                            round(abs(primary_amount - supp_amount), 2)
                            if primary_amount is not None and supp_amount is not None
                            else None
                        ),
                    )
                    findings.append(finding)
                except ValueError:
                    pass

        return findings
