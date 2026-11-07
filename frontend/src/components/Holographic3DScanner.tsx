"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Layers,
  Sparkles,
  ShieldCheck,
  UploadCloud,
  FileCheck,
  Cpu,
  Calculator,
  Scale,
  Binary,
  Compass,
} from "lucide-react";
import {
  FinalDecisionSupportResult,
  DecisionFlag,
  FinancialComponent,
  OkfRule,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface Holographic3DScannerProps {
  result?: FinalDecisionSupportResult | null;
  imagePreviewUrl?: string | null;
  okfRules?: OkfRule[];
  onSelectFlag?: (flag: DecisionFlag) => void;
  onSelectComponent?: (comp: FinancialComponent) => void;
  onTriggerUpload?: () => void;
}

export function Holographic3DScanner({
  result,
  imagePreviewUrl,
  okfRules = [],
  onSelectFlag,
  onSelectComponent,
  onTriggerUpload,
}: Holographic3DScannerProps) {
  // 3D Orbit Camera Angles
  const [rotX, setRotX] = useState<number>(16);
  const [rotY, setRotY] = useState<number>(-18);
  const [rotZ, setRotZ] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [viewPreset, setViewPreset] = useState<"isometric" | "exploded" | "orbit" | "flat">("isometric");
  const [isAutoRotating, setIsAutoRotating] = useState<boolean>(true);
  const [activeFlagIdx, setActiveFlagIdx] = useState<number>(0);

  // Auto-rotation idle loop
  useEffect(() => {
    if (!isAutoRotating || isDragging) return;
    let animId: number;
    let angle = 0;
    const loop = () => {
      angle += 0.006;
      if (viewPreset === "orbit") {
        setRotY((prev) => (prev + 0.18) % 360);
        setRotX(14 + Math.sin(angle) * 4);
      } else if (viewPreset === "isometric") {
        setRotY(-18 + Math.sin(angle * 2) * 4);
        setRotX(16 + Math.cos(angle * 2) * 2.5);
      }
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isAutoRotating, isDragging, viewPreset]);

  // Mouse drag for full 3D orbital manipulation
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setIsAutoRotating(false);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - dragStart.x;
      const deltaY = e.clientY - dragStart.y;
      setRotY((prev) => (prev + deltaX * 0.45) % 360);
      setRotX((prev) => Math.max(-60, Math.min(60, prev - deltaY * 0.45)));
      setDragStart({ x: e.clientX, y: e.clientY });
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleSetPreset = (preset: "isometric" | "exploded" | "orbit" | "flat") => {
    setViewPreset(preset);
    if (preset === "isometric") {
      setRotX(20);
      setRotY(-20);
      setRotZ(2);
    } else if (preset === "flat") {
      setRotX(0);
      setRotY(0);
      setRotZ(0);
      setIsAutoRotating(false);
    } else if (preset === "exploded") {
      setRotX(26);
      setRotY(-30);
      setRotZ(0);
      setIsAutoRotating(false);
    } else if (preset === "orbit") {
      setRotX(15);
      setIsAutoRotating(true);
    }
  };

  // 100% REAL DATA EXTRACTION FROM RESULT
  const currency = result?.document?.currency || result?.semantic_financial_structure?.currency || "INR";
  const rawStatedTotal = result?.document?.total_amount?.normalized_value ?? result?.semantic_financial_structure?.stated_total;
  const statedTotalNum = rawStatedTotal != null ? Number(rawStatedTotal) : null;
  const vendorName = result?.document?.vendor_name?.normalized_value ? String(result.document.vendor_name.normalized_value) : null;
  const invoiceNumber = result?.document_id || result?.document?.document_id || null;
  const documentType = result?.document?.document_type || "financial document";

  // Real Findings & Discrepancies
  const realFlags = result?.flags || [];
  const realChecks = result?.validation_checks || [];
  const criticalFindings = realFlags.filter((f) => f.severity === "CRITICAL" || f.severity === "WARNING");
  const activeFlag = realFlags[activeFlagIdx] || realFlags[0] || null;

  // Real Potential Cost Reduction
  const realSavingsTotal = result?.cost_reduction_summary?.max_potential_reduction ?? result?.cost_reduction_summary?.confirmed_optional_amount ?? null;

  return (
    <div className="relative w-full rounded-3xl border border-cyan-500/25 bg-slate-950/85 backdrop-blur-2xl p-4 sm:p-7 shadow-2xl shadow-cyan-950/40 overflow-hidden">
      {/* 3D Volumetric Lighting */}
      <div className="absolute -top-32 -left-32 w-80 h-80 rounded-full bg-cyan-500/15 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-80 h-80 rounded-full bg-indigo-500/15 blur-[120px] pointer-events-none" />

      {/* Top Controls Header */}
      <div className="relative z-30 flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-md shadow-cyan-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                {result ? "3D Spatial Evidence Inspector" : "3D Spatial Verification Chamber"}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                {result ? "Live Real Document Data" : "7-Stage Engine Ready"}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {result
                ? "Interactive 3D geometry of your verified document and extracted findings"
                : "Deterministic arithmetic rules and spatial geometry ready for your scan"}
            </p>
          </div>
        </div>

        {/* 3D Camera Preset Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-900/90 border border-white/10 rounded-xl p-1 text-xs">
          <button
            type="button"
            onClick={() => handleSetPreset("isometric")}
            className={`px-2.5 py-1 rounded-lg font-medium transition ${
              viewPreset === "isometric"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Isometric 3D
          </button>
          <button
            type="button"
            onClick={() => handleSetPreset("exploded")}
            className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1 ${
              viewPreset === "exploded"
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Layers className="w-3 h-3" />
            <span>Exploded Z-Layers</span>
          </button>
          <button
            type="button"
            onClick={() => handleSetPreset("orbit")}
            className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1 ${
              viewPreset === "orbit"
                ? "bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <RotateCw className="w-3 h-3" />
            <span>360° Orbit</span>
          </button>
          <button
            type="button"
            onClick={() => handleSetPreset("flat")}
            className={`px-2.5 py-1 rounded-lg font-medium transition ${
              viewPreset === "flat"
                ? "bg-slate-800 text-white border border-white/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Flat
          </button>
        </div>
      </div>

      {/* 3D Viewport Stage Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center pt-5">
        {/* Left Column: 3D Holographic Canvas */}
        <div
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className="lg:col-span-8 relative h-[380px] sm:h-[440px] flex items-center justify-center cursor-grab active:cursor-grabbing select-none overflow-hidden rounded-2xl bg-gradient-to-b from-slate-900/80 to-slate-950/95 border border-white/10"
          style={{ perspective: "1200px" }}
        >
          {/* Spatial 3D Laser Horizon Floor */}
          <div
            className="absolute w-[500px] h-[500px] pointer-events-none rounded-full"
            style={{
              background:
                "radial-gradient(circle, rgba(6, 182, 212, 0.18) 0%, rgba(99, 102, 241, 0.06) 50%, transparent 70%)",
              transform: "translateY(140px) rotateX(75deg)",
            }}
          />

          {/* Interactive Drag Hint */}
          <div className="absolute top-3 left-3 z-30 px-2.5 py-1 rounded-full bg-slate-900/80 border border-white/10 text-[10px] text-slate-300 flex items-center gap-1.5 backdrop-blur-md">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>Click & drag to rotate 3D view</span>
          </div>

          {/* ══════════ THE 3D ROTATING DOCUMENT / VAULT STAGE ══════════ */}
          <div
            className="relative w-[280px] sm:w-[330px] h-[340px] sm:h-[390px] transition-transform duration-75 ease-out will-change-transform preserve-3d"
            style={{
              transform: `rotateX(${rotX}deg) rotateY(${rotY}deg) rotateZ(${rotZ}deg)`,
              transformStyle: "preserve-3d",
            }}
          >
            {/* Exploded Z-Plane: Bottom Geometry Grid */}
            {viewPreset === "exploded" && (
              <div
                className="absolute inset-0 rounded-2xl bg-cyan-950/40 border border-cyan-500/25 p-3 flex flex-col justify-between"
                style={{ transform: "translateZ(-45px)" }}
              >
                <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-widest">
                  [LAYER 0: 3D OCR SPATIAL GEOMETRY]
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-[9px] font-mono text-cyan-300/70">
                  <div className="border border-cyan-500/20 p-1 rounded">X-COORD</div>
                  <div className="border border-cyan-500/20 p-1 rounded">Y-COORD</div>
                  <div className="border border-cyan-500/20 p-1 rounded">WIDTH</div>
                  <div className="border border-cyan-500/20 p-1 rounded">HEIGHT</div>
                </div>
              </div>
            )}

            {/* Core Document Plate */}
            <div
              className="absolute inset-0 rounded-2xl bg-slate-900/95 border border-cyan-500/35 shadow-[0_20px_50px_rgba(0,0,0,0.85),0_0_35px_rgba(6,182,212,0.25)] p-4 flex flex-col justify-between overflow-hidden backdrop-blur-2xl preserve-3d"
              style={{
                transform: "translateZ(0px)",
                transformStyle: "preserve-3d",
              }}
            >
              {/* Dynamic 3D Laser Sweep */}
              <div
                className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_20px_#06b6d4] animate-scan-sweep pointer-events-none z-20"
                style={{ transform: "translateZ(12px)" }}
              />

              {/* Real Document Mode (If Result Exists) */}
              {result ? (
                <>
                  <div className="space-y-1.5 pb-2 border-b border-white/10" style={{ transform: "translateZ(15px)" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono tracking-widest text-cyan-400 uppercase">
                        {documentType}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                          criticalFindings.length > 0
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        }`}
                      >
                        {criticalFindings.length > 0
                          ? `${criticalFindings.length} FINDING(S)`
                          : "VERIFIED PASS"}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-white truncate">
                      {vendorName || "Audited Document"}
                    </h4>
                    {invoiceNumber && (
                      <span className="text-[10px] font-mono text-slate-400 block truncate">
                        ID: {invoiceNumber}
                      </span>
                    )}
                  </div>

                  {/* Real Image Preview or Real Extracted Breakdown */}
                  {imagePreviewUrl ? (
                    <div
                      className="relative my-2 h-[170px] rounded-lg overflow-hidden border border-white/10 bg-black/60 flex items-center justify-center"
                      style={{ transform: "translateZ(20px)" }}
                    >
                      <img
                        src={imagePreviewUrl}
                        alt="Audited Document Evidence"
                        className="w-full h-full object-contain select-none"
                      />
                      {/* Bounding box glow indicator */}
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent pointer-events-none" />
                    </div>
                  ) : (
                    <div
                      className="space-y-1.5 my-2 max-h-[170px] overflow-hidden text-[11px] font-mono"
                      style={{ transform: "translateZ(20px)" }}
                    >
                      {realFlags.slice(0, 4).map((f, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-1.5 rounded bg-white/5 border border-white/5 text-slate-300"
                        >
                          <span className="truncate pr-2">{f.label}</span>
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.2 rounded shrink-0 ${
                              f.severity === "CRITICAL"
                                ? "bg-red-500/20 text-red-300"
                                : f.severity === "WARNING"
                                ? "bg-amber-500/20 text-amber-300"
                                : "bg-cyan-500/20 text-cyan-300"
                            }`}
                          >
                            {f.severity}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Real Footer Totals */}
                  <div
                    className="pt-2.5 border-t border-white/10 flex items-center justify-between"
                    style={{ transform: "translateZ(25px)" }}
                  >
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-mono block">
                        Stated Total
                      </span>
                      <span className="text-base font-extrabold text-white tracking-tight font-mono">
                        {statedTotalNum != null ? formatCurrency(statedTotalNum, currency) : "—"}
                      </span>
                    </div>
                    {realSavingsTotal != null && realSavingsTotal > 0 && (
                      <div className="text-right">
                        <span className="text-[10px] text-emerald-400 uppercase font-mono block">
                          Savings Detected
                        </span>
                        <span className="text-base font-extrabold text-emerald-400 tracking-tight font-mono">
                          {formatCurrency(realSavingsTotal, currency)}
                        </span>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                /* Engine Waiting / Scan Chamber Mode */
                <div className="flex flex-col justify-between h-full space-y-3">
                  <div className="space-y-1.5 pb-2 border-b border-white/10" style={{ transform: "translateZ(15px)" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono tracking-widest text-cyan-400 uppercase">
                        DETERMINISTIC VERIFICATION VAULT
                      </span>
                      <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        STANDBY
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-white">7-Stage Financial Pipeline</h4>
                    <p className="text-[10px] text-slate-400">
                      OCR Geometry • Python Arithmetic Reconciler • OKF Rule Engine
                    </p>
                  </div>

                  {/* 3D Stage Pipeline Badges */}
                  <div
                    className="space-y-2 py-1 text-[11px] font-mono"
                    style={{ transform: "translateZ(25px)" }}
                  >
                    <div className="flex items-center gap-2 p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-300">
                      <Binary className="w-3.5 h-3.5 shrink-0" />
                      <span className="text-[10px] font-semibold">1. Spatial Bounding Box Provenance</span>
                    </div>
                    <div className="flex items-center gap-2 p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                      <Calculator className="w-3.5 h-3.5 shrink-0" />
                      <span className="text-[10px] font-semibold">2. Exact Decimal Math Reconciliation</span>
                    </div>
                    <div className="flex items-center gap-2 p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                      <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                      <span className="text-[10px] font-semibold">3. OKF Statutory Surcharge Audit</span>
                    </div>
                  </div>

                  {/* Real Ready Status */}
                  <div
                    className="pt-2 border-t border-white/10 flex items-center justify-between text-xs"
                    style={{ transform: "translateZ(30px)" }}
                  >
                    <span className="text-slate-400 text-[11px]">Active Rules:</span>
                    <span className="font-mono text-cyan-300 font-bold text-[11px]">
                      {okfRules.length > 0 ? `${okfRules.length} Enforced Rules` : "Deterministic GAAP Rules"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* 3D Floating Real Findings Pins (Only if Real Document Results exist) */}
            {result &&
              realFlags.slice(0, 3).map((flag, idx) => {
                const zElevation = viewPreset === "exploded" ? 50 + idx * 25 : 25 + idx * 15;
                const isSelected = activeFlagIdx === idx;
                const isWarning = flag.severity === "CRITICAL" || flag.severity === "WARNING";

                return (
                  <div
                    key={flag.flag_id || idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveFlagIdx(idx);
                      if (onSelectFlag) onSelectFlag(flag);
                    }}
                    className="absolute cursor-pointer transition-all duration-200"
                    style={{
                      left: idx === 0 ? "75%" : idx === 1 ? "25%" : "68%",
                      top: idx === 0 ? "30%" : idx === 1 ? "55%" : "72%",
                      transform: `translateZ(${zElevation}px) translate(-50%, -50%)`,
                      transformStyle: "preserve-3d",
                    }}
                  >
                    <div
                      className={`px-2.5 py-1 rounded-full text-[10px] font-bold shadow-2xl flex items-center gap-1.5 border transition-all ${
                        isWarning
                          ? "bg-amber-950/90 text-amber-200 border-amber-500 shadow-amber-500/40"
                          : "bg-cyan-950/90 text-cyan-200 border-cyan-500 shadow-cyan-500/40"
                      } ${isSelected ? "ring-2 ring-white scale-110" : "hover:scale-105"}`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isWarning ? "bg-amber-400 animate-ping" : "bg-cyan-400"
                        }`}
                      />
                      <span className="truncate max-w-[120px]">{flag.label}</span>
                    </div>

                    {/* 3D Stalk Line anchoring back to plate */}
                    <div
                      className="absolute top-full left-1/2 w-0.5 bg-cyan-400/40 pointer-events-none"
                      style={{
                        height: `${zElevation}px`,
                        transform: "rotateX(90deg) translateZ(-10px)",
                        transformOrigin: "top",
                      }}
                    />
                  </div>
                );
              })}
          </div>
        </div>

        {/* Right Column: Real Telemetry & Actions */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-slate-900/90 border border-white/10 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                {result ? "Audited Item Telemetry" : "Engine Capabilities"}
              </span>
              <span className="text-[10px] font-mono text-cyan-400">
                ROT: {rotX.toFixed(0)}°X {rotY.toFixed(0)}°Y
              </span>
            </div>

            {/* Content Display based on Real State */}
            {result && activeFlag ? (
              <div className="space-y-2 pt-1">
                <div className="flex items-center gap-2">
                  {activeFlag.severity === "CRITICAL" ? (
                    <ShieldAlert className="w-5 h-5 text-red-400 shrink-0" />
                  ) : activeFlag.severity === "WARNING" ? (
                    <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  )}
                  <div>
                    <h5 className="text-sm font-bold text-white">{activeFlag.label}</h5>
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        activeFlag.severity === "CRITICAL"
                          ? "bg-red-500/20 text-red-300"
                          : activeFlag.severity === "WARNING"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-emerald-500/20 text-emerald-300"
                      }`}
                    >
                      {activeFlag.severity} Finding
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/70 p-2.5 rounded-xl border border-white/5">
                  {activeFlag.message}
                </p>
              </div>
            ) : (
              <div className="space-y-2.5 text-xs text-slate-300 leading-relaxed">
                <p className="text-slate-400 text-[11px]">
                  Before You Pay evaluates your scanned bill or quotation with strict source provenance:
                </p>
                <div className="p-2.5 rounded-xl bg-slate-950/70 border border-white/5 space-y-1.5 font-mono text-[11px]">
                  <div className="text-cyan-300">✓ Line item summation checking</div>
                  <div className="text-indigo-300">✓ Tax rate statutory reconciliation</div>
                  <div className="text-emerald-300">✓ Optional package & warranty isolation</div>
                </div>
              </div>
            )}

            {/* Arithmetic Reconciliation Status from Real Checks */}
            {result && realChecks.length > 0 && (
              <div className="pt-2 border-t border-white/10 space-y-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Reconciliation Checks
                </span>
                <div className="space-y-1">
                  {realChecks.slice(0, 2).map((chk) => (
                    <div
                      key={chk.validation_id}
                      className="flex items-center justify-between text-xs py-0.5"
                    >
                      <span className="text-slate-300 truncate pr-2 text-[11px]">
                        {chk.check_code.replace(/_/g, " ")}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.2 rounded shrink-0 ${
                          chk.status === "PASS"
                            ? "bg-emerald-500/20 text-emerald-300"
                            : "bg-amber-500/20 text-amber-300"
                        }`}
                      >
                        {chk.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Upload / Scan Action CTA */}
          <div className="p-3.5 rounded-2xl bg-gradient-to-r from-cyan-950/50 to-indigo-950/50 border border-cyan-500/30 flex items-center justify-between">
            <div>
              <div className="text-xs font-bold text-white">
                {result ? "Audit Another Document" : "Ready to Audit"}
              </div>
              <div className="text-[11px] text-slate-400">
                {result ? "Scan another quote or bill" : "Drop or snap any financial quotation"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                if (onTriggerUpload) {
                  onTriggerUpload();
                } else {
                  const el = document.getElementById("upload-dropzone-section");
                  if (el) el.scrollIntoView({ behavior: "smooth" });
                }
              }}
              className="px-3.5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shadow-lg shadow-cyan-500/30 transition transform hover:scale-105 flex items-center gap-1.5"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>{result ? "New Scan" : "Scan Document"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
