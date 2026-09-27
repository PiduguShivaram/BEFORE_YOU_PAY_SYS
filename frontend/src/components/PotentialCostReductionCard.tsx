"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Info,
  Layers,
  Sparkles,
  Tag,
} from "lucide-react";
import { PotentialCostReductionSummary, ReductionTierItem } from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface PotentialCostReductionCardProps {
  summary: PotentialCostReductionSummary;
  currency?: string | null;
}

const TierItemRow: React.FC<{
  item: ReductionTierItem;
  currency: string;
  dotColor: string;
  badgeBg: string;
}> = ({ item, currency, dotColor, badgeBg }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-white/5 bg-slate-900/60 overflow-hidden transition-all duration-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3 sm:p-3.5 flex items-center justify-between gap-3 cursor-pointer transition hover:bg-white/5 active:scale-[0.995] select-none text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
          <div className="min-w-0">
            <span className="text-xs sm:text-sm font-semibold text-slate-100 block truncate">
              {item.name}
            </span>
            <span className={`inline-block text-[10px] font-mono px-2 py-0.5 rounded border mt-0.5 ${badgeBg}`}>
              {item.status_label}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <span className="text-sm font-mono font-bold text-white">
            {formatCurrency(item.amount, currency)}
          </span>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-white/5 bg-slate-950/40 space-y-2 text-xs">
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Document Evidence
            </span>
            <p className="text-slate-300 mt-0.5 italic">
              {item.evidence}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export const PotentialCostReductionCard: React.FC<PotentialCostReductionCardProps> = ({
  summary,
  currency = "INR",
}) => {
  const cur = currency || "INR";
  const hasItems =
    summary.confirmed_optional_items.length > 0 ||
    summary.potentially_optional_items.length > 0 ||
    summary.unclear_confirmation_items.length > 0;

  if (!hasItems) {
    return null;
  }

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-7 border border-white/10 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
              <Layers className="w-3.5 h-3.5" />
              POTENTIAL COST REDUCTION
            </span>
            <span className="text-xs text-slate-400 font-mono hidden xs:inline">
              Phase 7 Summary
            </span>
          </div>
          <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Potential Cost Reduction
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Items identified as optional or requiring seller clarification. This analysis does not promise savings.
          </p>
        </div>

        {/* Range Pill */}
        <div className="shrink-0 p-3 sm:p-4 rounded-xl bg-gradient-to-br from-cyan-950/60 via-slate-900 to-indigo-950/60 border border-cyan-500/30 shadow-inner">
          <span className="text-[10px] font-bold text-cyan-300 uppercase tracking-wider block">
            Potential amount worth reviewing
          </span>
          <span className="text-xl sm:text-2xl font-mono font-extrabold text-white block mt-1 tracking-tight">
            {summary.potential_range_display}
          </span>
          <span className="text-[10px] text-slate-400 block mt-0.5">
            Subject to seller confirmation
          </span>
        </div>
      </div>

      {/* Mandatory Review Notice - Exact phrasing */}
      <div className="flex items-start gap-3 p-3.5 sm:p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
        <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs sm:text-sm text-amber-200 leading-relaxed font-medium">
          {summary.review_message}
        </p>
      </div>

      {/* Three Tiers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tier 1: Confirmed Optional */}
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-950/15 p-4 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                CONFIRMED OPTIONAL
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                {summary.confirmed_optional_items.length} item{summary.confirmed_optional_items.length === 1 ? "" : "s"}
              </span>
            </div>
            <span className="text-[11px] text-slate-400 block">
              Potential removable amount:
            </span>
            <span className="text-xl font-mono font-bold text-white block mt-0.5">
              {formatCurrency(summary.confirmed_optional_amount, cur)}
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t border-emerald-500/20">
            {summary.confirmed_optional_items.length > 0 ? (
              summary.confirmed_optional_items.map((item) => (
                <TierItemRow
                  key={item.component_id}
                  item={item}
                  currency={cur}
                  dotColor="bg-emerald-400"
                  badgeBg="bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                />
              ))
            ) : (
              <span className="text-xs text-slate-500 italic block py-1">
                No explicitly optional charges identified.
              </span>
            )}
          </div>
        </div>

        {/* Tier 2: Potentially Optional */}
        <div className="rounded-xl border border-amber-500/25 bg-amber-950/15 p-4 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-amber-400">
                <Tag className="w-4 h-4" />
                POTENTIALLY OPTIONAL
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {summary.potentially_optional_items.length} item{summary.potentially_optional_items.length === 1 ? "" : "s"}
              </span>
            </div>
            <span className="text-[11px] text-slate-400 block">
              Potential amount:
            </span>
            <span className="text-xl font-mono font-bold text-white block mt-0.5">
              {formatCurrency(summary.potentially_optional_amount, cur)}
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t border-amber-500/20">
            {summary.potentially_optional_items.length > 0 ? (
              summary.potentially_optional_items.map((item) => (
                <TierItemRow
                  key={item.component_id}
                  item={item}
                  currency={cur}
                  dotColor="bg-amber-400"
                  badgeBg="bg-amber-500/15 text-amber-300 border-amber-500/30"
                />
              ))
            ) : (
              <span className="text-xs text-slate-500 italic block py-1">
                No potentially optional charges identified.
              </span>
            )}
          </div>
        </div>

        {/* Tier 3: Unclear / Needs Confirmation */}
        <div className="rounded-xl border border-sky-500/25 bg-sky-950/15 p-4 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-sky-400">
                <HelpCircle className="w-4 h-4" />
                UNCLEAR / NEEDS CONFIRMATION
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
                {summary.unclear_confirmation_items.length} item{summary.unclear_confirmation_items.length === 1 ? "" : "s"}
              </span>
            </div>
            <span className="text-[11px] text-slate-400 block">
              Amount requiring clarification:
            </span>
            <span className="text-xl font-mono font-bold text-white block mt-0.5">
              {formatCurrency(summary.unclear_confirmation_amount, cur)}
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t border-sky-500/20">
            {summary.unclear_confirmation_items.length > 0 ? (
              summary.unclear_confirmation_items.map((item) => (
                <TierItemRow
                  key={item.component_id}
                  item={item}
                  currency={cur}
                  dotColor="bg-sky-400"
                  badgeBg="bg-sky-500/15 text-sky-300 border-sky-500/30"
                />
              ))
            ) : (
              <span className="text-xs text-slate-500 italic block py-1">
                No unclear charges requiring clarification.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
