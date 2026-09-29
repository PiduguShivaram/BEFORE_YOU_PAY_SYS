"use client";

import React, { useState } from "react";
import { HelpCircle, ChevronDown, ChevronUp, CheckCircle, AlertTriangle, Eye, SunMedium } from "lucide-react";

export const CaptureGuidance: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/60 p-3 sm:p-4 text-xs text-slate-300">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full min-h-[44px] flex items-center justify-between gap-2 text-left font-semibold text-slate-200 hover:text-white transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 rounded-lg px-1"
        aria-expanded={isOpen}
        aria-controls="capture-guidance-content"
      >
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-brand-400 shrink-0" />
          <span className="text-xs sm:text-sm">Document Capture Quality Tips</span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
          <span>{isOpen ? "Hide tips" : "Show tips"}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isOpen && (
        <div id="capture-guidance-content" className="mt-3 pt-3 border-t border-white/10 space-y-2.5 animate-in fade-in duration-150">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Spatial OCR inspects physical coordinates and line text. Follow these guidelines for accurate extraction:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <div className="flex items-start gap-2 bg-white/5 p-2 rounded-lg border border-white/5">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block">Full Document in Frame</strong>
                <span className="text-slate-400">Keep all 4 corners, headers, and totals visible without clipping.</span>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-white/5 p-2 rounded-lg border border-white/5">
              <SunMedium className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block">Even Lighting & No Glare</strong>
                <span className="text-slate-400">Avoid strong overhead flash or reflection directly on amount columns.</span>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-white/5 p-2 rounded-lg border border-white/5">
              <Eye className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block">Sharp Focus & Minimal Blur</strong>
                <span className="text-slate-400">Ensure item numbers and punctuation (commas, decimals) are legible.</span>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-white/5 p-2 rounded-lg border border-white/5">
              <AlertTriangle className="w-3.5 h-3.5 text-brand-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block">Parallel Flat Angle</strong>
                <span className="text-slate-400">Hold phone flat above paper to prevent perspective and keystone distortion.</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
