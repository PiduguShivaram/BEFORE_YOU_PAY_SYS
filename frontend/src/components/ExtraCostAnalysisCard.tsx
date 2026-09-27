"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Package,
  Search,
  ShieldAlert,
  Sparkles,
  Tag,
  TrendingDown,
} from "lucide-react";
import { ExtraCostAnalysisResult, ExtraCostFlag } from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface ExtraCostAnalysisCardProps {
  analysis: ExtraCostAnalysisResult;
  currency?: string | null;
}

const getFlagIcon = (flagType: string) => {
  switch (flagType) {
    case "potentially_optional":
      return <Tag className="w-4 h-4" />;
    case "additional_charge":
      return <AlertTriangle className="w-4 h-4" />;
    case "dealer_added":
      return <Sparkles className="w-4 h-4" />;
    case "bundled_package":
      return <Package className="w-4 h-4" />;
    case "unclear_charge":
      return <HelpCircle className="w-4 h-4" />;
    case "possible_duplicate":
      return <ShieldAlert className="w-4 h-4" />;
    case "requires_verification":
      return <Search className="w-4 h-4" />;
    default:
      return <AlertTriangle className="w-4 h-4" />;
  }
};

const getFlagStyle = (flagType: string) => {
  switch (flagType) {
    case "potentially_optional":
      return {
        bg: "bg-amber-500/8",
        border: "border-amber-500/25",
        accent: "text-amber-300",
        accentBg: "bg-amber-500/15",
        dot: "bg-amber-400",
        badgeBg: "bg-amber-500/12 text-amber-300 border-amber-500/25",
      };
    case "additional_charge":
      return {
        bg: "bg-rose-500/8",
        border: "border-rose-500/25",
        accent: "text-rose-300",
        accentBg: "bg-rose-500/15",
        dot: "bg-rose-400",
        badgeBg: "bg-rose-500/12 text-rose-300 border-rose-500/25",
      };
    case "dealer_added":
      return {
        bg: "bg-violet-500/8",
        border: "border-violet-500/25",
        accent: "text-violet-300",
        accentBg: "bg-violet-500/15",
        dot: "bg-violet-400",
        badgeBg: "bg-violet-500/12 text-violet-300 border-violet-500/25",
      };
    case "bundled_package":
      return {
        bg: "bg-sky-500/8",
        border: "border-sky-500/25",
        accent: "text-sky-300",
        accentBg: "bg-sky-500/15",
        dot: "bg-sky-400",
        badgeBg: "bg-sky-500/12 text-sky-300 border-sky-500/25",
      };
    case "unclear_charge":
      return {
        bg: "bg-orange-500/8",
        border: "border-orange-500/25",
        accent: "text-orange-300",
        accentBg: "bg-orange-500/15",
        dot: "bg-orange-400",
        badgeBg: "bg-orange-500/12 text-orange-300 border-orange-500/25",
      };
    case "possible_duplicate":
      return {
        bg: "bg-red-500/8",
        border: "border-red-500/25",
        accent: "text-red-300",
        accentBg: "bg-red-500/15",
        dot: "bg-red-400",
        badgeBg: "bg-red-500/12 text-red-300 border-red-500/25",
      };
    case "requires_verification":
    default:
      return {
        bg: "bg-cyan-500/8",
        border: "border-cyan-500/25",
        accent: "text-cyan-300",
        accentBg: "bg-cyan-500/15",
        dot: "bg-cyan-400",
        badgeBg: "bg-cyan-500/12 text-cyan-300 border-cyan-500/25",
      };
  }
};

