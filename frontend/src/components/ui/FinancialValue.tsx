"use client";

import React from "react";
import { formatCurrency } from "../../lib/utils";

export type FinancialValueVariant =
  | "hero"
  | "subtotal"
  | "item"
  | "deduction"
  | "discrepancy"
  | "review"
  | "muted"
  | "unknown";

interface FinancialValueProps {
  amount?: number | string | null;
  currency?: string | null;
  variant?: FinancialValueVariant;
  fallbackText?: string;
  showSign?: boolean;
  className?: string;
}

export const FinancialValue: React.FC<FinancialValueProps> = ({
  amount,
  currency = "INR",
  variant = "item",
  fallbackText = "Not stated",
  showSign = false,
  className = "",
}) => {
  const numericAmount = typeof amount === "string" ? parseFloat(amount) : amount;

  if (numericAmount == null || isNaN(numericAmount)) {
    return (
      <span className={`text-slate-400 font-sans italic text-xs ${className}`}>
        {fallbackText}
      </span>
    );
  }

  const formatted = formatCurrency(numericAmount, currency);

  const variantStyles: Record<FinancialValueVariant, string> = {
    hero: "text-2xl sm:text-3xl font-mono font-extrabold text-white tracking-tight",
    subtotal: "text-lg sm:text-xl font-mono font-bold text-slate-100",
    item: "text-sm sm:text-base font-mono font-semibold text-white",
    deduction: "text-sm sm:text-base font-mono font-semibold text-emerald-400",
    discrepancy: "text-sm sm:text-base font-mono font-bold text-amber-300",
    review: "text-sm sm:text-base font-mono font-semibold text-slate-200",
    muted: "text-xs font-mono text-slate-400",
    unknown: "text-xs font-sans italic text-slate-400",
  };

  const prefix =
    variant === "deduction"
      ? "−"
      : showSign && numericAmount > 0
      ? "+"
      : "";

  return (
    <span
      className={`tabular-nums inline-block ${variantStyles[variant]} ${className}`}
    >
      {prefix}
      {formatted}
    </span>
  );
};
