viewer_code = """\"use client\";

import React, { useState } from \"react\";
import { FileSearch, Sparkles, Image as ImageIcon, AlignLeft, AlertCircle, Eye, Info } from \"lucide-react\";
import { DecisionFlag, OcrLine } from \"../lib/types\";

interface DocumentViewerProps {
  documentText: string;
  ocrLines?: OcrLine[] | null;
  selectedFlag: DecisionFlag | null;
  imagePreviewUrl?: string | null;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentText,
  ocrLines,
  selectedFlag,
  imagePreviewUrl,
}) => {
  const [activeTab, setActiveTab] = useState<\"text\" | \"image\">(\"text\");
  const [inspectedLine, setInspectedLine] = useState<OcrLine | null>(null);

  // If structured ocrLines are provided, use them; otherwise split documentText
  const fallbackLines = documentText.split(\"\\n\").filter((l) => l.trim().length > 0);
  const totalCount = ocrLines && ocrLines.length > 0 ? ocrLines.length : fallbackLines.length;

  return (
    <div className=\"glass-panel rounded-2xl p-6 shadow-card sticky top-6\">
      <div className=\"flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-white/10\">
        <div className=\"flex items-center gap-2.5\">
          <FileSearch className=\"w-5 h-5 text-brand-400\" />
          <h3 className=\"font-bold text-base text-white\">Spatial Document Canvas</h3>
        </div>

        {/* Tab Switcher if image is available */}
        {imagePreviewUrl ? (
          <div className=\"flex items-center gap-1 bg-white/5 p-1 rounded-lg border border-white/10\">
            <button
              onClick={() => setActiveTab(\"text\")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                activeTab === \"text\"
                  ? \"bg-brand-500 text-white shadow-sm\"
                  : \"text-slate-400 hover:text-white\"
              }`}
            >
              <AlignLeft className=\"w-3.5 h-3.5\" />
              OCR Lines ({totalCount})
            </button>
            <button
              onClick={() => setActiveTab(\"image\")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                activeTab === \"image\"
                  ? \"bg-brand-500 text-white shadow-sm\"
                  : \"text-slate-400 hover:text-white\"
              }`}
            >
              <ImageIcon className=\"w-3.5 h-3.5\" />
              Scan Photo
            </button>
          </div>
        ) : (
          <span className=\"text-[11px] text-slate-400 font-mono\">
            {selectedFlag ? \"Line pointer active\" : \"Tap line to inspect provenance\"}
          </span>
        )}
      </div>

      {/* Main Preview Container */}
      <div className=\"relative rounded-xl border border-white/10 bg-slate-950/80 p-4 h-[520px] overflow-y-auto font-mono text-xs text-slate-300 leading-relaxed shadow-inner\">
        {activeTab === \"image\" && imagePreviewUrl ? (
          <div className=\"h-full flex items-center justify-center p-2\">
            <img
              src={imagePreviewUrl}
              alt=\"Uploaded Document\"
              className=\"max-h-full max-w-full object-contain rounded-lg border border-white/10 shadow-lg\"
            />
          </div>
        ) : totalCount === 0 ? (
          <div className=\"h-full flex items-center justify-center text-slate-500 text-xs text-center\">
            Upload a document to inspect spatial bounding boxes and physical lines.
          </div>
        ) : ocrLines && ocrLines.length > 0 ? (
          <div className=\"flex flex-col gap-1.5\">
            {ocrLines.map((line, idx) => {
              const isSelected = inspectedLine?.line_id === line.line_id;
              const isFlagged =
                selectedFlag !== null &&
                (selectedFlag.message.toLowerCase().includes(line.text.toLowerCase().slice(0, 15)) ||
                  line.text.toLowerCase().includes(\"total\") ||
                  line.text.toLowerCase().includes(\"renew\") ||
                  line.text.toLowerCase().includes(\"fee\"));

              const isUnreliable =
                line.is_unreliable ||
                line.confidence < 0.70 ||
                (line.raw_text && /\\d+[a-zA-Z]+[\\/\\\\]+/.test(line.raw_text));

              const hasDiff = line.raw_text && line.raw_text !== line.text;

              return (
                <div
                  key={line.line_id || idx}
                  onClick={() => setInspectedLine(isSelected ? null : line)}
                  className={`group relative flex flex-col p-2 rounded-lg cursor-pointer transition border ${
                    isSelected
                      ? \"bg-brand-500/25 border-brand-400 shadow-sm\"
                      : isFlagged
                      ? \"bg-brand-500/15 border-brand-500/30 text-white\"
                      : isUnreliable
                      ? \"bg-amber-950/20 border-amber-500/30 hover:border-amber-500/50\"
                      : \"border-transparent hover:bg-white/5 hover:border-white/10\"
                  }`}
                >
                  <div className=\"flex items-start gap-2.5\">
                    <span className=\"text-[10px] text-slate-500 select-none w-5 text-right font-mono shrink-0 pt-0.5\">
                      {idx + 1}
                    </span>

                    <div className=\"flex-1 min-w-0\">
                      <div className=\"flex items-center gap-2 flex-wrap\">
                        <span className={`break-words ${isUnreliable ? \"text-amber-200\" : \"text-slate-200\"}`}>
                          {line.text}
                        </span>

                        {isUnreliable && (
                          <span className=\"inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0\">
                            <AlertCircle className=\"w-2.5 h-2.5\" /> Unreliable
                          </span>
                        )}

                        {isFlagged && (
                          <span className=\"text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-brand-500/30 text-brand-300 shrink-0\">
                            Cited
                          </span>
                        )}
                      </div>

                      {hasDiff && (
                        <div className=\"mt-1 text-[11px] text-slate-400 flex items-center gap-1.5\">
                          <span className=\"text-[9px] uppercase font-bold text-slate-500\">Raw:</span>
                          <span className=\"font-mono text-slate-400 bg-white/5 px-1.5 py-0.5 rounded\">
                            \"{line.raw_text}\"
                          </span>
                        </div>
                      )}
                    </div>

                    <span className=\"text-[10px] font-mono text-slate-500 opacity-60 group-hover:opacity-100 transition shrink-0\">
                      {Math.round(line.confidence * 100)}%
                    </span>
                  </div>

                  {/* Tap Inspection Drawer */}
                  {isSelected && (
                    <div className=\"mt-2 pt-2 border-t border-white/10 text-[10px] text-slate-400 font-mono grid grid-cols-2 gap-2 bg-slate-900/60 p-2 rounded\">
                      <div>
                        <span className=\"text-slate-500 block\">Spatial Bounding Box:</span>
                        <span>x: {Math.round(line.bounding_box.x * 100)}%, y: {Math.round(line.bounding_box.y * 100)}%</span>
                        <span className=\"block\">w: {Math.round(line.bounding_box.width * 100)}%, h: {Math.round(line.bounding_box.height * 100)}%</span>
                      </div>
                      <div>
                        <span className=\"text-slate-500 block\">Provenance ID:</span>
                        <span className=\"truncate block\" title={line.line_id}>{line.line_id.slice(0, 13)}...</span>
                        <span className=\"text-slate-500 block mt-1\">Confidence:</span>
                        <span className={line.confidence >= 0.8 ? \"text-emerald-400\" : \"text-amber-400\"}>
                          {line.confidence.toFixed(2)} ({Math.round(line.confidence * 100)}%)
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className=\"flex flex-col gap-1\">
            {fallbackLines.map((line, idx) => {
              const isFlagged =
                selectedFlag !== null &&
                (selectedFlag.message.toLowerCase().includes(line.toLowerCase().slice(0, 15)) ||
                  line.toLowerCase().includes(\"total\") ||
                  line.toLowerCase().includes(\"renew\") ||
                  line.toLowerCase().includes(\"fee\"));

              return (
                <div
                  key={idx}
                  className={`group relative flex items-start gap-3 p-1.5 rounded transition ${
                    isFlagged
                      ? \"bg-brand-500/20 text-white border-l-2 border-brand-400 pl-2.5\"
                      : \"hover:bg-white/5\"
                  }`}
                >
                  <span className=\"text-[10px] text-slate-600 select-none w-5 text-right font-mono\">
                    {idx + 1}
                  </span>
                  <span className=\"flex-1 break-words\">{line}</span>
                  {isFlagged && (
                    <span className=\"shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-brand-500/30 text-brand-300\">
                      Cited
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className=\"mt-3 text-[11px] text-slate-500 flex items-center justify-between\">
        <div className=\"flex items-center gap-1.5\">
          <Sparkles className=\"w-3.5 h-3.5 text-brand-400 shrink-0\" />
          <span>Every finding is anchored to physical line geometry.</span>
        </div>
        {inspectedLine && (
          <button
            onClick={() => setInspectedLine(null)}
            className=\"text-[10px] text-slate-400 hover:text-white underline\"
          >
            Clear inspection
          </button>
        )}
      </div>
    </div>
  );
};
"""

with open("frontend/src/components/DocumentViewer.tsx", "w", encoding="utf-8") as f:
    f.write(viewer_code)
print("Updated frontend/src/components/DocumentViewer.tsx successfully")
