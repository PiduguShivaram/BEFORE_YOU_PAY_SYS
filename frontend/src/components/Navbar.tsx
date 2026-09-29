"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Database,
  BookOpen,
  User,
  CheckCircle2,
  AlertCircle,
  Scan,
  X,
} from "lucide-react";

interface NavbarProps {
  userId: string;
  onUpdateUserId: (newId: string) => void;
  ragCount: number;
  onOpenRag: () => void;
  onOpenOkf: () => void;
  isBackendHealthy: boolean;
  onTriggerScan?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  userId,
  onUpdateUserId,
  ragCount,
  onOpenRag,
  onOpenOkf,
  isBackendHealthy,
  onTriggerScan,
}) => {
  const [isEditingUser, setIsEditingUser] = useState(false);
  const [tempUserId, setTempUserId] = useState(userId);
  const [isMobileUserModalOpen, setIsMobileUserModalOpen] = useState(false);

  const handleSaveUser = () => {
    if (tempUserId.trim()) {
      onUpdateUserId(tempUserId.trim());
      setIsEditingUser(false);
      setIsMobileUserModalOpen(false);
    }
  };

  return (
    <>
      {/* Top Header: Responsive for both mobile and desktop */}
      <header className="sticky top-0 z-40 w-full bg-slate-950/85 backdrop-blur-md border-b border-white/10 py-3 sm:py-4 px-4 sm:px-6 mb-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          {/* Brand Identity */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-700 flex items-center justify-center text-white shadow-glow shrink-0">
              <ShieldCheck className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 sm:gap-2">
                <span className="font-extrabold text-sm sm:text-base tracking-tight bg-gradient-to-b from-white to-slate-200 bg-clip-text text-transparent">
                  Before You Pay
                </span>
                <span className="hidden sm:inline-block text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  Decision Support
                </span>
              </div>
              <p className="text-[10px] sm:text-xs text-slate-400 leading-none mt-0.5 hidden xs:block">
                Mobile Financial Document Auditor
              </p>
            </div>
          </div>

          {/* Right Header Elements */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* API Health Indicator */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] sm:text-xs font-medium border ${
                isBackendHealthy
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/20"
              }`}
              title={isBackendHealthy ? "Backend API connected at localhost:8000" : "Backend unreachable"}
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${
                  isBackendHealthy ? "bg-emerald-400 animate-pulse" : "bg-rose-400"
                }`}
              />
              <span className="hidden xs:inline">
                {isBackendHealthy ? "API Online" : "API Offline"}
              </span>
            </div>

            {/* Desktop Actions (hidden on phone, available in bottom bar) */}
            <div className="hidden md:flex items-center gap-2.5">
              {/* Tenant User ID */}
              {isEditingUser ? (
                <div className="flex items-center gap-1.5 bg-slate-900 border border-brand-500/50 rounded-lg p-1">
                  <input
                    type="text"
                    value={tempUserId}
                    onChange={(e) => setTempUserId(e.target.value)}
                    className="bg-transparent text-xs text-white px-2 py-0.5 focus:outline-none w-32 font-mono"
                    placeholder="Tenant UUID"
                  />
                  <button
                    onClick={handleSaveUser}
                    className="px-2.5 py-1 bg-brand-500 hover:bg-brand-600 text-white rounded text-xs font-semibold"
                  >
                    Save
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsEditingUser(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 transition cursor-pointer"
                  title="Click to edit Tenant User ID"
                  aria-label={`User: ${userId}`}
                >
                  <User className="w-3.5 h-3.5 text-slate-400 shrink-0" aria-hidden="true" />
                  <span className="font-mono text-slate-400">User:</span>
                  <span className="font-mono text-white font-semibold">{userId.slice(0, 8)}...</span>
                </button>
              )}

              {/* Past Records RAG */}
              <button
                type="button"
                onClick={onOpenRag}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-200 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-brand-500/40 transition cursor-pointer"
                aria-label={`Past Records (${ragCount})`}
              >
                <Database className="w-3.5 h-3.5 text-brand-400 shrink-0" aria-hidden="true" />
                <span>Past Records</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300">
                  {ragCount}
                </span>
              </button>

              {/* OKF Rules */}
              <button
                type="button"
                onClick={onOpenOkf}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-200 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-brand-500/40 transition cursor-pointer"
                aria-label="Verification Rules"
              >
                <BookOpen className="w-3.5 h-3.5 text-sky-400 shrink-0" aria-hidden="true" />
                <span>Rules</span>
              </button>
            </div>

            {/* Mobile Profile Trigger (Touch Target >= 44px) */}
            <button
              type="button"
              onClick={() => {
                setTempUserId(userId);
                setIsMobileUserModalOpen(true);
              }}
              className="md:hidden flex items-center justify-center w-11 h-11 rounded-xl bg-white/5 border border-white/10 text-slate-300 active:scale-95 transition cursor-pointer"
              title="Tenant Profile"
              aria-label="Tenant Profile"
            >
              <User className="w-4 h-4 text-brand-400" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Bottom Navigation Bar (Touch Targets >= 44px, sticky bottom) */}
      <nav
        aria-label="Mobile Navigation"
        className="fixed bottom-0 left-0 right-0 z-40 bg-slate-950/95 backdrop-blur-xl border-t border-white/10 px-2 py-1.5 md:hidden shadow-2xl safe-area-inset-bottom"
      >
        <div className="grid grid-cols-4 gap-1 max-w-md mx-auto items-center">
          {/* 1. Scan Document Primary Mobile Action */}
          <button
            type="button"
            onClick={onTriggerScan}
            className="flex flex-col items-center justify-center min-h-[48px] py-1 rounded-xl text-brand-400 hover:text-white active:scale-95 transition cursor-pointer"
            aria-label="Scan Document"
          >
            <Scan className="w-5 h-5 mb-0.5 text-brand-400" aria-hidden="true" />
            <span className="text-[10px] font-bold tracking-tight">Scan</span>
          </button>

          {/* 2. Past Records (RAG) */}
          <button
            type="button"
            onClick={onOpenRag}
            className="flex flex-col items-center justify-center min-h-[48px] py-1 rounded-xl text-slate-400 hover:text-slate-200 active:scale-95 transition relative cursor-pointer"
            aria-label={`Past Document Records: ${ragCount}`}
          >
            <div className="relative">
              <Database className="w-5 h-5 mb-0.5" aria-hidden="true" />
              {ragCount > 0 && (
                <span className="absolute -top-1 -right-2 px-1 py-0.2 rounded-full text-[9px] font-bold bg-brand-500 text-white">
                  {ragCount}
                </span>
              )}
            </div>
            <span className="text-[10px] font-medium tracking-tight">Records</span>
          </button>

          {/* 3. Rules (OKF) */}
          <button
            type="button"
            onClick={onOpenOkf}
            className="flex flex-col items-center justify-center min-h-[48px] py-1 rounded-xl text-slate-400 hover:text-slate-200 active:scale-95 transition cursor-pointer"
            aria-label="Verification Rules"
          >
            <BookOpen className="w-5 h-5 mb-0.5" aria-hidden="true" />
            <span className="text-[10px] font-medium tracking-tight">Rules</span>
          </button>

          {/* 4. Profile / Tenant */}
          <button
            type="button"
            onClick={() => {
              setTempUserId(userId);
              setIsMobileUserModalOpen(true);
            }}
            className="flex flex-col items-center justify-center min-h-[48px] py-1 rounded-xl text-slate-400 hover:text-slate-200 active:scale-95 transition cursor-pointer"
            aria-label="Tenant Profile"
          >
            <User className="w-5 h-5 mb-0.5" aria-hidden="true" />
            <span className="text-[10px] font-medium tracking-tight">Profile</span>
          </button>
        </div>
      </nav>

      {/* Mobile Profile & Tenant ID Modal */}
      {isMobileUserModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-sm rounded-2xl bg-slate-900 border border-white/10 p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <User className="w-5 h-5 text-brand-400" />
                <h3 className="font-bold text-base text-white">Tenant Profile</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsMobileUserModalOpen(false)}
                className="w-11 h-11 flex items-center justify-center rounded-xl bg-white/5 text-slate-400 hover:text-white"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Multi-Tenant User UUID
              </label>
              <input
                type="text"
                value={tempUserId}
                onChange={(e) => setTempUserId(e.target.value)}
                className="w-full p-3 rounded-xl bg-black/50 border border-white/10 text-white font-mono text-xs focus:outline-none focus:border-brand-500"
                placeholder="Enter user or tenant UUID"
              />
              <p className="text-[11px] text-slate-400">
                Isolates your uploaded documents and RAG history to this tenant identifier.
              </p>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={handleSaveUser}
                className="flex-1 min-h-[44px] py-2.5 rounded-xl font-bold text-sm bg-brand-500 text-white shadow-glow hover:bg-brand-600 active:scale-95 transition"
              >
                Save Tenant ID
              </button>
              <button
                type="button"
                onClick={() => setIsMobileUserModalOpen(false)}
                className="min-h-[44px] px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-300 bg-white/5 hover:bg-white/10 active:scale-95 transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