const FlaggedCostRow: React.FC<{
  flag: ExtraCostFlag;
  currency: string;
}> = ({ flag, currency }) => {
  const [expanded, setExpanded] = useState(false);
  const style = getFlagStyle(flag.flag_type);

  return (
    <div
      className={`rounded-xl border ${style.border} ${style.bg} overflow-hidden transition-all duration-200`}
    >
      {/* Collapsed Row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3.5 sm:p-4 flex items-center justify-between gap-3 cursor-pointer transition hover:bg-white/3 active:scale-[0.995] select-none"
        aria-expanded={expanded}
        aria-label={`${flag.what}: ${formatCurrency(flag.amount, currency)} — ${flag.flag_label}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`shrink-0 ${style.accent}`}>
            {getFlagIcon(flag.flag_type)}
          </span>
          <div className="min-w-0 text-left">
            <span className="text-xs sm:text-sm font-semibold text-slate-100 block truncate">
              {flag.what}
            </span>
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              <span
                className={`inline-block text-[10px] font-mono px-2 py-0.5 rounded border ${style.badgeBg}`}
              >
                {flag.flag_label}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <div className="text-right">
            <span className="text-sm sm:text-base font-mono font-bold text-white block">
              {formatCurrency(flag.amount, currency)}
            </span>
            {flag.potential_saving != null && flag.potential_saving > 0 && (
              <span className="text-[10px] text-amber-400 font-mono">
                Up to {formatCurrency(flag.potential_saving, currency)} removable
              </span>
            )}
          </div>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {/* Expanded Detail Panel */}
      {expanded && (
        <div className="px-3.5 pb-4 sm:px-4 space-y-3 border-t border-white/5">
          {/* WHY FLAGGED */}
          <div className="mt-3 bg-slate-950/70 rounded-lg p-3 border border-white/5">
            <span className="font-bold text-slate-400 uppercase tracking-wider text-[10px] block mb-1">
              Why flagged
            </span>
            <p className="text-xs text-slate-200 leading-relaxed">
              {flag.why_flagged}
            </p>
          </div>

          {/* WHAT TO VERIFY */}
          <div className="bg-amber-950/40 rounded-lg p-3 border border-amber-500/20">
            <span className="font-bold text-amber-300 uppercase tracking-wider text-[10px] block mb-1">
              What to verify
            </span>
            <p className="text-xs text-amber-200 leading-relaxed">
              {flag.what_to_verify}
            </p>
          </div>

          {/* POTENTIAL SAVING */}
          {flag.saving_language && (
            <div className="bg-emerald-950/30 rounded-lg p-3 border border-emerald-500/20">
              <span className="font-bold text-emerald-300 uppercase tracking-wider text-[10px] block mb-1">
                Potential amount that could be removed
              </span>
              <p className="text-xs text-emerald-200 leading-relaxed">
                {flag.saving_language}
              </p>
            </div>
          )}

          {/* BUNDLED PACKAGE QUESTIONS */}
          {flag.bundled_questions && flag.bundled_questions.length > 0 && (
            <div className="bg-sky-950/30 rounded-lg p-3 border border-sky-500/20">
              <span className="font-bold text-sky-300 uppercase tracking-wider text-[10px] block mb-1.5">
                Questions to ask the seller
              </span>
              <ul className="space-y-1.5">
                {flag.bundled_questions.map((q, i) => (
                  <li
                    key={i}
                    className="text-xs text-sky-200 flex items-start gap-2"
                  >
                    <span className="text-sky-400 mt-0.5 shrink-0">•</span>
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ExtraCostAnalysisCard: React.FC<ExtraCostAnalysisCardProps> = ({
  analysis,
  currency = "INR",
}) => {
  const cur = currency || "INR";
  const hasFlaggedCosts = analysis.flagged_costs.length > 0;

  if (!hasFlaggedCosts) {
    return (
      <div className="glass-panel rounded-2xl p-5 sm:p-7 border border-white/10 shadow-xl">
        <div className="flex items-center gap-2 mb-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <TrendingDown className="w-3.5 h-3.5" />
            EXTRA COST ANALYSIS
          </span>
        </div>
        <h3 className="text-base sm:text-lg font-bold text-white tracking-tight mb-1">
          No Extra Costs Flagged
        </h3>
        <p className="text-xs text-slate-400">
          All charges in this quotation appear to be standard components. No
          items were flagged for additional scrutiny.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-7 border border-white/10 shadow-xl space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <TrendingDown className="w-3.5 h-3.5" />
              POTENTIAL EXTRA COSTS
            </span>
            <span className="text-xs text-slate-400 font-mono hidden xs:inline">
              {analysis.total_flagged_count} of{" "}
              {analysis.total_charges_analyzed} charges flagged
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
            Extra Cost &amp; Cost-Reduction Analysis
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Charges that may deserve scrutiny — tap any row for details
          </p>
        </div>

        {/* Potential Reduction Pill */}
        {analysis.total_potential_reduction > 0 && (
          <div className="shrink-0">
            <div className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-950/40 to-emerald-950/30 border border-amber-500/25">
              <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider block">
                Maximum Potential Reduction
              </span>
              <span className="text-lg sm:text-xl font-mono font-extrabold text-white block mt-0.5">
                {formatCurrency(analysis.total_potential_reduction, cur)}
              </span>
              <span className="text-[10px] text-slate-400">
                if all flagged items are optional
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Flagged Cost Items */}
      <div className="space-y-2.5">
        {analysis.flagged_costs.map((flag) => (
          <FlaggedCostRow
            key={flag.component_id}
            flag={flag}
            currency={cur}
          />
        ))}
      </div>

      {/* Summary Footer */}
      <div className="p-3.5 sm:p-4 rounded-xl bg-slate-800/40 border border-white/10">
        <p className="text-xs text-slate-300 leading-relaxed">
          {analysis.reduction_summary}
        </p>
        <p className="text-[10px] text-slate-500 mt-2 italic">
          This analysis provides automated decision support. Verify each item
          individually with the seller before making decisions.
        </p>
      </div>
    </div>
  );
};
