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
  SmartCostReductionQuestion,
  ValidationCheck,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface WaysToReviewCostCardProps {
  components: FinancialComponent[];
  extraCostAnalysis?: ExtraCostAnalysisResult | null;
  smartQuestions?: SmartCostReductionQuestion[];
  validationChecks?: ValidationCheck[];
  currency?: string | null;
}

export type ReviewGroupKey =
  | "ALL"
  | "POTENTIALLY_OPTIONAL"
  | "POTENTIALLY_NEGOTIABLE"
  | "COMPARE_ALTERNATIVES"
  | "POTENTIAL_OVERLAPS"
  | "AMOUNT_DISCREPANCIES"
  | "QUESTIONS_TO_ASK";

export interface ReviewCardItem {
  id: string;
  chargeName: string;
  amount: number | null;
  whyItNeedsReview: string;
  evidence: string;
  questionToAsk: string;
  group:
    | "POTENTIALLY_OPTIONAL"
    | "POTENTIALLY_NEGOTIABLE"
    | "COMPARE_ALTERNATIVES"
    | "POTENTIAL_OVERLAPS"
    | "AMOUNT_DISCREPANCIES"
    | "QUESTIONS_TO_ASK";
  groupTitle: string;
}

export const WaysToReviewCostCard: React.FC<WaysToReviewCostCardProps> = ({
  components,
  extraCostAnalysis,
  smartQuestions,
  validationChecks = [],
  currency = "INR",
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

  // ── 5. AMOUNT DISCREPANCIES ──
  validationChecks.forEach((check) => {
    if (check.status === "FAIL" && check.absolute_delta != null && check.absolute_delta > 0) {
      const diffStr = formatCurrency(check.absolute_delta, currency);
      const isSubtotal = check.check_code.includes("SUBTOTAL");
      const title = isSubtotal ? "Component Reconciliation Discrepancy" : "Quoted Total Discrepancy";
      const key = `disc:${check.check_code}:${check.absolute_delta}`;

      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        items.push({
          id: `disc-${check.validation_id}`,
          chargeName: title,
          amount: check.absolute_delta,
          whyItNeedsReview: `Mathematical discrepancy of ${diffStr} exists between the listed charges and stated amount on the quotation.`,
          evidence: `Validation check: ${check.check_code} (${check.message})`,
          questionToAsk: `The listed components differ from the stated amount by ${diffStr}. Which amount is correct?`,
          group: "AMOUNT_DISCREPANCIES",
          groupTitle: "5. AMOUNT DISCREPANCIES",
        });
      }
    }
  });

  // ── 6. QUESTIONS TO ASK (Compiled discovery questions) ──
  if (smartQuestions && smartQuestions.length > 0) {
    smartQuestions.slice(0, 4).forEach((q) => {
      const key = `qta:${q.question}`;
      if (!seenChargeKeys.has(key)) {
        seenChargeKeys.add(key);

        items.push({
          id: `qta-${q.question_id}`,
          chargeName: q.related_charge || "Quotation Item",
          amount: q.amount_involved ?? null,
          whyItNeedsReview: q.reason || "Clarification needed prior to transaction authorization.",
          evidence: q.evidence_source || "Quotation document",
          questionToAsk: q.question,
          group: "QUESTIONS_TO_ASK",
          groupTitle: "6. QUESTIONS TO ASK",
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
      case "QUESTIONS_TO_ASK":
        return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    }
  };

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-6 border border-white/10 shadow-2xl space-y-5">
      {/* Title & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
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

        <div className="text-xs font-mono px-3 py-1.5 rounded-xl bg-slate-900 border border-white/10 text-slate-300 self-start sm:self-auto">
          {items.length} item{items.length !== 1 ? "s" : ""} to review
        </div>
      </div>

      {/* Group Navigation Tabs (Phone-friendly horizontal scroll) */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none text-xs">
        <button
          onClick={() => setActiveGroup("ALL")}
          className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
            activeGroup === "ALL"
              ? "bg-white text-slate-950 border-white shadow"
              : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
          }`}
        >
          All Items
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
            {groupCounts.ALL}
          </span>
        </button>

        {groupCounts.POTENTIALLY_OPTIONAL > 0 && (
          <button
            onClick={() => setActiveGroup("POTENTIALLY_OPTIONAL")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "POTENTIALLY_OPTIONAL"
                ? "bg-amber-400 text-slate-950 border-amber-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            1. Potentially Optional
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIALLY_OPTIONAL}
            </span>
          </button>
        )}

        {groupCounts.POTENTIALLY_NEGOTIABLE > 0 && (
          <button
            onClick={() => setActiveGroup("POTENTIALLY_NEGOTIABLE")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "POTENTIALLY_NEGOTIABLE"
                ? "bg-indigo-400 text-slate-950 border-indigo-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            2. Potentially Negotiable
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIALLY_NEGOTIABLE}
            </span>
          </button>
        )}

        {groupCounts.COMPARE_ALTERNATIVES > 0 && (
          <button
            onClick={() => setActiveGroup("COMPARE_ALTERNATIVES")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "COMPARE_ALTERNATIVES"
                ? "bg-cyan-400 text-slate-950 border-cyan-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            3. Compare Alternatives
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.COMPARE_ALTERNATIVES}
            </span>
          </button>
        )}

        {groupCounts.POTENTIAL_OVERLAPS > 0 && (
          <button
            onClick={() => setActiveGroup("POTENTIAL_OVERLAPS")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "POTENTIAL_OVERLAPS"
                ? "bg-purple-400 text-slate-950 border-purple-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            4. Potential Overlaps
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.POTENTIAL_OVERLAPS}
            </span>
          </button>
        )}

        {groupCounts.AMOUNT_DISCREPANCIES > 0 && (
          <button
            onClick={() => setActiveGroup("AMOUNT_DISCREPANCIES")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "AMOUNT_DISCREPANCIES"
                ? "bg-rose-400 text-slate-950 border-rose-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            5. Amount Discrepancies
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {groupCounts.AMOUNT_DISCREPANCIES}
            </span>
          </button>
        )}

        {groupCounts.QUESTIONS_TO_ASK > 0 && (
          <button
            onClick={() => setActiveGroup("QUESTIONS_TO_ASK")}
            className={`px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition flex items-center gap-1.5 border ${
              activeGroup === "QUESTIONS_TO_ASK"
                ? "bg-emerald-400 text-slate-950 border-emerald-400 shadow"
                : "bg-slate-900/80 text-slate-300 border-white/10 hover:bg-white/5"
            }`}
          >
            6. Questions to Ask
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
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
              className="p-4 sm:p-5 rounded-xl bg-slate-900/80 border border-white/10 hover:border-white/20 transition space-y-3 shadow-md"
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
                    <span className="text-base sm:text-lg font-mono font-extrabold text-white block">
                      {formatCurrency(item.amount, currency)}
                    </span>
                    <span className="text-[10px] text-slate-400 font-sans">
                      Quoted amount
                    </span>
                  </div>
                )}
              </div>

              {/* Why it needs review */}
              <div className="bg-slate-950/60 rounded-lg p-3 border border-white/5 space-y-1">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 block">
                  Why it needs review
                </span>
                <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">
                  {item.whyItNeedsReview}
                </p>
              </div>

              {/* Evidence */}
              <div className="text-xs text-slate-400 flex items-start gap-1.5">
                <span className="font-semibold text-slate-300 shrink-0">Evidence:</span>
                <span className="font-mono text-[11px] text-slate-300 break-words">
                  {item.evidence}
                </span>
              </div>

              {/* Question to ask with Copy Button */}
              <div className="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-brand-500/5 p-3 rounded-lg border border-brand-500/20">
                <div className="space-y-0.5">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-brand-300 flex items-center gap-1">
                    <MessageSquareQuote className="w-3 h-3 text-brand-400" />
                    Question to ask seller
                  </span>
                  <p className="text-xs sm:text-sm font-medium text-white italic">
                    "{item.questionToAsk}"
                  </p>
                </div>

                <button
                  onClick={() => handleCopy(item.id, item.questionToAsk)}
                  className={`self-start sm:self-auto shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition font-medium border ${
                    isCopied
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                      : "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700"
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
                      <span>Copy Question</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
