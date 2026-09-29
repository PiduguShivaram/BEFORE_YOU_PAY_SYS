"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Search,
  Calculator,
  BookOpen,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ExternalLink,
} from "lucide-react";
import { EvidenceItem, FindingExplanation } from "../lib/types";

interface EvidencePanelProps {
  explanation: FindingExplanation;
}

const EvidenceTypeIcon: React.FC<{ type: string }> = ({ type }) => {
  switch (type) {
    case "DOCUMENT_TEXT":
      return <FileText className="w-3.5 h-3.5" />;
    case "OCR_TEXT":
      return <Search className="w-3.5 h-3.5" />;
    case "EXTRACTED_VALUE":
      return <Calculator className="w-3.5 h-3.5" />;
    case "SEMANTIC_CLASSIFICATION":
      return <BookOpen className="w-3.5 h-3.5" />;
    case "DETERMINISTIC_CALCULATION":
      return <Calculator className="w-3.5 h-3.5" />;
    case "SUPPORTING_DOCUMENT":
      return <FileText className="w-3.5 h-3.5" />;
    case "CROSS_DOCUMENT_COMPARISON":
      return <Search className="w-3.5 h-3.5" />;
    case "AUTHORITATIVE_KNOWLEDGE":
      return <BookOpen className="w-3.5 h-3.5" />;
    default:
      return <HelpCircle className="w-3.5 h-3.5" />;
  }
};

