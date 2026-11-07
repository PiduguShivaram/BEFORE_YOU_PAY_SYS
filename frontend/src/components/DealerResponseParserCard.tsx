"use client";

import React, { useState } from "react";
import {
  DealerResponseAnalysisResult,
  ExtractedDealerAction,
} from "../lib/types";
import { parseDealerResponse } from "../lib/api";
import {
  MessageSquareQuote,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Copy,
  Check,
  ArrowRight,
  Calculator,
  Loader2,
  Send,
  XCircle,
  Tag,
  ShieldAlert,
} from "lucide-react";
import { Card3D } from "./Card3D";

interface DealerResponseParserCardProps {
  userId: string;
  defaultOriginalTotal?: number | null;
  currency?: string;
  onClose?: () => void;
  onParsed?: (res: DealerResponseAnalysisResult) => void;
  initialResult?: DealerResponseAnalysisResult | null;
}

export function DealerResponseParserCard({
  userId,
  defaultOriginalTotal,
  currency = "INR",
  onClose,
  onParsed,
  initialResult,
}: DealerResponseParserCardProps) {
  const [dealerText, setDealerText] = useState("");
  const [originalTotalInput, setOriginalTotalInput] = useState<string>(
    defaultOriginalTotal ? String(defaultOriginalTotal) : ""
  );
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DealerResponseAnalysisResult | null>(
    initialResult || null
  );
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const formatCurrency = (amount?: number | null) => {
    if (amount === undefined || amount === null) return "—";
    const sym = currency === "INR" ? "₹" : currency;
    return `${sym} ${amount.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const handleParse = async () => {
    if (!dealerText.trim()) {
      setError("Please paste the dealer's reply or counter-offer message.");
      return;
    }
    setError(null);
    setIsProcessing(true);

    try {
      const origTot = originalTotalInput ? parseFloat(originalTotalInput) : null;
      const parsed = await parseDealerResponse(
        dealerText,
        userId,
        origTot,
        currency
      );
      setResult(parsed);
      if (onParsed) onParsed(parsed);
    } catch (err: any) {
      setError(err.message || "Failed to analyze dealer response.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <Card3D intensity={5} glare={true} depth={15}>
      <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-2xl text-slate-100 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <MessageSquareQuote className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              Dealer Response & Counter-Offer Parser
            </h2>
            <p className="text-xs text-slate-400">
              Extract concessions, verify mathematical reconciliation, and identify discrepancies
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 transition"
          >
            Close
          </button>
        )}
      </div>

      {/* Input Form if no result */}
      {!result ? (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">
              Paste Dealer Email, WhatsApp, or Counter-Offer Text:
            </label>
            <textarea
              value={dealerText}
              onChange={(e) => setDealerText(e.target.value)}
              placeholder="e.g. 'We can waive the handling charges of Rs. 8,500 and reduce insurance to Rs. 35,000. Your revised on-road price is Rs. 11,31,500.'"
              rows={4}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 p-3.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500/50 resize-none font-sans"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Original Quotation Total Amount (Optional):
              </label>
              <input
                type="number"
                value={originalTotalInput}
                onChange={(e) => setOriginalTotalInput(e.target.value)}
                placeholder="e.g. 1150000"
                className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500/50 font-mono"
              />
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-red-950/40 border border-red-800/40 text-red-300 text-xs">
              <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end pt-1">
            <button
              onClick={handleParse}
              disabled={isProcessing || !dealerText.trim()}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold transition shadow-lg ${
                dealerText.trim() && !isProcessing
                  ? "bg-purple-600 hover:bg-purple-500 text-white shadow-purple-500/20"
                  : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-800"
              }`}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-purple-300" />
                  <span>Extracting Negotiation Terms...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Parse & Reconcile Response</span>
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* Results View */
        <div className="space-y-6">
          {/* Top Banner & Reconciliation Badge */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-400">Reconciliation Assessment</div>
              <div className="flex items-center gap-2">
                {result.math_reconciliation_status === "RECONCILED" ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4" />
                    Mathematically Reconciled
                  </span>
                ) : result.math_reconciliation_status === "DISCREPANCY" ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                    <AlertTriangle className="w-4 h-4" />
                    Discrepancy Detected ({formatCurrency(result.reconciliation_difference)})
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                    Concessions Extracted
                  </span>
                )}
              </div>
            </div>

            <button
              onClick={() => setResult(null)}
              className="text-xs text-purple-400 hover:text-purple-300 font-semibold px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-950/20 transition self-start sm:self-center"
            >
              Analyze Another Message
            </button>
          </div>

          {/* Financial Totals Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {result.original_total && (
              <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
                <div className="text-xs text-slate-400 font-medium">Original Quoted Total</div>
                <div className="text-lg font-bold text-slate-300 mt-0.5 font-mono">
                  {formatCurrency(result.original_total)}
                </div>
              </div>
            )}

            <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
              <div className="text-xs text-slate-400 font-medium">Total Agreed Reductions</div>
              <div className="text-lg font-bold text-emerald-400 mt-0.5 font-mono">
                {result.total_reduction ? `-${formatCurrency(result.total_reduction)}` : "—"}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-800/40">
              <div className="text-xs text-purple-300 font-medium">Calculated Revised Total</div>
              <div className="text-lg font-bold text-purple-300 mt-0.5 font-mono">
                {formatCurrency(result.calculated_new_total || result.stated_counter_total)}
              </div>
            </div>
          </div>

          {/* Extracted Dealer Concessions List */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Tag className="w-4 h-4 text-purple-400" />
              Extracted Action Items & Concessions ({result.extracted_actions.length})
            </h3>
            <div className="space-y-2">
              {result.extracted_actions.map((action) => (
                <div
                  key={action.action_id}
                  className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">
                      {action.target_component_name}
                    </span>
                    {action.reduction_amount ? (
                      <span className="text-emerald-400 font-mono font-semibold">
                        -{formatCurrency(action.reduction_amount)}
                      </span>
                    ) : action.revised_amount ? (
                      <span className="text-purple-300 font-mono font-semibold">
                        Revised: {formatCurrency(action.revised_amount)}
                      </span>
                    ) : (
                      <span className="text-slate-400 italic">Non-negotiable</span>
                    )}
                  </div>
                  <div className="text-slate-400 text-[11px] bg-slate-900/60 px-2.5 py-1 rounded border border-slate-800/80 font-mono">
                    &ldquo;{action.raw_text_snippet}&rdquo;
                  </div>
                  {action.notes && (
                    <div className="text-slate-300 text-[11px]">{action.notes}</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Follow-up Recommendations & Verification Checklist */}
          {result.follow_up_recommendations.length > 0 && (
            <div className="space-y-2.5">
              <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <HelpCircle className="w-4 h-4 text-purple-400" />
                Recommended Verification Steps Before Payment
              </h3>
              <div className="space-y-2">
                {result.follow_up_recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-3 p-3 rounded-xl bg-purple-950/20 border border-purple-800/30 text-xs"
                  >
                    <div className="text-slate-200 leading-relaxed flex-1">
                      <span className="font-semibold text-purple-300 mr-1.5">Step {idx + 1}:</span>
                      {rec}
                    </div>
                    <button
                      onClick={() => handleCopy(rec, idx)}
                      className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex-shrink-0"
                    >
                      {copiedIndex === idx ? (
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
            {result.disclaimer}
          </div>
        </div>
      )}
      </div>
    </Card3D>
  );
}
