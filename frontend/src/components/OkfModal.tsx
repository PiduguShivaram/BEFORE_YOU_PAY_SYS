"use client";

import React from "react";
import { X, BookOpen, ShieldAlert } from "lucide-react";
import { OkfRule } from "../lib/types";

interface OkfModalProps {
  isOpen: boolean;
  onClose: () => void;
  rules: OkfRule[];
}

export const OkfModal: React.FC<OkfModalProps> = ({ isOpen, onClose, rules }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
      <div className="glass-panel rounded-2xl max-w-lg w-full max-h-[85vh] flex flex-col shadow-2xl border border-white/10">
        <div className="flex items-center justify-between p-5 border-b border-white/10">
          <div className="flex items-center gap-2.5 text-sky-400">
            <BookOpen className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">Curated Verification Rules (OKF)</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4">
          <p className="text-xs text-slate-400 leading-relaxed">
            The Open Knowledge Format (OKF) knowledge catalog contains versioned, curated standards
            and statutory guidelines. User documents are never stored here.
          </p>

          <div className="space-y-3">
            {rules.map((rule) => (
              <div
                key={rule.rule_id}
                className="p-4 rounded-xl bg-slate-900/60 border border-white/5 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-brand-400">
                    {rule.rule_id}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                    {rule.category}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">{rule.rule_name}</h4>
                <p className="text-xs text-slate-300 leading-relaxed">{rule.guidance}</p>
                <div className="pt-2 border-t border-white/5 text-[11px] text-slate-500">
                  Authority: <span className="text-slate-400">{rule.source_reference}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
