"use client";

import React, { useState } from "react";
import { X, Database, Plus, Check, Loader2 } from "lucide-react";
import { DocumentClassification, RagRecord } from "../lib/types";
import { storeUserDocument } from "../lib/api";
import { generateUUID } from "../lib/utils";

interface RagDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  records: RagRecord[];
  onRecordAdded: (record: RagRecord) => void;
}

export const RagDrawer: React.FC<RagDrawerProps> = ({
  isOpen,
  onClose,
  userId,
  records,
  onRecordAdded,
}) => {
  const [docType, setDocType] = useState<DocumentClassification>("contract");
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setIsSubmitting(true);
    setSuccessMsg("");

    try {
      const docId = generateUUID();
      await storeUserDocument(userId, docId, docType, content.trim());

      const newRecord: RagRecord = {
        id: docId,
        type: docType,
        content: content.trim(),
        indexedAt: new Date().toLocaleTimeString(),
      };

      onRecordAdded(newRecord);
      setContent("");
      setSuccessMsg("Document successfully indexed in your isolated SQLite RAG store!");
      setTimeout(() => setSuccessMsg(""), 3500);
    } catch (err: any) {
      alert(`Error storing document: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
      <div className="glass-panel rounded-2xl max-w-lg w-full max-h-[90vh] flex flex-col shadow-2xl border border-white/10">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/10">
          <div className="flex items-center gap-2.5 text-brand-400">
            <Database className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">User Document RAG Store</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          <p className="text-xs text-slate-400 leading-relaxed">
            Index your real historical agreements, prior quotations, or active warranties. Future scans
            are cross-referenced against these records using strict tenant isolation (<code className="text-brand-300">WHERE user_id = ?</code>).
          </p>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Document Category
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocumentClassification)}
                className="w-full bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
              >
                <option value="contract">Prior Contract / Master Services Agreement</option>
                <option value="warranty">Active Hardware / Software Warranty</option>
                <option value="quotation">Approved Past Quotation</option>
                <option value="subscription">Recurring Subscription Terms</option>
                <option value="bill">Historical Utility / Service Bill</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Key Terms & Pricing Clauses
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="e.g. Master Services Agreement: Monthly maintenance fee agreed at $80.00/mo through 2026."
                rows={3}
                required
                className="w-full bg-slate-900 border border-white/10 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-sans"
              />
            </div>

            {successMsg && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                <Check className="w-4 h-4" />
                <span>{successMsg}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl font-semibold text-xs bg-brand-500 hover:bg-brand-600 text-white shadow-glow transition disabled:opacity-50"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              <span>Index Record in Private RAG Database</span>
            </button>
          </form>

          {/* Existing Records */}
          <div className="pt-4 border-t border-white/10">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
              Currently Indexed Records ({records.length})
            </h4>

            {records.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-500 bg-white/2 rounded-xl border border-white/5">
                No past records indexed yet. Add your prior agreement above.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-48 overflow-y-auto">
                {records.map((rec) => (
                  <div
                    key={rec.id}
                    className="p-3 rounded-xl bg-slate-900/60 border border-white/5 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] uppercase font-bold text-brand-400">
                        {rec.type}
                      </span>
                      {rec.indexedAt && (
                        <span className="text-[10px] text-slate-500">{rec.indexedAt}</span>
                      )}
                    </div>
                    <p className="text-slate-300">{rec.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
