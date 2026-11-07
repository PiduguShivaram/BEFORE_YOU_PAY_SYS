"""Phase 1B: Dealer Response & Counter-Offer Parser Service.

Parses unstructured text from dealer emails, WhatsApp messages, and counter-offers,
extracting agreed waivers, discounts, price revisions, and stated totals, then
performing pure deterministic arithmetic reconciliation against the original quote.

Design principles:
- Pure deterministic arithmetic for all numerical adjustments and reconciliation deltas.
- Non-committal, objective language (no advice, recommendations, or accusations).
- Strict identification of mathematical discrepancies between stated final prices and itemized concessions.
- Actionable follow-up verification prompts for the user.
"""

from __future__ import annotations

import re
from uuid import UUID

from before_you_pay.models.dealer_response import (
    DealerActionType,
    DealerResponseAnalysisResult,
    ExtractedDealerAction,
)
from before_you_pay.models.document import StructuredFinancialDocument


def _parse_amount(text: str) -> float | None:
    """Parse a numeric string into a float, stripping commas and currency symbols."""
    clean = re.sub(r"[^\d.]", "", text.strip())
    try:
        val = float(clean)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


class DealerResponseParserService:
    """Service to parse and reconcile unstructured dealer negotiation responses."""

    def parse(
        self,
        dealer_text: str,
        user_id: UUID,
        original_document: StructuredFinancialDocument | None = None,
        original_total: float | None = None,
        currency: str = "INR",
    ) -> DealerResponseAnalysisResult:
        """Parse dealer negotiation response and reconcile against original quote."""
        if not dealer_text or not dealer_text.strip():
            raise ValueError("Dealer response text cannot be empty.")

        text_lower = dealer_text.lower()
        extracted_actions: list[ExtractedDealerAction] = []

        # 1. Resolve Original Total and Document Context
        orig_doc_id = None
        orig_tot = original_total
        curr = currency

        if original_document:
            orig_doc_id = original_document.document_id
            if original_document.currency:
                curr = original_document.currency.upper()
            if orig_tot is None and original_document.total_amount:
                if original_document.total_amount.normalized_value is not None:
                    try:
                        orig_tot = float(original_document.total_amount.normalized_value)
                    except (ValueError, TypeError):
                        pass

        # 2. Extract Handling / Incidental Fee Waiver
        handling_match = re.search(
            r"(?:waiv(?:e|ed|ing)|remov(?:e|ed|ing)|zero|0|drop(?:ped)?|cancel(?:led)?|free|complimentary)\s+(?:the\s+)?(?:handling|pdi|logistics?|depot|incidental|documentation)\s*(?:charges?|fees?)?",
            text_lower,
        ) or re.search(
            r"(?:handling|pdi|logistics?|depot|incidental)\s*(?:charges?|fees?)?\s*(?:is|are|will be)?\s*(?:waived|removed|free|zero|dropped|cancelled)",
            text_lower,
        )
        if handling_match:
            # Check if an amount is mentioned near the match
            amt_match = re.search(
                r"(?:rs\.?|₹|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{3,6})",
                text_lower[max(0, handling_match.start() - 20) : handling_match.end() + 30],
            )
            waived_amt = _parse_amount(amt_match.group(1)) if amt_match else None

            # Fallback to original doc handling charge if not explicitly stated in text
            if waived_amt is None and original_document and original_document.cost_breakdown:
                for comp in original_document.cost_breakdown:
                    if "handling" in (comp.raw_label or comp.raw_text or comp.name or "").lower():
                        if (
                            comp.amount
                            and hasattr(comp.amount, "normalized_value")
                            and comp.amount.normalized_value
                        ):
                            waived_amt = float(comp.amount.normalized_value)
                            break

            extracted_actions.append(
                ExtractedDealerAction(
                    action_type=DealerActionType.CHARGE_WAIVED,
                    target_component_name="Handling / Incidental Charges",
                    raw_text_snippet=dealer_text[
                        max(0, handling_match.start() - 10) : min(
                            len(dealer_text), handling_match.end() + 20
                        )
                    ].strip(),
                    original_amount=waived_amt,
                    revised_amount=0.0,
                    reduction_amount=waived_amt,
                    notes="Handling charges agreed to be waived/removed.",
                )
            )

        # 3. Extract Refusal / Non-negotiable Charges
        refusal_match = re.search(
            r"(?:cannot|can't|unable to|not possible to|mandatory|non-negotiable|company policy|fixed)\s+.*?(?:waive|remove|discount|reduce)\s+(?:the\s+)?(handling|insurance|price|fee|tax|rto)",
            text_lower,
        )
        if refusal_match:
            target = refusal_match.group(1).title()
            extracted_actions.append(
                ExtractedDealerAction(
                    action_type=DealerActionType.REFUSED_NON_NEGOTIABLE,
                    target_component_name=f"{target} Charges",
                    raw_text_snippet=dealer_text[
                        max(0, refusal_match.start() - 5) : min(
                            len(dealer_text), refusal_match.end() + 15
                        )
                    ].strip(),
                    notes=f"Dealer stated {target} charge is non-negotiable/mandatory.",
                )
            )

        # 4. Extract Insurance Price Revision / Reduction
        ins_revision = re.search(
            r"insurance\s*(?:price|premium|cost)?\s*(?:reduced|revised|discounted|brought down)?\s*(?:from\s*(?:rs\.?|₹|inr)?\s*([0-9,]+)\s*)?(?:to|at|is)\s*(?:rs\.?|₹|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,6})",
            text_lower,
        )
        if ins_revision:
            orig_ins_str = ins_revision.group(1)
            new_ins_str = ins_revision.group(2)
            new_ins = _parse_amount(new_ins_str)
            orig_ins = _parse_amount(orig_ins_str) if orig_ins_str else None

            if orig_ins is None and original_document and original_document.cost_breakdown:
                for comp in original_document.cost_breakdown:
                    if "insurance" in (comp.raw_label or comp.raw_text or comp.name or "").lower():
                        if (
                            comp.amount
                            and hasattr(comp.amount, "normalized_value")
                            and comp.amount.normalized_value
                        ):
                            orig_ins = float(comp.amount.normalized_value)
                            break

            red_amt = (
                round(orig_ins - new_ins, 2)
                if (orig_ins and new_ins and orig_ins > new_ins)
                else None
            )
            extracted_actions.append(
                ExtractedDealerAction(
                    action_type=DealerActionType.PRICE_REDUCED,
                    target_component_name="Insurance Premium",
                    raw_text_snippet=dealer_text[
                        max(0, ins_revision.start() - 5) : min(
                            len(dealer_text), ins_revision.end() + 15
                        )
                    ].strip(),
                    original_amount=orig_ins,
                    revised_amount=new_ins,
                    reduction_amount=red_amt,
                    notes=f"Insurance revised to {curr} {new_ins:,.2f}"
                    if new_ins
                    else "Insurance premium revised.",
                )
            )

        # 5. Extract Additional Cash / Consumer Discounts
        disc_match = re.search(
            r"(?:extra|additional|special|consumer|cash|corporate|dealer)\s+(?:discount|offer|scheme|bonus)\s+(?:of\s+)?(?:rs\.?|₹|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,7})",
            text_lower,
        )
        if disc_match:
            disc_amt = _parse_amount(disc_match.group(1))
            if disc_amt:
                extracted_actions.append(
                    ExtractedDealerAction(
                        action_type=DealerActionType.DISCOUNT_ADDED,
                        target_component_name="Additional Discount",
                        raw_text_snippet=dealer_text[
                            max(0, disc_match.start() - 5) : min(
                                len(dealer_text), disc_match.end() + 10
                            )
                        ].strip(),
                        reduction_amount=disc_amt,
                        notes=f"Additional discount of {curr} {disc_amt:,.2f} applied.",
                    )
                )

        # 6. Extract Stated Final / Counter Total
        counter_total_match = re.search(
            r"(?:final|net|revised|counter|new|best)\s+(?:on[- ]road|total|price|offer|amount|\s)*?(?:is|will be|of|:)?\s*(?:rs\.?|₹|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{5,8})",
            text_lower,
        ) or re.search(
            r"(?:pay|take it for|give it for)\s*(?:at|for|:)?\s*(?:rs\.?|₹|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{5,8})",
            text_lower,
        )

        stated_counter_total = None
        if counter_total_match:
            stated_counter_total = _parse_amount(counter_total_match.group(1))
            if stated_counter_total and (orig_tot is None or stated_counter_total > orig_tot * 0.4):
                extracted_actions.append(
                    ExtractedDealerAction(
                        action_type=DealerActionType.COUNTER_TOTAL_STATED,
                        target_component_name="Stated Counter-Offer Total",
                        raw_text_snippet=dealer_text[
                            max(0, counter_total_match.start() - 5) : min(
                                len(dealer_text), counter_total_match.end() + 10
                            )
                        ].strip(),
                        revised_amount=stated_counter_total,
                        notes=f"Stated net price: {curr} {stated_counter_total:,.2f}",
                    )
                )

        # 7. Deterministic Arithmetic & Math Reconciliation
        total_red = round(
            sum(a.reduction_amount for a in extracted_actions if a.reduction_amount is not None),
            2,
        )
        calc_new_tot = None
        reconciliation_diff = None
        recon_status = "INCOMPLETE_DATA"

        if orig_tot is not None:
            calc_new_tot = round(orig_tot - total_red, 2)
            if stated_counter_total is not None:
                diff = round(abs(calc_new_tot - stated_counter_total), 2)
                reconciliation_diff = diff
                if diff <= 1.0:
                    recon_status = "RECONCILED"
                else:
                    recon_status = "DISCREPANCY"
            else:
                recon_status = "RECONCILED"
        elif stated_counter_total is not None:
            calc_new_tot = stated_counter_total
            recon_status = "RECONCILED"

        # 8. Actionable Follow-up Verification Questions
        follow_ups: list[str] = [
            "Request a revised, written quotation breakdown reflecting the agreed concessions before making any advance or booking payment.",
        ]

        if any(a.action_type == DealerActionType.CHARGE_WAIVED for a in extracted_actions):
            follow_ups.append(
                "Verify that the waived handling/incidental fee is explicitly listed as ₹0 on the revised invoice to avoid re-addition at delivery."
            )

        if any(
            a.action_type == DealerActionType.PRICE_REDUCED
            and "Insurance" in a.target_component_name
            for a in extracted_actions
        ):
            follow_ups.append(
                "Confirm that the revised insurance policy retains all essential add-on riders (Zero Depreciation, RTI, Engine Protection) without coverage dilution."
            )

        if (
            recon_status == "DISCREPANCY"
            and reconciliation_diff
            and orig_tot
            and stated_counter_total
        ):
            follow_ups.append(
                f"Clarify the {curr} {reconciliation_diff:,.2f} variance between the stated final total ({curr} {stated_counter_total:,.2f}) and the sum of itemized concessions ({curr} {calc_new_tot:,.2f})."
            )

        # 9. Neutral Summary Text
        action_count = len(extracted_actions)
        if orig_tot and calc_new_tot:
            summary = (
                f"Extracted {action_count} negotiation items from dealer communication. "
                f"Total itemized reductions sum to {curr} {total_red:,.2f}, bringing the estimated total from "
                f"{curr} {orig_tot:,.2f} to {curr} {calc_new_tot:,.2f}."
            )
        elif stated_counter_total:
            summary = (
                f"Extracted {action_count} negotiation items from dealer communication with a stated counter-offer "
                f"of {curr} {stated_counter_total:,.2f} (itemized concessions: {curr} {total_red:,.2f})."
            )
        else:
            summary = (
                f"Extracted {action_count} negotiation items from dealer communication with total itemized "
                f"concessions of {curr} {total_red:,.2f}."
            )

        if recon_status == "DISCREPANCY" and reconciliation_diff:
            summary += f" Note: A discrepancy of {curr} {reconciliation_diff:,.2f} was detected between stated counter-offer and itemized deductions."

        return DealerResponseAnalysisResult(
            user_id=user_id,
            original_document_id=orig_doc_id,
            dealer_raw_text=dealer_text,
            extracted_actions=extracted_actions,
            currency=curr,
            original_total=orig_tot,
            calculated_new_total=calc_new_tot,
            stated_counter_total=stated_counter_total,
            total_reduction=total_red if total_red > 0 else None,
            math_reconciliation_status=recon_status,
            reconciliation_difference=reconciliation_diff,
            follow_up_recommendations=follow_ups,
            summary_text=summary,
        )
