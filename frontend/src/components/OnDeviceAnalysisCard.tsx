"use client";

import React from "react";
import { Cpu, CheckCircle2, AlertTriangle, HelpCircle, HardDrive, ArrowRight, ShieldCheck } from "lucide-react";
import { OfflineAnalysisResult } from "../lib/offlineAnalysisEngine";

interface OnDeviceAnalysisCardProps {
  result: OfflineAnalysisResult;
  onQueueForCloud?: () => void;
}

export const OnDeviceAnalysisCard: React.FC<OnDeviceAnalysisCardProps> = ({
  result,
  onQueueForCloud,
}) => {
  const isReconciled = result.math_status === "RECONCILED";
  const hasDiscrepancy = result.math_status === "DISCREPANCY";
  const currSym = result.currency === "USD" ? "$" : "₹";

  return (
    <div className="glass-panel rounded-2xl p-6 mb-8 border border-emerald-500/40 shadow-glow bg-gradient-to-b from-slate-900/90 to-slate-950/90 transition-all">
      {/* Header with On-Device Chip */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Cpu className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Analysis completed on-device
              </span>
              <span className="text-[11px] text-slate-400 font-mono">
                Pure Local WebWorker
              </span>
            </div>
            <h3 className="text-lg font-bold text-white tracking-tight mt-1">
              On-Device Financial Verification
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <HardDrive className="w-4 h-4 text-slate-500" />
          <span>Zero Server Network Activity</span>
        </div>
      </div>

      {/* 5 Distinct Status Indicators Ledger */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 my-4 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[11px] font-mono">
        <div className="p-2 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          Analysis completed on-device
        </div>
        <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-600"></span>
          Document captured locally
        </div>
        <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-600"></span>
          Upload queued
        </div>
        <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-600"></span>
          Cloud analysis pending
        </div>
        <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-600"></span>
          Analysis unavailable
        </div>
      </div>

      {/* Summary Banner */}
      <div className={`p-4 rounded-xl border mb-5 flex items-start gap-3 ${
        isReconciled 
          ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-200"
          : hasDiscrepancy
            ? "bg-rose-950/20 border-rose-500/30 text-rose-200"
            : "bg-amber-950/20 border-amber-500/30 text-amber-200"
      }`}>
        {isReconciled ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        ) : hasDiscrepancy ? (
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
        ) : (
          <HelpCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        )}
        <div>
          <span className="font-bold text-sm block">
            {isReconciled ? "Deterministic Math Reconciled" : hasDiscrepancy ? "Arithmetic Discrepancy Found" : "Component Reconciliation Inconclusive"}
          </span>
          <p className="text-xs mt-0.5 leading-relaxed opacity-90">
            {result.summary}
          </p>
        </div>
      </div>

      {/* Extracted Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Stated Total</span>
          <span className="text-lg font-mono font-bold text-white block mt-1">
            {result.detected_total ? `${currSym}${result.detected_total.toLocaleString()}` : "Not detected"}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Base / Subtotal</span>
          <span className="text-lg font-mono font-bold text-white block mt-1">
            {result.detected_subtotal ? `${currSym}${result.detected_subtotal.toLocaleString()}` : "—"}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Stated Tax</span>
          <span className="text-lg font-mono font-bold text-white block mt-1">
            {result.detected_tax ? `${currSym}${result.detected_tax.toLocaleString()}` : "—"}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Discount</span>
          <span className="text-lg font-mono font-bold text-emerald-400 block mt-1">
            {result.detected_discount ? `-${currSym}${result.detected_discount.toLocaleString()}` : "—"}
          </span>
        </div>
      </div>

      {/* Itemized Detected Lines */}
      {result.components.length > 0 && (
        <div className="mb-5">
          <span className="text-xs font-mono font-bold text-slate-300 block mb-2">
            Itemized Lines Extracted On-Device ({result.components.length})
          </span>
          <div className="space-y-1.5">
            {result.components.map((c, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60 text-xs">
                <span className="text-slate-300 font-medium truncate max-w-[240px]">{c.name}</span>
                <span className="font-mono text-white">{currSym}{c.amount.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-800">
        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Calculations run on your CPU with zero cloud transmission</span>
        </div>

        {onQueueForCloud && (
          <button
            onClick={onQueueForCloud}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-brand-500 to-indigo-600 hover:from-brand-400 hover:to-indigo-500 text-white font-semibold text-xs transition-all flex items-center gap-2 shadow-lg"
          >
            <span>Queue for Full Cloud Deep Audit</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
};

