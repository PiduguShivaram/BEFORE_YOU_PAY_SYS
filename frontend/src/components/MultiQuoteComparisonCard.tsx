"use client";

import React, { useState } from "react";
import {
  MultiQuoteComparisonResult,
  AlignedFinancialComponent,
  InclusionExclusionFinding,
  QuoteSummary,
} from "../lib/types";
import {
  Scale,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Copy,
  Check,
  Building2,
  FileSpreadsheet,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Card3D } from "./Card3D";

interface MultiQuoteComparisonCardProps {
  comparison: MultiQuoteComparisonResult;
  onClose?: () => void;
}

export function MultiQuoteComparisonCard({
  comparison,
  onClose,
}: MultiQuoteComparisonCardProps) {
  const [copiedQuestionIndex, setCopiedQuestionIndex] = useState<number | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

  const formatCurrency = (amount?: number | null) => {
    if (amount === undefined || amount === null) return "—";
    const sym = comparison.primary_currency === "INR" ? "₹" : comparison.primary_currency;
    return `${sym} ${amount.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const handleCopyQuestion = (question: string, index: number) => {
    navigator.clipboard.writeText(question);
    setCopiedQuestionIndex(index);
    setTimeout(() => setCopiedQuestionIndex(null), 2000);
  };

  const toggleCategory = (catId: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [catId]: !prev[catId],
    }));
  };

  return (
    <Card3D intensity={5} glare={true} depth={15}>
      <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-2xl text-slate-100 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              Multi-Quotation Comparison Matrix
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-medium">
                {comparison.quotes.length} Quotes
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Side-by-side component alignment and deterministic price variance
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 transition"
          >
            Close Matrix
          </button>
        )}
      </div>

      {/* Summary Delta Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <div className="text-xs text-slate-400 font-medium">Lowest Total Quote</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">
            {formatCurrency(comparison.min_total)}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <div className="text-xs text-slate-400 font-medium">Highest Total Quote</div>
          <div className="text-lg font-bold text-amber-400 mt-0.5">
            {formatCurrency(comparison.max_total)}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-800/40">
          <div className="text-xs text-blue-300 font-medium">Total Variance (Delta)</div>
          <div className="text-lg font-bold text-blue-400 mt-0.5">
            {formatCurrency(comparison.total_delta)}
          </div>
        </div>
      </div>

      {/* Currency mismatch alert if applicable */}
      {comparison.currency_mismatch && (
        <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-300 text-xs">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            Multiple currencies detected across uploaded quotations. Numeric deltas are computed
            using primary currency ({comparison.primary_currency}). Verify local exchange rates.
          </span>
        </div>
      )}

      {/* Side-by-side Matrix Table */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-300 px-1">
          <span className="flex items-center gap-1.5">
            <FileSpreadsheet className="w-4 h-4 text-blue-400" />
            Itemized Component Breakdown
          </span>
          <span className="text-slate-500 font-normal">
            Scroll horizontally for full comparison
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80">
                <th className="p-3 font-semibold text-slate-300 min-w-[200px]">
                  Financial Component
                </th>
                {comparison.quotes.map((q, idx) => (
                  <th key={q.document_id} className="p-3 font-semibold text-slate-300 min-w-[160px]">
                    <div className="flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-slate-400" />
                      <span className="truncate">{q.vendor_name || `Quote #${idx + 1}`}</span>
                    </div>
                    {q.total_amount && (
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        Total: {formatCurrency(q.total_amount)}
                      </div>
                    )}
                  </th>
                ))}
                <th className="p-3 font-semibold text-slate-300 min-w-[120px] text-right">
                  Price Delta
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {comparison.aligned_components.map((comp) => {
                const hasVariance = comp.presence_variance || (comp.delta_amount && comp.delta_amount > 0);
                return (
                  <tr
                    key={comp.alignment_id}
                    className={`hover:bg-slate-850/50 transition-colors ${
                      hasVariance ? "bg-slate-900/30" : ""
                    }`}
                  >
                    <td className="p-3">
                      <div className="font-medium text-slate-200">{comp.display_name}</div>
                      {comp.presence_variance && (
                        <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                          Excluded in some quotes
                        </span>
                      )}
                    </td>

                    {comparison.quotes.map((q) => {
                      const cell = comp.cells[q.document_id];
                      const isPresent = cell && cell.is_present;
                      return (
                        <td key={q.document_id} className="p-3 font-mono">
                          {isPresent ? (
                            <div className="text-slate-200 font-semibold">
                              {cell.amount !== null && cell.amount !== undefined
                                ? formatCurrency(cell.amount)
                                : "Included (Unpriced)"}
                              {cell.raw_label && (
                                <div className="text-[10px] font-sans text-slate-400 font-normal truncate max-w-[150px]">
                                  {cell.raw_label}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-500 text-xs italic">Not listed</span>
                          )}
                        </td>
                      );
                    })}

                    <td className="p-3 text-right font-mono font-semibold">
                      {comp.delta_amount && comp.delta_amount > 0 ? (
                        <span className="text-blue-300">
                          +{formatCurrency(comp.delta_amount)}
                        </span>
                      ) : (
                        <span className="text-slate-500 font-normal">Aligned</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Inclusions & Exclusions */}
      {comparison.inclusions_and_exclusions.length > 0 && (
        <div className="space-y-2 pt-2">
          <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Detected Inclusion & Exclusion Variances
          </h3>
          <div className="grid grid-cols-1 gap-2.5">
            {comparison.inclusions_and_exclusions.map((finding) => (
              <div
                key={finding.finding_id}
                className="p-3 rounded-xl bg-slate-950/40 border border-slate-800 text-xs space-y-1.5"
              >
                <div className="font-semibold text-slate-200 flex items-center justify-between">
                  <span>{finding.component_name}</span>
                  {finding.potential_cost_difference && (
                    <span className="text-amber-400 font-mono">
                      Delta: {formatCurrency(finding.potential_cost_difference)}
                    </span>
                  )}
                </div>
                <p className="text-slate-400 leading-relaxed">{finding.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggested Negotiation Questions */}
      {comparison.suggested_negotiation_questions.length > 0 && (
        <div className="space-y-2 pt-2">
          <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <HelpCircle className="w-4 h-4 text-blue-400" />
            Recommended Vendor Negotiation Questions
          </h3>
          <div className="space-y-2">
            {comparison.suggested_negotiation_questions.map((q, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between gap-3 p-3 rounded-xl bg-blue-950/20 border border-blue-800/30 text-xs"
              >
                <div className="text-slate-200 leading-relaxed flex-1">
                  <span className="font-semibold text-blue-300 mr-1.5">Q{idx + 1}:</span>
                  {q}
                </div>
                <button
                  onClick={() => handleCopyQuestion(q, idx)}
                  className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex-shrink-0"
                >
                  {copiedQuestionIndex === idx ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-400" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Standard Non-Committal Disclaimer */}
      <div className="text-[11px] text-slate-400 border-t border-slate-800 pt-3 leading-relaxed">
        {comparison.disclaimer}
      </div>
      </div>
    </Card3D>
  );
}
