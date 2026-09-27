"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  FileText,
  HelpCircle,
  MessageSquare,
  Sparkles,
  Tag,
} from "lucide-react";
import { PlainLanguageExplanation } from "../lib/types";

interface PlainLanguageExplanationCardProps {
  explanation: PlainLanguageExplanation;
}

export const PlainLanguageExplanationCard: React.FC<PlainLanguageExplanationCardProps> = ({
  explanation,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(explanation.full_explanation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 sm:p-7 border border-white/10 shadow-xl space-y-5 bg-gradient-to-br from-slate-900/90 via-slate-900/80 to-slate-950/90">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
              <FileText className="w-3.5 h-3.5" />
              PLAIN-LANGUAGE EXPLANATION
            </span>
            <span className="text-xs text-slate-400 font-mono hidden xs:inline">
              Evidence-Derived
            </span>
          </div>
          <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Financial Summary &amp; Breakdown
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Clear, plain-language translation of all stated quotation obligations
          </p>
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="self-start sm:self-center inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-colors"
          title="Copy explanation text"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy Summary</span>
            </>
          )}
        </button>
      </div>

      {/* Main Narrative Statements */}
      <div className="space-y-2.5">
        {/* Quoted Total Main Callout */}
        <div className="p-3.5 sm:p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/25 flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-indigo-400 shrink-0" />
          <p className="text-sm sm:text-base font-semibold text-indigo-100">
            {explanation.quoted_amount_sentence}
          </p>
        </div>

        {/* Base Price */}
        <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5 flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
          <p className="text-xs sm:text-sm text-slate-200">
            {explanation.base_price_sentence}
          </p>
        </div>

        {/* Charges Breakdown */}
        {explanation.charge_breakdown_sentences.map((sentence, idx) => (
          <div
            key={idx}
            className="p-3 rounded-lg bg-slate-900/60 border border-white/5 flex items-center gap-2.5"
          >
            <span className="w-2 h-2 rounded-full bg-sky-400 shrink-0" />
            <p className="text-xs sm:text-sm text-slate-200">
              {sentence}
            </p>
          </div>
        ))}

        {/* Offers / Deductions */}
        {explanation.offers_sentence && (
          <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/25 flex items-center gap-2.5">
            <Tag className="w-4 h-4 text-emerald-400 shrink-0" />
            <p className="text-xs sm:text-sm text-emerald-200 font-medium">
              {explanation.offers_sentence}
            </p>
          </div>
        )}

        {/* Discrepancy Alert */}
        {explanation.discrepancy_sentence && (
          <div className="p-3.5 rounded-lg bg-amber-950/30 border border-amber-500/30 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs sm:text-sm text-amber-200 font-medium leading-relaxed">
              {explanation.discrepancy_sentence}
            </p>
          </div>
        )}
      </div>

      {/* Clarification Section */}
      {explanation.clarification_items && explanation.clarification_items.length > 0 && (
        <div className="pt-4 border-t border-white/10 space-y-3">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-cyan-400 shrink-0" />
            <h4 className="text-xs sm:text-sm font-bold text-white uppercase tracking-wider">
              {explanation.clarification_heading}
            </h4>
          </div>

          <ul className="space-y-2">
            {explanation.clarification_items.map((item, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2.5 p-2.5 sm:p-3 rounded-lg bg-slate-800/40 border border-white/5 text-xs sm:text-sm text-slate-200"
              >
                <span className="text-cyan-400 font-bold shrink-0 mt-0.5">•</span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
