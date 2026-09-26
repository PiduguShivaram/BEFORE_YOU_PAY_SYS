"use client";

import React from "react";
import { Loader2, Check, Cpu } from "lucide-react";
import { StreamEvent } from "../lib/api";

interface PipelineProgressProps {
  isProcessing: boolean;
  currentEvent?: StreamEvent | null;
}

const STAGES = [
  { key: "precondition", id: 1, label: "Precondition", detail: "File integrity & bounds" },
  { key: "spatial_ocr", id: 2, label: "Spatial OCR", detail: "Geometry & lines" },
  { key: "structured_extraction", id: 3, label: "AI Extraction", detail: "Groq Failover Pool" },
  { key: "knowledge_retrieval", id: 4, label: "RAG & Rules", detail: "SQLite & OKF rules" },
  { key: "arithmetic_gate", id: 5, label: "Math Gate", detail: "Pure Python verification" },
  { key: "semantic_reasoning", id: 6, label: "Reasoning", detail: "Grounded claim analysis" },
  { key: "complete", id: 7, label: "Final Verdict", detail: "Audit synthesis ready" },
];

export const PipelineProgress: React.FC<PipelineProgressProps> = ({ isProcessing, currentEvent }) => {
  if (!isProcessing && !currentEvent) return null;

  // Determine active stage number from event stage key
  const getStageId = (stageKey?: string): number => {
    switch (stageKey) {
      case "precondition":
        return 1;
      case "spatial_ocr":
        return 2;
      case "structured_extraction":
        return 3;
      case "knowledge_retrieval":
        return 4;
      case "arithmetic_gate":
        return 5;
      case "semantic_reasoning":
        return 6;
      case "final_verdict":
      case "complete":
        return 7;
      default:
        return 1;
    }
  };

  const isError = currentEvent?.stage === "error";
  const activeStageId = getStageId(currentEvent?.stage);
  const progressPercent = isError ? 100 : (currentEvent?.progress || 10);
  const statusMessage = isError 
    ? ((currentEvent as any)?.error || currentEvent?.message || "Analysis rejected") 
    : (currentEvent?.message || "Initializing 7-stage verification pipeline...");
  const providerUsed = currentEvent?.data?.provider;

  return (
    <div className="glass-panel rounded-2xl p-6 mb-8 border border-brand-500/40 shadow-glow transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          {isError ? <span className="w-5 h-5 text-rose-400 font-bold">✕</span> : <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />}
          <div>
            <span className="text-sm font-bold text-white tracking-wide block">
              7-Stage Orchestration & Verification Pipeline
            </span>
            <span className="text-xs text-brand-300 font-mono">
              {statusMessage}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {providerUsed && (
            <span className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
              <Cpu className="w-3 h-3 text-emerald-400" />
              {providerUsed}
            </span>
          )}
          <span className="text-xs font-mono font-bold text-slate-300 bg-white/10 px-2 py-0.5 rounded-md">
            {progressPercent}%
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-white/5 rounded-full h-1.5 mb-5 overflow-hidden">
        <div
          className="bg-gradient-to-r from-brand-500 via-emerald-400 to-teal-300 h-1.5 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {STAGES.map((st) => {
          const isDone = activeStageId > st.id || (activeStageId === 7 && currentEvent?.stage === "complete");
          const isCurrent = activeStageId === st.id && currentEvent?.stage !== "complete";

          return (
            <div
              key={st.id}
              className={`rounded-xl p-2.5 text-center transition border ${
                isDone
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : isCurrent
                  ? "bg-brand-500/20 border-brand-500 text-white shadow-glow"
                  : "bg-white/5 border-white/5 text-slate-500"
              }`}
            >
              <div className="flex items-center justify-center gap-1.5 mb-1">
                {isDone ? (
                  <Check className="w-3 h-3 text-emerald-400" />
                ) : (
                  <span className="text-[10px] font-mono font-bold w-4 h-4 rounded-full bg-white/10 flex items-center justify-center">
                    {st.id}
                  </span>
                )}
                <span className="text-xs font-bold leading-none">{st.label}</span>
              </div>
              <span className="text-[10px] text-slate-400 block truncate">{st.detail}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
