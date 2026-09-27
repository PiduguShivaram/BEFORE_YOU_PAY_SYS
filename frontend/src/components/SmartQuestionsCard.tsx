"use client";

import React, { useState } from "react";
import {
  MessageSquareQuote,
  Copy,
  Check,
  HelpCircle,
  TrendingDown,
  FileText,
  Shield,
  ChevronDown,
  ChevronUp,
  Tag,
  SlidersHorizontal,
  Info,
} from "lucide-react";
import { SmartCostReductionQuestion } from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface SmartQuestionsCardProps {
  questions: SmartCostReductionQuestion[];
  currency?: string | null;
}

export const SmartQuestionsCard: React.FC<SmartQuestionsCardProps> = ({
  questions,
  currency = "INR",
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedScoringId, setExpandedScoringId] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>("ALL");

  if (!questions || questions.length === 0) {
    return null;
  }

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId(null);
    }, 2000);
  };

  const toggleScoring = (id: string) => {
    setExpandedScoringId((prev) => (prev === id ? null : id));
  };

  const filterQuestions = (qList: SmartCostReductionQuestion[]) => {
    if (selectedFilter === "ALL") return qList;
    if (selectedFilter === "WARRANTY_BUNDLE") {
      return qList.filter((q) =>
        ["EXTENDED_WARRANTY", "WARRANTY", "ACCESSORY", "ACCESSORY_PACKAGE", "DEALER_PACKAGE", "SERVICE_PACKAGE"].includes(
          (q.category || "").toUpperCase()
        )
      );
    }
    if (selectedFilter === "FEES") {
      return qList.filter((q) =>
        ["HANDLING_FEE", "LOGISTICS_FEE", "PROCESSING_FEE", "FASTAG", "INSURANCE", "OTHER_FEE"].includes(
          (q.category || "").toUpperCase()
        )
      );
    }
    if (selectedFilter === "DISCREPANCY_OFFER") {
      return qList.filter((q) =>
        ["ARITHMETIC_DISCREPANCY", "OFFER", "DISCOUNT", "POSSIBLE_DUPLICATE"].includes(
          (q.category || "").toUpperCase()
        )
      );
    }
    return qList;
  };

  const filtered = filterQuestions(questions);

  const getCategoryBadge = (category?: string | null) => {
    const cat = (category || "").toUpperCase();
    switch (cat) {
      case "EXTENDED_WARRANTY":
      case "WARRANTY":
        return { label: "Warranty", bg: "bg-purple-500/10 text-purple-400 border-purple-500/20" };
      case "ACCESSORY":
      case "ACCESSORY_PACKAGE":
        return { label: "Accessories", bg: "bg-blue-500/10 text-blue-400 border-blue-500/20" };
      case "INSURANCE":
        return { label: "Insurance", bg: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20" };
      case "HANDLING_FEE":
      case "LOGISTICS_FEE":
      case "PROCESSING_FEE":
        return { label: "Dealer Fee", bg: "bg-amber-500/10 text-amber-400 border-amber-500/20" };
      case "DEALER_PACKAGE":
      case "SERVICE_PACKAGE":
        return { label: "Package", bg: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20" };
      case "FASTAG":
        return { label: "FASTag", bg: "bg-teal-500/10 text-teal-400 border-teal-500/20" };
      case "ARITHMETIC_DISCREPANCY":
        return { label: "Math Discrepancy", bg: "bg-red-500/10 text-red-400 border-red-500/20" };
      case "OFFER":
      case "DISCOUNT":
        return { label: "Offer / Discount", bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" };
      case "POSSIBLE_DUPLICATE":
        return { label: "Duplicate Risk", bg: "bg-rose-500/10 text-rose-400 border-rose-500/20" };
      default:
        return { label: "Clarification", bg: "bg-slate-500/10 text-slate-300 border-slate-500/20" };
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <MessageSquareQuote className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white tracking-tight">
              Questions to ask before paying
            </h3>
            <p className="text-xs text-slate-400">
              Evidence-grounded discovery questions to help you verify whether charges can be removed, reduced, or clarified.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-medium">
            {questions.length} question{questions.length !== 1 ? "s" : ""} identified
          </span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          onClick={() => setSelectedFilter("ALL")}
          className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
            selectedFilter === "ALL"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
          }`}
        >
          All ({questions.length})
        </button>
        <button
          onClick={() => setSelectedFilter("WARRANTY_BUNDLE")}
          className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
            selectedFilter === "WARRANTY_BUNDLE"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
          }`}
        >
          Warranties & Packages
        </button>
        <button
          onClick={() => setSelectedFilter("FEES")}
          className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
            selectedFilter === "FEES"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
          }`}
        >
          Fees & Insurance
        </button>
        <button
          onClick={() => setSelectedFilter("DISCREPANCY_OFFER")}
          className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
            selectedFilter === "DISCREPANCY_OFFER"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
          }`}
        >
          Math & Offers
        </button>
      </div>

      {/* Questions List */}
      <div className="space-y-4">
        {filtered.map((item, idx) => {
          const badge = getCategoryBadge(item.category);
          const isCopied = copiedId === item.question_id;
          const isScoringExpanded = expandedScoringId === item.question_id;

          return (
            <div
              key={item.question_id || idx}
              className="bg-slate-950/70 border border-slate-800/80 hover:border-slate-700/80 rounded-xl p-4 transition-all duration-200 space-y-3"
            >
              {/* Question Top Row: Category + Charge + Copy Action */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${badge.bg}`}
                  >
                    {badge.label}
                  </span>
                  <span className="text-xs text-slate-300 font-medium bg-slate-900 border border-slate-800 px-2 py-0.5 rounded-md">
                    {item.related_charge}
                  </span>
                  {item.amount_involved != null && item.amount_involved > 0 && (
                    <span className="text-xs font-semibold text-white px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700">
                      {formatCurrency(item.amount_involved, currency)}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(item.question_id, item.question)}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md font-medium transition-colors ${
                      isCopied
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                    }`}
                    title="Copy question to clipboard"
                  >
                    {isCopied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-400" />
                        <span>Copy question</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* The Actual Question */}
              <div className="bg-indigo-950/20 border-l-2 border-indigo-500 pl-3.5 py-1 rounded-r-md">
                <p className="text-sm font-semibold text-slate-100 leading-snug">
                  &ldquo;{item.question}&rdquo;
                </p>
              </div>

              {/* Reason & Potential Impact Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
                {/* Reason */}
                <div className="bg-slate-900/60 rounded-lg p-2.5 border border-slate-850 space-y-1">
                  <span className="text-slate-400 font-medium flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-slate-400" />
                    Why ask this
                  </span>
                  <p className="text-slate-300 leading-relaxed">{item.reason}</p>
                </div>

                {/* Potential Impact */}
                <div className="bg-emerald-950/15 rounded-lg p-2.5 border border-emerald-900/25 space-y-1">
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
                    Potential impact
                  </span>
                  <p className="text-emerald-200/90 leading-relaxed font-medium">
                    {item.potential_impact}
                  </p>
                </div>
              </div>

              {/* Evidence & Ranking Accordion Footer */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-900 text-[11px] text-slate-400">
                <div className="flex items-center gap-1.5 truncate">
                  <FileText className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span className="truncate text-slate-400">
                    <strong className="text-slate-300">Evidence:</strong> {item.evidence_source}
                  </span>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <button
                    onClick={() => toggleScoring(item.question_id)}
                    className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    <SlidersHorizontal className="w-3 h-3" />
                    <span>Priority {item.priority_score.toFixed(2)}</span>
                    {isScoringExpanded ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>

              {/* Expanded Transparent Scoring Breakdown */}
              {isScoringExpanded && item.ranking_factors && (
                <div className="mt-2 p-3 bg-slate-900/90 rounded-lg border border-slate-800 space-y-2 animate-in fade-in duration-200">
                  <p className="text-[11px] text-slate-300 font-semibold">
                    Transparent Ranking Factors (Measurable Criteria):
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[10px]">
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-slate-400 block">Amount (35%)</span>
                      <span className="font-semibold text-slate-200">
                        {item.ranking_factors.amount_factor != null
                          ? item.ranking_factors.amount_factor.toFixed(2)
                          : "0.00"}
                      </span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-slate-400 block">Impact (25%)</span>
                      <span className="font-semibold text-slate-200">
                        {item.ranking_factors.impact_factor != null
                          ? item.ranking_factors.impact_factor.toFixed(2)
                          : "0.00"}
                      </span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-slate-400 block">Optionality (15%)</span>
                      <span className="font-semibold text-slate-200">
                        {item.ranking_factors.optionality_uncertainty_factor != null
                          ? item.ranking_factors.optionality_uncertainty_factor.toFixed(2)
                          : "0.00"}
                      </span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-slate-400 block">Duplication (15%)</span>
                      <span className="font-semibold text-slate-200">
                        {item.ranking_factors.duplication_risk_factor != null
                          ? item.ranking_factors.duplication_risk_factor.toFixed(2)
                          : "0.00"}
                      </span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-slate-400 block">Uncertainty (10%)</span>
                      <span className="font-semibold text-slate-200">
                        {item.ranking_factors.general_uncertainty_factor != null
                          ? item.ranking_factors.general_uncertainty_factor.toFixed(2)
                          : "0.00"}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Neutral Footer Note */}
      <div className="flex items-start gap-2 pt-2 text-[11px] text-slate-500">
        <Shield className="w-3.5 h-3.5 mt-0.5 shrink-0 text-slate-500" />
        <p>
          These discovery questions are generated strictly from document findings to assist your review with the seller.
          The system does not negotiate on your behalf.
        </p>
      </div>
    </div>
  );
};
