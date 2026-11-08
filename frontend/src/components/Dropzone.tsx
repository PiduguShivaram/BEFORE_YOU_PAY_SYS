"use client";

import React, { useRef, useState } from "react";
import {
  UploadCloud,
  Camera,
  FileText,
  PlusCircle,
  X,
  FileCheck,
  Layers,
  AlertCircle,
} from "lucide-react";
import { DocumentClassification } from "../lib/types";
import { CameraCaptureModal } from "./CameraCaptureModal";
import { CaptureGuidance } from "./CaptureGuidance";
import { Card3D } from "./Card3D";

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
  const [validationError, setValidationError] = useState<string | null>(null);
  const [supportingFile, setSupportingFile] = useState<File | null>(null);
  const [stagedPrimaryFile, setStagedPrimaryFile] = useState<File | null>(
    selectedPrimaryFile || null
  );
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const supportingFileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
  const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"];

  const validateFile = (file: File): boolean => {
    if (file.size > MAX_FILE_SIZE) {
      setValidationError(`File "${file.name}" exceeds maximum allowed size of 25MB.`);
      return false;
    }
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const mime = file.type.toLowerCase();
    const isAllowedExt = ALLOWED_EXTENSIONS.some((e) => ext === e);
    const isAllowedMime =
      mime.startsWith("image/") || mime === "application/pdf" || mime === "text/plain";
    if (!isAllowedExt && !isAllowedMime) {
      setValidationError(
        `Unsupported format for "${file.name}". Please upload PDF, PNG, JPG, or WEBP.`
      );
      return false;
    }
    setValidationError(null);
    return true;
  };

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
      if (!validateFile(dropped)) return;
      if (stagedPrimaryFile && !supportingFile) {
        setSupportingFile(dropped);
        onFileSelect(stagedPrimaryFile, docType, dropped);
      } else {
        setStagedPrimaryFile(dropped);
        onFileSelect(dropped, docType, supportingFile);
      }
    }
  };

  const handlePrimaryFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!validateFile(file)) return;
      setStagedPrimaryFile(file);
      onFileSelect(file, docType, supportingFile);
    }
  };

  const handleSupportingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!validateFile(file)) return;
      setSupportingFile(file);
      if (stagedPrimaryFile) {
        onFileSelect(stagedPrimaryFile, docType, file);
      }
    }
  };

  const handleCameraCapture = (capturedFile: File) => {
    if (!validateFile(capturedFile)) return;
    setStagedPrimaryFile(capturedFile);
    onFileSelect(capturedFile, docType, supportingFile);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Card3D intensity={7} glare={true} depth={20} className="mb-6">
      <div className="surface-card rounded-2xl p-4 sm:p-7 shadow-card border border-white/10 space-y-4">
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

      {/* Validation Error Alert */}
      {validationError && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs animate-in fade-in">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span className="flex-1">{validationError}</span>
          <button
            type="button"
            onClick={() => setValidationError(null)}
            className="text-rose-400 hover:text-white p-0.5"
            aria-label="Dismiss error"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Primary Actions Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Primary Action 1: Camera / Live Scan Document (Touch target >= 52px) */}
        <button
          type="button"
          disabled={isProcessing}
          onClick={() => setIsCameraModalOpen(true)}
          className="w-full min-h-[52px] px-5 py-3 rounded-xl font-bold text-sm bg-gradient-to-r from-brand-500 to-indigo-600 hover:from-brand-400 hover:to-indigo-500 text-white shadow-lg shadow-brand-500/25 active:scale-98 transition flex items-center justify-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          aria-label="Scan Document with Camera"
        >
          <Camera className="w-5 h-5 text-white shrink-0" />
          <span>Camera / Scan Document</span>
        </button>

        {/* Primary Action 2: Upload from Device */}
        <button
          type="button"
          disabled={isProcessing}
          onClick={() => fileInputRef.current?.click()}
          className="w-full min-h-[52px] px-5 py-3 rounded-xl font-bold text-sm bg-slate-900/90 hover:bg-slate-800 text-slate-100 border border-white/15 hover:border-brand-500/50 shadow-md active:scale-98 transition flex items-center justify-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          aria-label="Upload Document from Device"
        >
          <FileText className="w-5 h-5 text-brand-400 shrink-0" />
          <span>Upload from Device</span>
        </button>
      </div>

      {/* Drag & Drop Visual Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        className={`relative overflow-hidden rounded-xl border border-dashed p-4 sm:p-6 text-center transition cursor-pointer ${
          isDragOver
            ? "border-brand-500 bg-brand-500/10"
            : "border-white/15 bg-slate-950/40 hover:border-brand-500/50 hover:bg-slate-900/30"
        } ${isProcessing ? "pointer-events-none opacity-80" : ""}`}
      >
        {isProcessing && (
          <div className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-brand-400 to-transparent shadow-[0_0_15px_#818cf8] animate-scan z-10" />
        )}

        <div className="flex flex-col items-center justify-center gap-1.5 text-xs text-slate-400">
          <div className="flex items-center gap-2 text-slate-300 font-medium">
            <UploadCloud className="w-4 h-4 text-brand-400" />
            <span>Drop your bill, invoice, or quotation here</span>
          </div>
          <span className="text-[11px] text-slate-500">
            Supported formats: PDF, PNG, JPG, WEBP (Max 25MB)
          </span>
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
    </Card3D>
  );
};
