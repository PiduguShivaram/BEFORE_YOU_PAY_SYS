"use client";

import React, { useState } from "react";
import { Compass, Box, Sparkles, Layers, Sliders, Eye } from "lucide-react";

interface SpatialHUD3DProps {
  currentMode: "antigravity" | "cyber" | "minimal";
  onChangeMode: (mode: "antigravity" | "cyber" | "minimal") => void;
  showHologram: boolean;
  onToggleHologram: () => void;
}

export function SpatialHUD3D({
  currentMode,
  onChangeMode,
  showHologram,
  onToggleHologram,
}: SpatialHUD3DProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {isOpen ? (
        <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-cyan-500/30 backdrop-blur-2xl shadow-2xl shadow-cyan-950/80 w-64 space-y-3 animate-in fade-in zoom-in-95 duration-200">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-400">
              <Box className="w-3.5 h-3.5" />
              <span>3D Spatial Engine Controls</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-white text-xs px-1.5 py-0.5 rounded"
            >
              ✕
            </button>
          </div>

          {/* 3D Atmosphere Selector */}
          <div className="space-y-1.5">
            <span className="text-[10px] uppercase font-mono text-slate-400 tracking-wider">
              3D Environment
            </span>
            <div className="grid grid-cols-3 gap-1">
              <button
                onClick={() => onChangeMode("antigravity")}
                className={`py-1 px-1.5 rounded-lg text-[10px] font-semibold transition ${
                  currentMode === "antigravity"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "bg-slate-900 text-slate-400 hover:text-white"
                }`}
              >
                Antigravity
              </button>
              <button
                onClick={() => onChangeMode("cyber")}
                className={`py-1 px-1.5 rounded-lg text-[10px] font-semibold transition ${
                  currentMode === "cyber"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                    : "bg-slate-900 text-slate-400 hover:text-white"
                }`}
              >
                Cyber 3D
              </button>
              <button
                onClick={() => onChangeMode("minimal")}
                className={`py-1 px-1.5 rounded-lg text-[10px] font-semibold transition ${
                  currentMode === "minimal"
                    ? "bg-slate-700 text-slate-200 border border-white/20"
                    : "bg-slate-900 text-slate-400 hover:text-white"
                }`}
              >
                Minimal
              </button>
            </div>
          </div>

          {/* Hologram Stage Toggle */}
          <div className="pt-2 border-t border-white/10 flex items-center justify-between">
            <span className="text-xs text-slate-300">3D Hologram Stage</span>
            <button
              onClick={onToggleHologram}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                showHologram
                  ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/30"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {showHologram ? "Visible" : "Hidden"}
            </button>
          </div>

          <div className="text-[10px] text-slate-500 font-mono text-center pt-1">
            GPU-Accelerated 3D Perspective
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="group flex items-center gap-2 px-3.5 py-2 rounded-full bg-slate-900/90 border border-cyan-500/40 backdrop-blur-xl shadow-xl shadow-cyan-950/60 hover:border-cyan-400 text-slate-200 transition-all hover:scale-105"
        >
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <Box className="w-4 h-4 text-cyan-400 group-hover:rotate-12 transition-transform" />
          <span className="text-xs font-bold tracking-wide">3D View</span>
        </button>
      )}
    </div>
  );
}
