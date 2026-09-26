"use client";

import React, { useRef, useState } from "react";
import {
  UploadCloud,
  Camera,
  FileText,
  Sparkles,
  Zap,
} from "lucide-react";
import { DocumentClassification } from "../lib/types";

interface DropzoneProps {
  onFileSelect: (file: File, docType: DocumentClassification) => void;
  isProcessing: boolean;
}

export const Dropzone: React.FC<DropzoneProps> = ({ onFileSelect, isProcessing }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [docType, setDocType] = useState<DocumentClassification>("other");
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileSelect(e.dataTransfer.files[0], docType);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0], docType);
    }
  };

  const handleLoadSample = async () => {
    if (isProcessing || isLoadingSample) return;
    setIsLoadingSample(true);
    try {
      const response = await fetch("/sample_handwritten_quotation.jpeg");
      const blob = await response.blob();
      const file = new File([blob], "handwritten_vehicle_quotation.jpeg", {
        type: "image/jpeg",
      });
      onFileSelect(file, "quotation");
    } catch (err) {
      alert("Failed to load sample quotation. Please select an image from your device.");
    } finally {
      setIsLoadingSample(false);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-7 shadow-card mb-6 border border-white/10 space-y-4">
      {/* Target Document Category Selector (Horizontally scrollable for mobile) */}
      <div className="space-y-1.5 pb-3 border-b border-white/10">
        <div className="flex items-center justify-between">
          <span className="text-[11px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Target Document Category
          </span>
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            Refines verification rules
          </span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scrollbar-none -mx-1 px-1">
          {(
            [
              { id: "other", label: "Auto Detect" },
              { id: "quotation", label: "Quotation" },
              { id: "invoice", label: "Invoice" },
              { id: "subscription", label: "Subscription" },
              { id: "warranty", label: "Warranty" },
              { id: "contract", label: "Contract" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setDocType(item.id)}
              className={`min-h-[44px] px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 active:scale-95 ${
                docType === item.id
                  ? "bg-brand-500 text-white shadow-glow"
                  : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border border-white/5"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile-First Primary Actions Grid */}
      <div className="space-y-3">
        {/* Primary Action: Camera / Scan Document (High touch target >= 48px) */}
        <button
          type="button"
          disabled={isProcessing}
          onClick={() => cameraInputRef.current?.click()}
          className="w-full min-h-[52px] px-5 py-3 rounded-xl font-bold text-sm sm:text-base bg-gradient-to-r from-brand-500 via-indigo-600 to-brand-600 text-white shadow-glow hover:brightness-110 active:scale-98 transition flex items-center justify-center gap-2.5"
          aria-label="Scan Document with Camera"
        >
          <Camera className="w-5 h-5 text-white shrink-0" />
          <span>Camera / Scan Document</span>
        </button>

        {/* Secondary Mobile Actions: Upload from device & Try Sample */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <button
            type="button"
            disabled={isProcessing}
            onClick={() => fileInputRef.current?.click()}
            className="w-full min-h-[48px] px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 transition active:scale-98 flex items-center justify-center gap-2"
            aria-label="Upload Document from Files"
          >
            <FileText className="w-4 h-4 text-brand-400 shrink-0" />
            <span>Upload from Device</span>
          </button>

          <button
            type="button"
            disabled={isProcessing || isLoadingSample}
            onClick={handleLoadSample}
            className="w-full min-h-[48px] px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/25 transition active:scale-98 flex items-center justify-center gap-2"
            aria-label="Try Sample Quotation"
          >
            <Zap className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{isLoadingSample ? "Loading Sample..." : "Try Sample Quotation"}</span>
          </button>
        </div>
      </div>

      {/* Desktop Drag & Drop Visual Area (Compact on mobile) */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        className={`relative overflow-hidden rounded-xl border border-dashed p-4 sm:p-8 text-center transition cursor-pointer ${
          isDragOver
            ? "border-brand-500 bg-brand-500/10"
            : "border-white/15 bg-slate-950/40 hover:border-brand-500/50 hover:bg-slate-900/30"
        } ${isProcessing ? "pointer-events-none opacity-80" : ""}`}
      >
        {isProcessing && (
          <div className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-brand-400 to-transparent shadow-[0_0_15px_#818cf8] animate-scan z-10" />
        )}

        <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
          <UploadCloud className="w-4 h-4 text-brand-400" />
          <span>Or drag & drop scan / PDF here (Max 25MB)</span>
        </div>
      </div>

      {/* Hidden native inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,image/jpeg,image/png,image/webp,text/plain"
        onChange={handleFileInputChange}
        className="hidden"
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileInputChange}
        className="hidden"
      />
    </div>
  );
};