const ConfidenceBadge: React.FC<{ level: string }> = ({ level }) => {
  const getColor = () => {
    switch (level) {
      case "High":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "Medium":
        return "bg-amber-500/15 text-amber-400 border-amber-500/30";
      case "Low":
        return "bg-orange-500/15 text-orange-400 border-orange-500/30";
      case "Requires verification":
        return "bg-rose-500/15 text-rose-400 border-rose-500/30";
      default:
        return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    }
  };

  return (
    <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${getColor()}`}>
      {level}
    </span>
  );
};

const EvidenceItemCard: React.FC<{ item: EvidenceItem }> = ({ item }) => {
  return (
    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/60 text-xs">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5">
          <EvidenceTypeIcon type={item.evidence_type} />
          <span className="text-slate-400 font-medium">{item.evidence_type.replace(/_/g, " ")}</span>
        </div>
        <ConfidenceBadge level={item.confidence_level} />
      </div>

      {item.original_text && (
        <div className="mb-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            Original
          </span>
          <p className="text-slate-300 italic mt-0.5">&ldquo;{item.original_text}&rdquo;</p>
        </div>
      )}

      {item.interpreted_as && (
        <div className="mb-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            Interpreted as
          </span>
          <p className="text-slate-200 mt-0.5">{item.interpreted_as}</p>
        </div>
      )}

      {item.extracted_value !== null && item.extracted_value !== undefined && (
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Amount:</span>
          <span className="font-mono font-bold text-white">₹{item.extracted_value.toLocaleString("en-IN")}</span>
        </div>
      )}

      {item.semantic_category && (
        <div className="flex items-center gap-2 mt-1">
          <span className="text-slate-400">Category:</span>
          <span className="text-slate-300">{item.semantic_category}</span>
        </div>
      )}

      {item.page_number && (
        <div className="flex items-center gap-2 mt-1">
          <span className="text-slate-400">Page:</span>
          <span className="text-slate-300">{item.page_number}</span>
        </div>
      )}

      {item.uncertainty_reason && (
        <div className="mt-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
          <span className="text-amber-300 text-[10px]">{item.uncertainty_reason}</span>
        </div>
      )}

      {item.calculation_status && (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-slate-400">Status:</span>
          <span
            className={`font-mono font-bold ${
              item.calculation_status === "PASS"
                ? "text-emerald-400"
                : item.calculation_status === "FAIL"
                ? "text-rose-400"
                : "text-amber-400"
            }`}
          >
            {item.calculation_status}
          </span>
        </div>
      )}
    </div>
  );
};

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ explanation }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 overflow-hidden">
      {/* Header - Always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between gap-3 cursor-pointer transition hover:bg-white/5 active:scale-[0.999] select-none text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2 min-w-0">
          <HelpCircle className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="min-w-0">
            <span className="text-xs sm:text-sm font-semibold text-white block">
              Why was this flagged?
            </span>
            <span className="text-[11px] text-slate-400 block truncate">
              {explanation.why_flagged}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ConfidenceBadge level={explanation.confidence_level} />
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-800/60">
          {/* Concise explanation */}
          <div className="mt-3 p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
            <p className="text-xs text-cyan-200 leading-relaxed">{explanation.concise_explanation}</p>
          </div>

          {/* What we know */}
          {explanation.what_we_know.length > 0 && (
            <div>
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                What we know
              </h4>
              <ul className="space-y-1">
                {explanation.what_we_know.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* What we infer */}
          {explanation.what_we_infer.length > 0 && (
            <div>
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                What we infer
              </h4>
              <ul className="space-y-1">
                {explanation.what_we_infer.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                    <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* What remains uncertain */}
          {explanation.what_remains_uncertain.length > 0 && (
            <div>
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                What remains uncertain
              </h4>
              <ul className="space-y-1">
                {explanation.what_remains_uncertain.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                    <HelpCircle className="w-3 h-3 text-orange-400 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action */}
          {explanation.action && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <h4 className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">
                Action
              </h4>
              <p className="text-xs text-emerald-200">{explanation.action}</p>
            </div>
          )}

          {/* Calculation explanation */}
          {explanation.calculation_explanation && (
            <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                Calculation
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Expected:</span>
                  <span className="font-mono text-white">
                    {explanation.calculation_explanation.expected_result != null
                      ? `₹${explanation.calculation_explanation.expected_result.toLocaleString("en-IN")}`
                      : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Document:</span>
                  <span className="font-mono text-white">
                    {explanation.calculation_explanation.document_result != null
                      ? `₹${explanation.calculation_explanation.document_result.toLocaleString("en-IN")}`
                      : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Difference:</span>
                  <span
                    className={`font-mono font-bold ${
                      explanation.calculation_explanation.delta === 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }`}
                  >
                    {explanation.calculation_explanation.delta != null
                      ? `₹${explanation.calculation_explanation.delta.toLocaleString("en-IN")}`
                      : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span
                    className={`font-mono font-bold ${
                      explanation.calculation_explanation.status === "PASS"
                        ? "text-emerald-400"
                        : explanation.calculation_explanation.status === "FAIL"
                        ? "text-rose-400"
                        : "text-amber-400"
                    }`}
                  >
                    {explanation.calculation_explanation.status}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Supporting document explanation */}
          {explanation.supporting_document_explanation && (
            <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/60">
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                Supporting Document Comparison
              </h4>
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 block">Current document:</span>
                  <span className="text-slate-200">
                    {explanation.supporting_document_explanation.current_document_label}
                    {explanation.supporting_document_explanation.current_document_amount != null &&
                      ` — ₹${explanation.supporting_document_explanation.current_document_amount.toLocaleString("en-IN")}`}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Supporting document:</span>
                  <span className="text-slate-200">
                    {explanation.supporting_document_explanation.supporting_document_label}
                    {explanation.supporting_document_explanation.supporting_document_amount != null &&
                      ` — ₹${explanation.supporting_document_explanation.supporting_document_amount.toLocaleString("en-IN")}`}
                  </span>
                </div>
                <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20">
                  <span className="text-amber-300 text-[10px]">
                    {explanation.supporting_document_explanation.uncertainty}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Evidence */}
          {explanation.evidence.length > 0 && (
            <div>
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                Evidence
              </h4>
              <div className="space-y-2">
                {explanation.evidence.map((item) => (
                  <EvidenceItemCard key={item.evidence_id} item={item} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
