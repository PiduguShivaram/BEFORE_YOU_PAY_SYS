"use client";

import React from "react";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "chip";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isActive?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  size = "md",
  isActive = false,
  children,
  className = "",
  disabled,
  ...props
}) => {
  const baseStyles =
    "inline-flex items-center justify-center gap-2 font-sans font-medium transition-all select-none disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#070b14] focus-visible:outline-none";

  const sizeStyles: Record<ButtonSize, string> = {
    sm: "px-2.5 py-1.5 text-xs min-h-[36px] rounded-lg",
    md: "px-4 py-2.5 text-xs sm:text-sm min-h-[44px] rounded-xl",
    lg: "px-5 py-3 text-sm sm:text-base min-h-[48px] rounded-xl font-semibold",
  };

  const variantStyles: Record<ButtonVariant, string> = {
    primary:
      "bg-brand-600 hover:bg-brand-500 active:bg-brand-700 text-white font-semibold shadow-sm",
    secondary:
      "bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-slate-200 border border-slate-700/60",
    outline:
      "bg-transparent border border-white/10 hover:border-white/20 text-slate-300 hover:text-white hover:bg-white/5",
    ghost:
      "bg-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 active:bg-slate-800",
    chip: isActive
      ? "bg-brand-600 text-white border border-brand-500 shadow-sm"
      : "bg-slate-900/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-white/5",
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
