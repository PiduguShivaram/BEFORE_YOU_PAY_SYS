"use client";

import React from "react";
import { AlertCircle, AlertTriangle, Info, Flag, ExternalLink } from "lucide-react";
import { DecisionFlag } from "../lib/types";

interface DecisionFlagsProps {
  flags: DecisionFlag[];
  selectedFlagId: string | null;
  onSelectFlag: (flag: DecisionFlag) => void;
}

export const DecisionFlags: React.FC<DecisionFlagsProps> = ({
  flags,
  selectedFlagId,
  onSelectFlag,
}) => {
  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-6 shadow-card mb-6 border border-white/10">
      <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Flag className="w-5 h-5 text-brand-400" />
          <h3 className="font-bold text-sm sm:text-base text-white">Verification Findings</h3>
        </div>
        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-white/10 text-slate-300">
          {flags.length} finding{flags.length === 1 ? "" : "s"}
        </span>
      </div>

      {flags.length === 0 ? (
        <div className="text-center py-6 text-xs text-slate-400 bg-white/2 rounded-xl border border-white/5">
          No discrepancy flags or unverified clauses detected.
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {flags.map((flag) => {
            const isSelected = selectedFlagId === flag.flag_id;
            const isCritical = flag.severity === "CRITICAL";
            const isWarning = flag.severity === "WARNING";

            return (
              <div
                key={flag.flag_id}
                onClick={() => onSelectFlag(flag)}
                className={`min-h-[52px] p-3.5 sm:p-4 rounded-xl border transition cursor-pointer active:scale-[0.99] select-none ${
                  isSelected
                    ? "border-brand-500 bg-brand-500/15 shadow-glow"
                    : "border-white/10 bg-slate-900/40 hover:border-white/20 hover:bg-slate-800/40"
                } ${
                  isCritical
                    ? "border-l-4 border-l-rose-500"
                    : isWarning
                    ? "border-l-4 border-l-amber-500"
                    : "border-l-4 border-l-sky-500"
                }`}
                role="button"
                tabIndex={0}
                aria-label={`Finding: ${flag.label}`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2 min-w-0">
                    {isCritical ? (
                      <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    ) : isWarning ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    ) : (
                      <Info className="w-4 h-4 text-sky-400 shrink-0" />
                    )}
                    <span className="font-bold text-xs sm:text-sm text-white truncate">
                      {flag.label}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] font-extrabold px-1.5 py-0.2 rounded uppercase tracking-wider shrink-0 ${
                      isCritical
                        ? "bg-rose-500/15 text-rose-300"
                        : isWarning
                        ? "bg-amber-500/15 text-amber-300"
                        : "bg-sky-500/15 text-sky-300"
                    }`}
                  >
                    {flag.severity}
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed pl-6">
                  {flag.message}
                </p>

                <div className="mt-2 pl-6 flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-white/5">
                  <span className="font-mono text-[10px] text-slate-500">
                    {flag.claim_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-brand-400 hover:underline flex items-center gap-1 font-medium">
                    <span>{isSelected ? "Inspecting on slip" : "Inspect on slip"}</span>
                    <ExternalLink className="w-2.5 h-2.5" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
