"use client";

import React, { useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  Plus,
  Trash2,
  Scale,
  Sparkles,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { MultiQuoteComparisonResult } from "../lib/types";
import { compareQuotes } from "../lib/api";

interface MultiQuoteUploadDropzoneProps {
  userId: string;
  onComparisonComplete: (result: MultiQuoteComparisonResult) => void;
}

export function MultiQuoteUploadDropzone({
  userId,
  onComparisonComplete,
}: MultiQuoteUploadDropzoneProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAddFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    setError(null);

    const combined = [...files, ...selected];
    if (combined.length > 5) {
      setError("You can compare a maximum of 5 quotations at a time.");
      setFiles(combined.slice(0, 5));
    } else {
      setFiles(combined);
    }
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleStartComparison = async () => {
    if (files.length < 2) {
      setError("Please add at least 2 quotation documents to compare.");
      return;
    }
    setError(null);
    setIsProcessing(true);

    try {
      const result = await compareQuotes(files, userId);
      onComparisonComplete(result);
    } catch (err: any) {
      setError(err.message || "Failed to compare quotations. Please ensure files are clear.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 sm:p-7 shadow-2xl text-slate-100 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Scale className="w-5 h-5 text-blue-400" />
            N-Way Multi-Quotation Comparison
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Upload 2 to 5 dealer quotes/bills to align items, compute deltas, and find missing charges.
          </p>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-medium">
          {files.length} / 5 Selected
        </span>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-red-950/40 border border-red-800/40 text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Selected Files List */}
      {files.length > 0 ? (
        <div className="space-y-2">
          {files.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-[11px] flex-shrink-0">
                  #{idx + 1}
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-slate-200 truncate">{file.name}</div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleRemoveFile(idx)}
                disabled={isProcessing}
                className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="cursor-pointer border-2 border-dashed border-slate-800 hover:border-blue-500/50 rounded-xl p-8 text-center bg-slate-950/40 hover:bg-slate-950/70 transition-all flex flex-col items-center justify-center gap-2"
        >
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div className="text-sm font-semibold text-slate-200">
            Click to select 2 to 5 quotation scans or PDFs
          </div>
          <div className="text-xs text-slate-500">
            Supports PNG, JPEG, PDF up to 5 files
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,text/plain"
          onChange={handleAddFiles}
          className="hidden"
        />

        {files.length > 0 && files.length < 5 && (
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isProcessing}
            className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-semibold transition"
          >
            <Plus className="w-4 h-4" />
            Add Another Quote ({5 - files.length} remaining)
          </button>
        )}

        <button
          onClick={handleStartComparison}
          disabled={files.length < 2 || isProcessing}
          className={`w-full sm:w-auto ml-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold transition shadow-lg ${
            files.length >= 2 && !isProcessing
              ? "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20"
              : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-800"
          }`}
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span>Aligning {files.length} Quotations...</span>
            </>
          ) : (
            <>
              <Scale className="w-4 h-4" />
              <span>Compare {files.length >= 2 ? `${files.length} Quotes` : "Quotes (Add ≥ 2)"}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
