"use client";

import React, { useState } from "react";
import {
  HelpCircle,
  Copy,
  Check,
  Sparkles,
  Scale,
  Split,
  Calculator,
  MessageSquareQuote,
  ShieldAlert,
  ChevronRight,
  ExternalLink,
  Layers,
} from "lucide-react";
import {
  ExtraCostAnalysisResult,
  FinancialComponent,
  LineItem,
  PotentialCostReductionSummary,
  SmartCostReductionQuestion,
  ValidationCheck,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";
import { FinancialValue, Button } from "./ui";

interface WaysToReviewCostCardProps {
  components?: FinancialComponent[];
  lineItems?: LineItem[];
  extraCostAnalysis?: ExtraCostAnalysisResult | null;
  costReductionSummary?: PotentialCostReductionSummary | null;
  smartQuestions?: SmartCostReductionQuestion[];
  validationChecks?: ValidationCheck[];
  currency?: string | null;
  onInspectEvidence?: (evidenceText: string) => void;
}

export type ReviewGroupKey =
  | "ALL"
  | "POTENTIALLY_OPTIONAL"
  | "POTENTIALLY_NEGOTIABLE"
  | "COMPARE_ALTERNATIVES"
  | "POTENTIAL_OVERLAPS"
  | "AMOUNT_DISCREPANCIES"
  | "UNEXPLAINED_CHARGES"
  | "QUESTIONS_TO_ASK";

export interface ReviewCardItem {
  id: string;
  chargeName: string;
  amount: number | null;
  whyItNeedsReview: string;
  evidence: string;
  questionToAsk: string;
  suggestedAction?: string | null;
  group:
    | "POTENTIALLY_OPTIONAL"
    | "POTENTIALLY_NEGOTIABLE"
    | "COMPARE_ALTERNATIVES"
    | "POTENTIAL_OVERLAPS"
    | "AMOUNT_DISCREPANCIES"
    | "UNEXPLAINED_CHARGES"
    | "QUESTIONS_TO_ASK";
  groupTitle: string;
}

export const WaysToReviewCostCard: React.FC<WaysToReviewCostCardProps> = ({
  components = [],
  lineItems = [],
  extraCostAnalysis,
  costReductionSummary,
  smartQuestions = [],
  validationChecks = [],
  currency = "INR",
  onInspectEvidence,
}) => {
  const [activeGroup, setActiveGroup] = useState<ReviewGroupKey>("ALL");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const getAmount = (comp: FinancialComponent): number => {
    return Number(comp.amount?.normalized_value || 0);
  };

  const items: ReviewCardItem[] = [];
  const seenChargeKeys = new Set<string>();

  // ── 1. POTENTIALLY OPTIONAL ──
  components.forEach((c) => {
    const cat = (c.category || "").toLowerCase();
    const name = (c.normalized_name || c.name || "").toLowerCase();
    const opt = (c.optionality_status || "").toLowerCase();
    const amt = getAmount(c);
    const amtStr = amt > 0 ? formatCurrency(amt, currency) : "";

    const isWarranty =
      cat.includes("warranty") ||
      name.includes("warranty");
    const isAccessory =
      cat.includes("accessory") ||
      name.includes("accessory") ||
      name.includes("accessories");
    const isPackage =
      cat.includes("package") ||
      name.includes("dealer package") ||
      name.includes("service package") ||
      name.includes("basic kit") ||
      name.includes("essential kit");

    if (isWarranty || isAccessory || isPackage || opt === "potentially_optional" || opt === "confirmed_optional") {
      const chargeTitle = c.normalized_label || c.normalized_name || c.name;
      const key = `opt:${chargeTitle}:${amt}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        let why = "Potentially optional. Verify whether it is required or can be removed.";
        let question = amt > 0 ? `Is the ${amtStr} ${chargeTitle.toLowerCase()} optional?` : `Is ${chargeTitle} optional?`;

        if (isAccessory) {
          why = "Potentially optional. Verify whether accessories are required for delivery or if individual items can be unbundled.";
          question = "Are these accessories required for delivery?";
        } else if (isWarranty) {
          why = "Potentially optional. Verify whether it is required or can be removed.";
          question = amt > 0 ? `Is the ${amtStr} extended warranty package optional?` : "Is the extended warranty package optional?";
        }

        items.push({
          id: `opt-${c.component_id}`,
          chargeName: chargeTitle,
          amount: amt > 0 ? amt : null,
          whyItNeedsReview: why,
          evidence: c.evidence || `Quotation line: '${chargeTitle}${amt > 0 ? ` — ${amtStr}` : ""}'`,
          questionToAsk: question,
          group: "POTENTIALLY_OPTIONAL",
          groupTitle: "1. POTENTIALLY OPTIONAL",
        });
      }
    }
  });

  // ── 2. POTENTIALLY NEGOTIABLE ──
  components.forEach((c) => {
    const cat = (c.category || "").toLowerCase();
    const name = (c.normalized_name || c.name || "").toLowerCase();
    const amt = getAmount(c);
    const amtStr = amt > 0 ? formatCurrency(amt, currency) : "";

    const isDealerFee =
      cat === "handling_fee" ||
      cat === "logistics_fee" ||
      cat === "processing_fee" ||
      name.includes("handling") ||
      name.includes("logistics") ||
      name.includes("processing") ||
      name.includes("documentation") ||
      name.includes("depot") ||
      name.includes("incidental");

    if (isDealerFee) {
      const chargeTitle = c.normalized_label || c.normalized_name || c.name;
      const key = `neg:${chargeTitle}:${amt}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        items.push({
          id: `neg-${c.component_id}`,
          chargeName: chargeTitle,
          amount: amt > 0 ? amt : null,
          whyItNeedsReview: "Potentially negotiable. Verify whether this dealer charge can be waived or negotiated under consumer guidelines.",
          evidence: c.evidence || `Quotation line: '${chargeTitle}${amt > 0 ? ` — ${amtStr}` : ""}'`,
          questionToAsk: amt > 0
            ? `What service does this ${amtStr} charge cover, and is it mandatory?`
            : `What service does the '${chargeTitle}' charge cover, and is it mandatory?`,
          group: "POTENTIALLY_NEGOTIABLE",
          groupTitle: "2. POTENTIALLY NEGOTIABLE",
        });
      }
    }
  });

  // ── 3. COMPARE ALTERNATIVES ──
  components.forEach((c) => {
    const cat = (c.category || "").toLowerCase();
    const name = (c.normalized_name || c.name || "").toLowerCase();
    const amt = getAmount(c);
    const amtStr = amt > 0 ? formatCurrency(amt, currency) : "";

    if (cat === "insurance" || name.includes("insurance")) {
      const chargeTitle = c.normalized_label || c.normalized_name || c.name;
      const key = `alt:${chargeTitle}:${amt}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        items.push({
          id: `alt-${c.component_id}`,
          chargeName: chargeTitle,
          amount: amt > 0 ? amt : null,
          whyItNeedsReview: "Compare available insurance options. Verify whether the quoted policy is required.",
          evidence: c.evidence || `Quotation line: '${chargeTitle}${amt > 0 ? ` — ${amtStr}` : ""}'`,
          questionToAsk: "Can I choose my own insurance provider?",
          group: "COMPARE_ALTERNATIVES",
          groupTitle: "3. COMPARE ALTERNATIVES",
        });
      }
    }

    if (cat === "fastag" || name.includes("fastag")) {
      if (amt > 500) {
        const chargeTitle = c.normalized_label || c.normalized_name || c.name;
        const key = `alt:${chargeTitle}:${amt}`;
        if (!seenChargeKeys.has(key)) {
          seenChargeKeys.add(key);

          items.push({
            id: `alt-${c.component_id}`,
            chargeName: chargeTitle,
            amount: amt,
            whyItNeedsReview: "Compare available issuing options. Official FASTag issuance through banks typically incurs statutory fees of ₹200–₹500.",
            evidence: c.evidence || `Quotation line: '${chargeTitle} — ${amtStr}'`,
            questionToAsk: `What is the breakdown of the ${amtStr} FASTag charge, and can I obtain my own tag directly?`,
            group: "COMPARE_ALTERNATIVES",
            groupTitle: "3. COMPARE ALTERNATIVES",
          });
        }
      }
    }
  });

  // ── 4. POTENTIAL OVERLAPS ──
  // Check pairs of components or duplicate flags
  for (let i = 0; i < components.length; i++) {
    for (let j = i + 1; j < components.length; j++) {
      const c1 = components[i];
      const c2 = components[j];
      const c1Cat = (c1.category || "").toLowerCase();
      const c2Cat = (c2.category || "").toLowerCase();

      if (["base_price", "ex_showroom_price", "total", "subtotal", "amount_paid", "balance_due"].includes(c1Cat)) {
        continue;
      }

      const sameCat = c1Cat === c2Cat && c1Cat !== "other_fee" && c1Cat !== "unknown";
      const namesSimilar =
        c1.normalized_name &&
        c2.normalized_name &&
        c1.normalized_name.toLowerCase() === c2.normalized_name.toLowerCase() &&
        c1.name.toLowerCase() !== c2.name.toLowerCase();

      if (sameCat || namesSimilar) {
        const amt1 = getAmount(c1);
        const amt2 = getAmount(c2);
        const pairAmount = Math.min(amt1, amt2) > 0 ? Math.min(amt1, amt2) : Math.max(amt1, amt2);
        const key = `overlap:${c1.name}:${c2.name}`;

        if (!seenChargeKeys.has(key)) {
          seenChargeKeys.add(key);

          items.push({
            id: `overlap-${c1.component_id}-${c2.component_id}`,
            chargeName: `${c1.name} / ${c2.name}`,
            amount: pairAmount > 0 ? pairAmount : null,
            whyItNeedsReview: "Potential overlap — verify whether this is already included.",
            evidence: `Quotation lines: '${c1.name}' (${formatCurrency(amt1, currency)}) and '${c2.name}' (${formatCurrency(amt2, currency)})`,
            questionToAsk: `Can you explain why both ${c1.name} and ${c2.name} are being charged separately?`,
            group: "POTENTIAL_OVERLAPS",
            groupTitle: "4. POTENTIAL OVERLAPS",
          });
        }
      }
    }
  }

  // Ingest from costReductionSummary (Tiers)
  if (costReductionSummary) {
    const allTierItems = [
      ...costReductionSummary.confirmed_optional_items,
      ...costReductionSummary.potentially_optional_items,
    ];
    allTierItems.forEach((ti) => {
      const key = `opt:${ti.name}:${ti.amount}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);
        items.push({
          id: `opt-${ti.component_id}`,
          chargeName: ti.name,
          amount: ti.amount > 0 ? ti.amount : null,
          whyItNeedsReview: `${ti.status_label}. Verify whether it can be removed from total commitment.`,
          evidence: ti.evidence || `Quotation line: '${ti.name}'`,
          questionToAsk: ti.amount > 0 ? `Is the ${formatCurrency(ti.amount, currency)} ${ti.name.toLowerCase()} package optional?` : `Is ${ti.name} optional?`,
          group: "POTENTIALLY_OPTIONAL",
          groupTitle: "1. POTENTIALLY OPTIONAL",
        });
      }
    });
  }

  // Ingest from extraCostAnalysis (Dealer added, bundled, duplicates)
  if (extraCostAnalysis?.flagged_costs) {
    extraCostAnalysis.flagged_costs.forEach((fc) => {
      const fcTitle = fc.normalized_name || fc.flag_label;
      const key = `fc:${fcTitle}:${fc.amount}`;
      if (seenChargeKeys.has(key)) return;

      if (fc.flag_type === "potentially_optional" || fc.flag_type === "bundled_package") {
        seenChargeKeys.add(key);
        items.push({
          id: `opt-${fc.component_id}`,
          chargeName: fcTitle,
          amount: fc.amount > 0 ? fc.amount : null,
          whyItNeedsReview: fc.why_flagged || "Potentially optional. Verify whether it is required or can be removed.",
          evidence: fc.evidence || `Quotation line: '${fcTitle}'`,
          questionToAsk: fc.bundled_questions?.[0] || (fc.amount > 0 ? `Is the ${formatCurrency(fc.amount, currency)} ${fcTitle.toLowerCase()} optional?` : `Is ${fcTitle} optional?`),
          group: "POTENTIALLY_OPTIONAL",
          groupTitle: "1. POTENTIALLY OPTIONAL",
        });
      } else if (fc.flag_type === "dealer_added" || fc.flag_type === "additional_charge") {
        seenChargeKeys.add(key);
        items.push({
          id: `neg-${fc.component_id}`,
          chargeName: fcTitle,
          amount: fc.amount > 0 ? fc.amount : null,
          whyItNeedsReview: fc.why_flagged || "Potentially negotiable dealer fee.",
          evidence: fc.evidence || `Quotation line: '${fcTitle}'`,
          questionToAsk: fc.bundled_questions?.[0] || `Can this ${fc.amount > 0 ? formatCurrency(fc.amount, currency) : ""} charge be waived or negotiated?`,
          group: "POTENTIALLY_NEGOTIABLE",
          groupTitle: "2. POTENTIALLY NEGOTIABLE",
        });
      } else if (fc.flag_type === "possible_duplicate") {
        seenChargeKeys.add(key);
        items.push({
          id: `overlap-${fc.component_id}`,
          chargeName: fcTitle,
          amount: fc.amount > 0 ? fc.amount : null,
          whyItNeedsReview: fc.why_flagged || "Potential overlap — verify whether this is already included.",
          evidence: fc.evidence || `Quotation line: '${fcTitle}'`,
          questionToAsk: fc.bundled_questions?.[0] || `Verify whether ${fcTitle} is already covered in another line item.`,
          suggestedAction: "Ask whether existing coverage already covers the same area.",
          group: "POTENTIAL_OVERLAPS",
          groupTitle: "4. POTENTIAL OVERLAPS",
        });
      } else if (fc.flag_type === "unclear_charge") {
        seenChargeKeys.add(key);
        items.push({
          id: `unclear-${fc.component_id}`,
          chargeName: fcTitle,
          amount: fc.amount > 0 ? fc.amount : null,
          whyItNeedsReview: fc.why_flagged || "The quotation lists this charge without an itemized explanation.",
          evidence: fc.evidence || `Quotation line: '${fcTitle}'`,
          questionToAsk: fc.bundled_questions?.[0] || `What service does this charge cover, and is it mandatory?`,
          suggestedAction: "Ask the provider to explain what the charge represents.",
          group: "UNEXPLAINED_CHARGES",
          groupTitle: "6. UNEXPLAINED CHARGES",
        });
      }
    });
  }

  // ── 5. AMOUNT DISCREPANCIES ──
  validationChecks.forEach((check) => {
    if (check.status === "FAIL") {
      const deltaVal = check.absolute_delta != null ? check.absolute_delta : null;
      const diffStr = deltaVal != null && deltaVal > 0 ? formatCurrency(deltaVal, currency) : "";
      const isLineItem = check.check_code.includes("LINE_ITEM");
      const isSubtotal = check.check_code.includes("SUBTOTAL");
      const isNetTotal = check.check_code.includes("NET_TOTAL") || check.check_code.includes("TOTAL_CONSISTENCY");

      let title = "Amount Discrepancy";
      let why = check.message || "Arithmetic discrepancy requires verification.";
      let qText = diffStr ? `The calculation differs by ${diffStr}. Which amount is correct?` : (check.message || "Please clarify this calculation.");
      let amountVal = deltaVal;

      if (isLineItem) {
        const failedItem = lineItems.find((li) =>
          check.message?.toLowerCase().includes(String(li.description?.normalized_value || "").toLowerCase())
        );
        const itemName = failedItem?.description?.normalized_value || "Line item";
        title = `${itemName} — Line Item Calculation Discrepancy`;
        why = `Displayed values do not mathematically explain the line amount on the document.`;
        const matchingQ = smartQuestions.find((q) =>
          q.question.toLowerCase().includes(String(itemName).toLowerCase())
        );
        qText = matchingQ?.question || `Could you please clarify how the line item amount for ${itemName} is calculated?`;
        if (failedItem?.total_price?.normalized_value) {
          amountVal = Number(failedItem.total_price.normalized_value);
        }
      } else if (isSubtotal) {
        title = "Component Reconciliation Discrepancy";
        why = `Mathematical discrepancy of ${diffStr} exists between the listed charges and stated subtotal.`;
        qText = `The listed components differ from the stated subtotal by ${diffStr}. Which amount is correct?`;
      } else if (isNetTotal) {
        title = "Quoted Total Discrepancy";
        why = `Mathematical discrepancy of ${diffStr} exists between subtotal minus discounts and the final quoted total.`;
        qText = `The calculated total differs from the quoted total by ${diffStr}. Which amount is correct?`;
      }

      const key = `disc:${check.check_code}:${title}:${amountVal}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);
        items.push({
          id: `disc-${check.validation_id}`,
          chargeName: title,
          amount: amountVal,
          whyItNeedsReview: why,
          evidence: `Validation check: ${check.check_code} (${check.message})`,
          questionToAsk: qText,
          group: "AMOUNT_DISCREPANCIES",
          groupTitle: "5. AMOUNT DISCREPANCIES",
        });
      }
    }
  });

  // ── 6. QUESTIONS TO ASK (Compiled discovery questions) ──
  if (smartQuestions && smartQuestions.length > 0) {
    smartQuestions.forEach((q) => {
      const key = `qta:${q.question}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        items.push({
          id: `qta-${q.question_id}`,
          chargeName: q.related_charge || "Quotation Item",
          amount: q.amount_involved ?? null,
          whyItNeedsReview: q.reason || "Clarification needed prior to transaction authorization.",
          evidence: q.ocr_line || q.evidence_source || "Quotation document",
          questionToAsk: q.question,
          suggestedAction: q.suggested_action,
          group: "QUESTIONS_TO_ASK",
          groupTitle: "QUESTIONS TO ASK",
        });
      }
    });
  }

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const groupCounts: Record<ReviewGroupKey, number> = {
    ALL: items.length,
    POTENTIALLY_OPTIONAL: items.filter((i) => i.group === "POTENTIALLY_OPTIONAL").length,
    POTENTIALLY_NEGOTIABLE: items.filter((i) => i.group === "POTENTIALLY_NEGOTIABLE").length,
    COMPARE_ALTERNATIVES: items.filter((i) => i.group === "COMPARE_ALTERNATIVES").length,
    POTENTIAL_OVERLAPS: items.filter((i) => i.group === "POTENTIAL_OVERLAPS").length,
    AMOUNT_DISCREPANCIES: items.filter((i) => i.group === "AMOUNT_DISCREPANCIES").length,
    UNEXPLAINED_CHARGES: items.filter((i) => i.group === "UNEXPLAINED_CHARGES").length,
    QUESTIONS_TO_ASK: items.filter((i) => i.group === "QUESTIONS_TO_ASK").length,
  };

  const filteredItems =
    activeGroup === "ALL" ? items : items.filter((i) => i.group === activeGroup);

  const getGroupBadgeColor = (group: ReviewCardItem["group"]) => {
    switch (group) {
      case "POTENTIALLY_OPTIONAL":
        return "bg-amber-500/15 text-amber-300 border-amber-500/30";
      case "POTENTIALLY_NEGOTIABLE":
        return "bg-indigo-500/15 text-indigo-300 border-indigo-500/30";
      case "COMPARE_ALTERNATIVES":
        return "bg-cyan-500/15 text-cyan-300 border-cyan-500/30";
      case "POTENTIAL_OVERLAPS":
        return "bg-purple-500/15 text-purple-300 border-purple-500/30";
      case "AMOUNT_DISCREPANCIES":
        return "bg-rose-500/15 text-rose-300 border-rose-500/30";
      case "UNEXPLAINED_CHARGES":
        return "bg-orange-500/15 text-orange-300 border-orange-500/30";
      case "QUESTIONS_TO_ASK":
        return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
      default:
        return "bg-white/10 text-slate-300 border-white/10";
    }
  };

  return (
    <div className="surface-card rounded-2xl border border-white/10 bg-app-card p-4 sm:p-6 shadow-card space-y-5">
      {/* Title & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/25">
              <Scale className="w-3.5 h-3.5" />
              BUYER DISCOVERY
            </span>
            <span className="text-xs text-slate-400 font-mono">
              6 Structured Review Dimensions
            </span>
          </div>
          <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            WAYS TO REVIEW THIS COST
          </h2>
          <p className="text-xs text-slate-400">
            Factual inquiries and verification items grounded strictly in document evidence. Never promising savings.
          </p>
        </div>

        <div className="text-xs font-mono px-3 py-1.5 rounded-xl bg-app-cardSubtle border border-white/10 text-slate-300 self-start sm:self-auto">
          {items.length} item{items.length !== 1 ? "s" : ""} to review
        </div>
      </div>

      {/* Group Navigation Tabs (Accessible, touch-friendly min 44px) */}
      <div
        className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none text-xs"
        role="tablist"
        aria-label="Review Categories"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeGroup === "ALL"}
          onClick={() => setActiveGroup("ALL")}
          className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
            activeGroup === "ALL"
              ? "bg-slate-100 text-slate-950 border-white shadow-sm"
              : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
          }`}
        >
          All Items
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
            {groupCounts.ALL}
          </span>
        </button>

        {groupCounts.POTENTIALLY_OPTIONAL > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "POTENTIALLY_OPTIONAL"}
            onClick={() => setActiveGroup("POTENTIALLY_OPTIONAL")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "POTENTIALLY_OPTIONAL"
                ? "bg-amber-400 text-slate-950 border-amber-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            1. Potentially Optional
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIALLY_OPTIONAL}
            </span>
          </button>
        )}

        {groupCounts.POTENTIALLY_NEGOTIABLE > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "POTENTIALLY_NEGOTIABLE"}
            onClick={() => setActiveGroup("POTENTIALLY_NEGOTIABLE")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "POTENTIALLY_NEGOTIABLE"
                ? "bg-indigo-400 text-slate-950 border-indigo-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            2. Potentially Negotiable
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIALLY_NEGOTIABLE}
            </span>
          </button>
        )}

        {groupCounts.COMPARE_ALTERNATIVES > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "COMPARE_ALTERNATIVES"}
            onClick={() => setActiveGroup("COMPARE_ALTERNATIVES")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "COMPARE_ALTERNATIVES"
                ? "bg-cyan-400 text-slate-950 border-cyan-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            3. Compare Alternatives
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.COMPARE_ALTERNATIVES}
            </span>
          </button>
        )}

        {groupCounts.POTENTIAL_OVERLAPS > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "POTENTIAL_OVERLAPS"}
            onClick={() => setActiveGroup("POTENTIAL_OVERLAPS")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "POTENTIAL_OVERLAPS"
                ? "bg-purple-400 text-slate-950 border-purple-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            4. Potential Overlaps
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIAL_OVERLAPS}
            </span>
          </button>
        )}

        {groupCounts.AMOUNT_DISCREPANCIES > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "AMOUNT_DISCREPANCIES"}
            onClick={() => setActiveGroup("AMOUNT_DISCREPANCIES")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "AMOUNT_DISCREPANCIES"
                ? "bg-rose-400 text-slate-950 border-rose-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            5. Amount Discrepancies
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.AMOUNT_DISCREPANCIES}
            </span>
          </button>
        )}

        {groupCounts.UNEXPLAINED_CHARGES > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "UNEXPLAINED_CHARGES"}
            onClick={() => setActiveGroup("UNEXPLAINED_CHARGES")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "UNEXPLAINED_CHARGES"
                ? "bg-orange-400 text-slate-950 border-orange-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            6. Unexplained Charges
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.UNEXPLAINED_CHARGES}
            </span>
          </button>
        )}

        {groupCounts.QUESTIONS_TO_ASK > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeGroup === "QUESTIONS_TO_ASK"}
            onClick={() => setActiveGroup("QUESTIONS_TO_ASK")}
            className={`px-3.5 py-2.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border min-h-[44px] touch-target ${
              activeGroup === "QUESTIONS_TO_ASK"
                ? "bg-emerald-400 text-slate-950 border-emerald-400 shadow-sm"
                : "bg-slate-900/80 text-slate-300 border-white/8 hover:bg-white/5"
            }`}
          >
            Questions to Ask
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.QUESTIONS_TO_ASK}
            </span>
          </button>
        )}
      </div>

      {/* Cards List: Each card has: charge name, amount, why it needs review, evidence, question to ask */}
      <div className="grid grid-cols-1 gap-4">
        {filteredItems.map((item) => {
          const isCopied = copiedId === item.id;
          const badgeColor = getGroupBadgeColor(item.group);

          return (
            <div
              key={item.id}
              className="p-4 sm:p-5 rounded-xl bg-app-cardSubtle border border-white/8 hover:border-white/16 transition space-y-3 shadow-subtle"
            >
              {/* Header: Charge Name, Category Pill, and Amount */}
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${badgeColor}`}
                    >
                      {item.groupTitle}
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
                    {item.chargeName}
                  </h3>
                </div>

                {item.amount != null && (
                  <div className="text-right shrink-0">
                    <FinancialValue
                      amount={item.amount}
                      currency={currency}
                      variant="item"
                      className="text-base sm:text-lg font-extrabold text-white block"
                    />
                    <span className="text-[10px] text-slate-400 font-sans">
                      Quoted amount
                    </span>
                  </div>
                )}
              </div>

              {/* Why it needs review */}
              <div className="bg-app-cardInset rounded-lg p-3 border border-white/4 space-y-1">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 block">
                  Why it needs review
                </span>
                <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">
                  {item.whyItNeedsReview}
                </p>
              </div>

              {/* Evidence */}
              <div className="flex items-center justify-between text-xs text-slate-400 gap-2">
                <div className="flex items-start gap-1.5 min-w-0">
                  <span className="font-semibold text-slate-300 shrink-0">Evidence:</span>
                  <span className="font-mono text-[11px] text-slate-300 break-words">
                    {item.evidence}
                  </span>
                </div>
                {onInspectEvidence && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onInspectEvidence(item.chargeName || item.evidence)}
                    className="text-[11px] py-1 px-2.5 min-h-[32px] text-brand-400 hover:text-brand-300 shrink-0"
                  >
                    <span>Inspect on slip</span>
                    <ExternalLink className="w-3 h-3" />
                  </Button>
                )}
              </div>

              {/* Question to ask with Copy Button & Action */}
              <div className="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-app-cardInset p-3 rounded-lg border border-white/6">
                <div className="space-y-1">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-brand-300 flex items-center gap-1">
                    <MessageSquareQuote className="w-3 h-3 text-brand-400" />
                    Question to ask seller
                  </span>
                  <p className="text-xs sm:text-sm font-medium text-white italic">
                    "{item.questionToAsk}"
                  </p>
                  {item.suggestedAction && (
                    <div className="flex items-center gap-1.5 text-[11px] text-brand-300 font-medium pt-0.5">
                      <span className="px-1.5 py-0.5 rounded bg-brand-500/15 border border-brand-500/25 text-[10px] uppercase tracking-wider font-semibold">
                        Action
                      </span>
                      <span>{item.suggestedAction}</span>
                    </div>
                  )}
                </div>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleCopy(item.id, item.questionToAsk)}
                  className={`self-start sm:self-auto shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 ${
                    isCopied ? "border-emerald-500/30 text-emerald-300 bg-emerald-500/10" : ""
                  }`}
                  title="Copy question to ask seller"
                >
                  {isCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-400" />
                      <span>Copy</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

