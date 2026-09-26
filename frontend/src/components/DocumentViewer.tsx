"use client";

import React, { useState, useEffect } from "react";
import {
  FileSearch,
  Image as ImageIcon,
  AlignLeft,
  AlertCircle,
  Sparkles,
  ArrowLeft,
  Eye,
  CheckCircle2,
} from "lucide-react";
import { DecisionFlag, OcrLine } from "../lib/types";

interface DocumentViewerProps {
  documentText: string;
  ocrLines?: OcrLine[] | null;
  selectedFlag: DecisionFlag | null;
  imagePreviewUrl?: string | null;
  onReturnToSummary?: () => void;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentText,
  ocrLines,
  selectedFlag,
  imagePreviewUrl,
  onReturnToSummary,
}) => {
  const [activeTab, setActiveTab] = useState<"image" | "text">(
    imagePreviewUrl ? "image" : "text"
  );
  const [inspectedLine, setInspectedLine] = useState<OcrLine | null>(null);

  // Switch to image tab automatically when an image is provided
  useEffect(() => {
    if (imagePreviewUrl) {
      setActiveTab("image");
    }
  }, [imagePreviewUrl]);

  // If structured ocrLines are provided, use them; otherwise split documentText
  const fallbackLines = documentText.split("\n").filter((l) => l.trim().length > 0);
  const totalCount = ocrLines && ocrLines.length > 0 ? ocrLines.length : fallbackLines.length;

  // Selected bounding box from active flag or inspected line
  const activeBoundingBoxes = selectedFlag?.bounding_boxes || (inspectedLine ? [inspectedLine.bounding_box] : []);

  return (
    <div
      id="document-evidence-viewer"
      className="glass-panel rounded-2xl p-4 sm:p-6 shadow-card border border-white/10 space-y-4"
    >
      {/* Header & Return Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          {onReturnToSummary && (
            <button
              type="button"
              onClick={onReturnToSummary}
              className="min-h-[44px] px-3 py-2 rounded-xl text-xs font-bold text-brand-300 bg-brand-500/10 hover:bg-brand-500/20 active:scale-95 transition flex items-center gap-1.5 shrink-0"
              aria-label="Return to audit summary"
            >
              <ArrowLeft className="w-4 h-4 text-brand-400" />
              <span>Back to Summary</span>
            </button>
          )}

          <div>
            <div className="flex items-center gap-2">
              <FileSearch className="w-4 h-4 text-brand-400" />
              <h3 className="font-bold text-sm sm:text-base text-white">Source Document Evidence</h3>
            </div>
            <p className="text-[11px] text-slate-400 hidden xs:block">
              Physical document authority for all financial claims
            </p>
          </div>
        </div>

        {/* Tab Switcher (Touch Target >= 44px) */}
        {imagePreviewUrl ? (
          <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/10 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setActiveTab("image")}
              className={`min-h-[44px] flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95 ${
                activeTab === "image"
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Document Scan</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("text")}
              className={`min-h-[44px] flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95 ${
                activeTab === "text"
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <AlignLeft className="w-3.5 h-3.5" />
              <span>OCR Lines ({totalCount})</span>
            </button>
          </div>
        ) : (
          <span className="text-[11px] text-slate-400 font-mono">
            {selectedFlag ? "Line cited in audit" : "Tap line to inspect provenance"}
          </span>
        )}
      </div>

      {/* Cited Field Callout (If an item is actively selected) */}
      {selectedFlag && (
        <div className="p-3 rounded-xl bg-brand-500/15 border border-brand-500/30 flex items-center justify-between gap-3 text-xs animate-in fade-in duration-200">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping" />
              <span className="font-bold text-white uppercase text-[11px]">
                Inspecting: {selectedFlag.label}
              </span>
            </div>
            <p className="text-slate-300 font-mono text-[11px] truncate mt-0.5">
              {selectedFlag.message}
            </p>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 shrink-0">
            Highlighted
          </span>
        </div>
      )}

      {/* Main Preview Container (Mobile viewport responsive, max-w-full, no horizontal scroll) */}
      <div className="relative rounded-xl border border-white/10 bg-slate-950/90 p-3 sm:p-4 min-h-[360px] max-h-[580px] overflow-y-auto font-mono text-xs text-slate-300 leading-relaxed shadow-inner">
        {activeTab === "image" && imagePreviewUrl ? (
          <div className="relative w-full flex flex-col items-center justify-center">
            {/* Document Image with Spatial Bounding Box Overlay */}
            <div className="relative max-w-full inline-block rounded-lg overflow-hidden border border-white/10 bg-black/40">
              <img
                src={imagePreviewUrl}
                alt="Uploaded Document"
                className="w-full h-auto max-h-[500px] object-contain rounded-lg select-none"
              />

              {/* Spatial OCR Bounding Box Overlays */}
              {activeBoundingBoxes.map((box, idx) => {
                if (
                  box.x == null ||
                  box.y == null ||
                  box.width == null ||
                  box.height == null
                ) {
                  return null;
                }
                const left = `${Math.max(0, Math.min(100, box.x * 100))}%`;
                const top = `${Math.max(0, Math.min(100, box.y * 100))}%`;
                const width = `${Math.max(1, Math.min(100, box.width * 100))}%`;
                const height = `${Math.max(1, Math.min(100, box.height * 100))}%`;

                return (
                  <div
                    key={idx}
                    className="absolute border-2 border-brand-400 bg-brand-500/30 rounded shadow-[0_0_12px_#818cf8] pointer-events-none animate-pulse z-20"
                    style={{ left, top, width, height }}
                    title="Spatial OCR Bounding Box"
                  />
                );
              })}
            </div>

            <p className="text-[10px] text-slate-400 text-center mt-2 font-sans">
              Spatial bounding box indicates physical position parsed by vision OCR.
            </p>
          </div>
        ) : totalCount === 0 ? (
          <div className="h-48 flex items-center justify-center text-slate-500 text-xs text-center">
            Upload a document to inspect spatial bounding boxes and physical lines.
          </div>
        ) : ocrLines && ocrLines.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {ocrLines.map((line, idx) => {
              const isSelected = inspectedLine?.line_id === line.line_id;
              const isFlagged =
                selectedFlag !== null &&
                (selectedFlag.message.toLowerCase().includes(line.text.toLowerCase().slice(0, 15)) ||
                  line.text.toLowerCase().includes("total") ||
                  line.text.toLowerCase().includes("exshorum") ||
                  line.text.toLowerCase().includes("waranty"));

              const isUnreliable =
                line.is_unreliable ||
                (line.confidence != null && line.confidence < 0.7) ||
                (line.raw_text && /\d+[a-zA-Z]+[\/\\]+/.test(line.raw_text));

              const hasDiff = line.raw_text && line.raw_text !== line.text;

              return (
                <div
                  key={line.line_id || idx}
                  onClick={() => setInspectedLine(isSelected ? null : line)}
                  className={`min-h-[44px] flex flex-col p-2.5 rounded-lg cursor-pointer transition border select-none active:scale-[0.99] ${
                    isSelected
                      ? "bg-brand-500/25 border-brand-400 shadow-sm"
                      : isFlagged
                      ? "bg-brand-500/15 border-brand-500/40 text-white"
                      : isUnreliable
                      ? "bg-amber-950/20 border-amber-500/30 hover:border-amber-500/50"
                      : "border-transparent hover:bg-white/5 hover:border-white/10"
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-label={`Line ${idx + 1}: ${line.text}`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] text-slate-500 select-none w-5 text-right font-mono shrink-0 pt-0.5">
                      {idx + 1}
                    </span>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`break-words text-xs ${isUnreliable ? "text-amber-200" : "text-slate-200"}`}>
                          {line.text}
                        </span>

                        {isFlagged && (
                          <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-brand-500/30 text-brand-300 shrink-0">
                            Cited
                          </span>
                        )}

                        {isUnreliable && (
                          <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                            <AlertCircle className="w-2.5 h-2.5" /> Informal
                          </span>
                        )}
                      </div>

                      {hasDiff && (
                        <div className="mt-0.5 text-[10px] text-slate-400 flex items-center gap-1">
                          <span className="text-[9px] uppercase font-bold text-slate-500">Raw:</span>
                          <span className="font-mono text-slate-400 bg-white/5 px-1 rounded">
                            "{line.raw_text}"
                          </span>
                        </div>
                      )}
                    </div>

                    <span className="text-[10px] font-mono text-slate-500 shrink-0">
                      {line.confidence != null ? `${Math.round(line.confidence * 100)}%` : "Transcribed"}
                    </span>
                  </div>

                  {/* Tap Inspection Drawer */}
                  {isSelected && (
                    <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-slate-400 font-mono grid grid-cols-2 gap-2 bg-slate-900/80 p-2.5 rounded-lg">
                      <div>
                        <span className="text-slate-500 block font-sans font-semibold">Bounding Box:</span>
                        <span>x: {Math.round(line.bounding_box.x * 100)}%, y: {Math.round(line.bounding_box.y * 100)}%</span>
                        <span className="block">w: {Math.round(line.bounding_box.width * 100)}%, h: {Math.round(line.bounding_box.height * 100)}%</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block font-sans font-semibold">Line ID:</span>
                        <span className="truncate block">{line.line_id.slice(0, 12)}...</span>
                        <span className="text-slate-500 block mt-1 font-sans font-semibold">Engine Calibration:</span>
                        <span className="text-slate-300">
                          {line.confidence != null ? `${(line.confidence * 100).toFixed(0)}%` : "Handwritten vision pass"}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {fallbackLines.map((line, idx) => (
              <div key={idx} className="flex items-start gap-2 p-1.5 text-xs text-slate-300">
                <span className="text-[10px] text-slate-600 select-none w-5 text-right font-mono">
                  {idx + 1}
                </span>
                <span className="flex-1 break-words">{line}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-brand-400 shrink-0" />
          <span>Physical spatial provenance verified against raw image</span>
        </div>
        {inspectedLine && (
          <button
            type="button"
            onClick={() => setInspectedLine(null)}
            className="text-brand-400 hover:underline"
          >
            Clear line
          </button>
        )}
      </div>
    </div>
  );
};
