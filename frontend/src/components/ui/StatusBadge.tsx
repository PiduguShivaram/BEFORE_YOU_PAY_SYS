"use client";

import React from "react";
import {
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Info,
  AlertTriangle,
} from "lucide-react";

export type StatusVariant =
  | "PASS"
  | "REQUIRES_VERIFICATION"
  | "INCONCLUSIVE"
  | "INFORMATION"
  | "ERROR";

interface StatusBadgeProps {
  status: StatusVariant | string;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = "sm",
  className = "",
}) => {
  const normalized = (status || "").toUpperCase().replace(/\s+/g, "_");

  let variant: StatusVariant = "INFORMATION";
  if (normalized === "PASS" || normalized === "CLEAR" || normalized === "VALID") {
    variant = "PASS";
  } else if (
    normalized === "REQUIRES_VERIFICATION" ||
    normalized === "REQUIRES_ATTENTION" ||
    normalized === "WARNING"
  ) {
    variant = "REQUIRES_VERIFICATION";
  } else if (normalized === "INCONCLUSIVE" || normalized === "UNVERIFIED") {
    variant = "INCONCLUSIVE";
  } else if (normalized === "ERROR" || normalized === "FAIL" || normalized === "CRITICAL") {
    variant = "ERROR";
  } else {
    variant = "INFORMATION";
  }

  const configs: Record<
    StatusVariant,
    { text: string; icon: React.ReactNode; styles: string }
  > = {
    PASS: {
      text: label || "PASS",
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />,
      styles: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    },
    REQUIRES_VERIFICATION: {
      text: label || "REQUIRES VERIFICATION",
      icon: <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" aria-hidden="true" />,
      styles: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    },
    INCONCLUSIVE: {
      text: label || "INCONCLUSIVE",
      icon: <HelpCircle className="w-3.5 h-3.5 text-blue-400 shrink-0" aria-hidden="true" />,
      styles: "bg-blue-500/10 text-blue-400 border-blue-500/25",
    },
    INFORMATION: {
      text: label || "INFORMATION",
      icon: <Info className="w-3.5 h-3.5 text-slate-400 shrink-0" aria-hidden="true" />,
      styles: "bg-slate-800/80 text-slate-300 border-slate-700/50",
    },
    ERROR: {
      text: label || "ERROR",
      icon: <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" aria-hidden="true" />,
      styles: "bg-rose-500/10 text-rose-400 border-rose-500/25",
    },
  };

  const current = configs[variant];
  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-1 text-[11px]"
      : "px-3 py-1.5 text-xs font-bold";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-mono font-bold border tracking-wide uppercase transition-colors shrink-0 ${sizeClasses} ${current.styles} ${className}`}
      role="status"
    >
      {current.icon}
      <span>{current.text}</span>
    </span>
  );
};
