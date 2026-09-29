"use client";

import React, { useRef, useState } from "react";
import {
  UploadCloud,
  Camera,
  FileText,
  Zap,
  PlusCircle,
  X,
  FileCheck,
  Layers,
  ArrowRight,
} from "lucide-react";
import { DocumentClassification } from "../lib/types";
import { CameraCaptureModal } from "./CameraCaptureModal";
import { CaptureGuidance } from "./CaptureGuidance";

interface DropzoneProps {
  onFileSelect: (
    file: File,
    docType: DocumentClassification,
    supportingFile?: File | null
  ) => void;
  isProcessing: boolean;
  selectedPrimaryFile?: File | null;
  onClearPrimaryFile?: () => void;
}

export const Dropzone: React.FC<DropzoneProps> = ({
  onFileSelect,
  isProcessing,
  selectedPrimaryFile,
  onClearPrimaryFile,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [docType, setDocType] = useState<DocumentClassification>("other");
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [supportingFile, setSupportingFile] = useState<File | null>(null);
  const [stagedPrimaryFile, setStagedPrimaryFile] = useState<File | null>(
    selectedPrimaryFile || null
  );
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const supportingFileInputRef = useRef<HTMLInputElement>(null);

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
      const dropped = e.dataTransfer.files[0];
      if (stagedPrimaryFile && !supportingFile) {
        // Drop as supporting file
        setSupportingFile(dropped);
      } else {
        setStagedPrimaryFile(dropped);
        onFileSelect(dropped, docType, supportingFile);
      }
    }
  };

  const handlePrimaryFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setStagedPrimaryFile(file);
      onFileSelect(file, docType, supportingFile);
    }
  };

  const handleSupportingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSupportingFile(file);
      if (stagedPrimaryFile) {
        onFileSelect(stagedPrimaryFile, docType, file);
      }
    }
  };

  const handleCameraCapture = (capturedFile: File) => {
    setStagedPrimaryFile(capturedFile);
    onFileSelect(capturedFile, docType, supportingFile);
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
      setStagedPrimaryFile(file);
      onFileSelect(file, "quotation", supportingFile);
    } catch {
      alert("Failed to load sample quotation. Please select an image from your device.");
    } finally {
      setIsLoadingSample(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="surface-card rounded-2xl p-4 sm:p-7 shadow-card mb-6 border border-white/10 space-y-4">
      {/* Target Document Category Selector */}
      <div className="space-y-1.5 pb-3 border-b border-white/10">
        <div className="flex items-center justify-between">
          <span className="text-[11px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Target Document Category
          </span>
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            Refines deterministic verification rules
          </span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scrollbar-none -mx-1 px-1">
          {(
            [
              { id: "other", label: "Auto Detect" },
              { id: "quotation", label: "Quotation" },
              { id: "invoice", label: "Invoice / Bill" },
              { id: "subscription", label: "Subscription" },
              { id: "warranty", label: "Warranty" },
              { id: "contract", label: "Contract" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setDocType(item.id)}
              className={`min-h-[44px] px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                docType === item.id
                  ? "bg-brand-500 text-white shadow-sm"
                  : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border border-white/5"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Selected Document Role Distinction Banner (When file staged) */}
      {(stagedPrimaryFile || supportingFile) && (
        <div className="space-y-2 p-3 rounded-xl bg-white/5 border border-white/10">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
            Staged Document Scan Roles
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {stagedPrimaryFile && (
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-brand-500/15 border border-brand-500/30 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <FileCheck className="w-4 h-4 text-brand-400 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold text-brand-300 block uppercase">
                      Primary Document
                    </span>
                    <span className="text-white truncate block text-[11px]">
                      {stagedPrimaryFile.name} ({formatFileSize(stagedPrimaryFile.size)})
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setStagedPrimaryFile(null);
                    if (onClearPrimaryFile) onClearPrimaryFile();
                  }}
                  className="p-1 rounded text-slate-400 hover:text-white transition"
                  aria-label="Remove primary document"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {supportingFile ? (
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <Layers className="w-4 h-4 text-cyan-400 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold text-cyan-300 block uppercase">
                      Supporting Document
                    </span>
                    <span className="text-white truncate block text-[11px]">
                      {supportingFile.name} ({formatFileSize(supportingFile.size)})
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSupportingFile(null)}
                  className="p-1 rounded text-slate-400 hover:text-white transition"
                  aria-label="Remove supporting document"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => supportingFileInputRef.current?.click()}
                className="min-h-[44px] flex items-center justify-center gap-2 p-2.5 rounded-lg border border-dashed border-white/20 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/40 hover:bg-cyan-500/5 transition text-xs"
              >
                <PlusCircle className="w-4 h-4 text-cyan-400" />
                <span>Add Supporting Document (Optional)</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Mobile-First Primary Actions Grid */}
      <div className="space-y-3">
        {/* Primary Action: Camera / Live Scan Document (Touch target >= 52px) */}
        <button
          type="button"
          disabled={isProcessing}
          onClick={() => setIsCameraModalOpen(true)}
          className="w-full min-h-[52px] px-5 py-3 rounded-xl font-bold text-sm sm:text-base bg-brand-500 hover:bg-brand-400 text-white shadow-card active:scale-98 transition flex items-center justify-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
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
            className="w-full min-h-[48px] px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 transition active:scale-98 flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            aria-label="Upload Document from Files"
          >
            <FileText className="w-4 h-4 text-brand-400 shrink-0" />
            <span>Upload from Device</span>
          </button>

          <button
            type="button"
            disabled={isProcessing || isLoadingSample}
            onClick={handleLoadSample}
            className="w-full min-h-[48px] px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/25 transition active:scale-98 flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            aria-label="Try Sample Quotation"
          >
            <Zap className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{isLoadingSample ? "Loading Sample..." : "Try Sample Quotation"}</span>
          </button>
        </div>
      </div>

      {/* Desktop Drag & Drop Visual Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        className={`relative overflow-hidden rounded-xl border border-dashed p-4 sm:p-7 text-center transition cursor-pointer ${
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
          <span>Or drag & drop scan / PDF here (PDF, JPEG, PNG, WEBP — Max 25MB)</span>
        </div>
      </div>

      {/* Capture Quality Guidance Drawer */}
      <CaptureGuidance />

      {/* Hidden native file and camera inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,image/jpeg,image/png,image/webp,text/plain"
        onChange={handlePrimaryFileChange}
        className="hidden"
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handlePrimaryFileChange}
        className="hidden"
      />
      <input
        ref={supportingFileInputRef}
        type="file"
        accept=".pdf,image/jpeg,image/png,image/webp,text/plain"
        onChange={handleSupportingFileChange}
        className="hidden"
      />

      {/* Live WebRTC Camera Capture Modal */}
      <CameraCaptureModal
        isOpen={isCameraModalOpen}
        onClose={() => setIsCameraModalOpen(false)}
        onCapture={handleCameraCapture}
        onFallbackToFileInput={() => cameraInputRef.current?.click()}
      />
    </div>
  );
};
