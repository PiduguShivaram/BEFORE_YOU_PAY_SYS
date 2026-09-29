"use client";

import React from "react";
import { AlertOctagon, RotateCcw, Camera, FileText, X } from "lucide-react";

export interface MobileFailureState {
  title: string;
  message: string;
  category?: "unsupported_format" | "ocr_unreadable" | "network_error" | "precondition_failed" | "general";
  onRetry?: () => void;
  onRetake?: () => void;
  onChooseFile?: () => void;
}

interface MobileFailureRecoveryProps {
  error: MobileFailureState;
  onDismiss: () => void;
}

export const MobileFailureRecovery: React.FC<MobileFailureRecoveryProps> = ({ error, onDismiss }) => {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="surface-card rounded-2xl p-4 sm:p-6 border border-rose-500/40 bg-rose-950/20 shadow-card space-y-4 animate-in fade-in slide-in-from-top-2 duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-rose-500/20 text-rose-400 shrink-0 mt-0.5">
            <AlertOctagon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-sm sm:text-base text-rose-200">{error.title}</h3>
            <p className="text-xs text-rose-300/90 mt-1 leading-relaxed">{error.message}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="p-1.5 rounded-lg text-rose-400 hover:text-white hover:bg-rose-500/20 transition min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          aria-label="Dismiss error notification"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-rose-500/20">
        {error.onRetry && (
          <button
            type="button"
            onClick={error.onRetry}
            className="min-h-[48px] px-4 py-2.5 rounded-xl font-bold text-xs sm:text-sm bg-rose-600 hover:bg-rose-500 text-white shadow transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Try Again</span>
          </button>
        )}

        {error.onRetake && (
          <button
            type="button"
            onClick={error.onRetake}
            className="min-h-[48px] px-4 py-2.5 rounded-xl font-bold text-xs sm:text-sm bg-white/10 hover:bg-white/15 text-white border border-white/15 transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <Camera className="w-4 h-4 text-brand-300" />
            <span>Retake Photo</span>
          </button>
        )}

        {error.onChooseFile && (
          <button
            type="button"
            onClick={error.onChooseFile}
            className="min-h-[48px] px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            <FileText className="w-4 h-4 text-slate-400" />
            <span>Choose Another File</span>
          </button>
        )}
      </div>
    </div>
  );
};
