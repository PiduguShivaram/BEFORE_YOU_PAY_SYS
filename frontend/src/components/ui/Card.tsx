"use client";

import React from "react";

export type CardVariant =
  | "primary"
  | "secondary"
  | "inset"
  | "verification"
  | "pass";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({
  variant = "primary",
  children,
  className = "",
  ...props
}) => {
  const variantStyles: Record<CardVariant, string> = {
    primary:
      "rounded-2xl border border-white/10 bg-app-card p-4 sm:p-6 shadow-card",
    secondary:
      "rounded-xl border border-white/6 bg-app-cardSubtle p-3.5 sm:p-4",
    inset:
      "rounded-xl border border-white/4 bg-app-cardInset p-3 sm:p-3.5",
    verification:
      "rounded-xl border border-amber-500/30 bg-amber-950/20 p-3.5 sm:p-4",
    pass:
      "rounded-xl border border-emerald-500/25 bg-emerald-950/20 p-3.5 sm:p-4",
  };

  return (
    <div
      className={`transition-colors ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
