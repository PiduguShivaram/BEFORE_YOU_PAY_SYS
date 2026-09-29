"use client";

import React, { useState } from "react";
import {
  Calculator,
  CheckCircle2,
  XCircle,
  MinusCircle,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  FileCode2,
  ExternalLink,
} from "lucide-react";
import { ValidationCheck } from "../lib/types";
import { formatCurrency, formatDifference } from "../lib/utils";

interface MathVerificationProps {
  checks: ValidationCheck[];
  currency?: string | null;
  isQuotation?: boolean;
  quotedTotal?: number | null;
  subtotal?: number | null;
  discountTotal?: number | null;
  onSelectFieldId?: (fieldId: string) => void;
}

interface CheckPresentation {
  title: string;
  simpleExplanation: string;
  expectedLabel: string;
  calculatedLabel: string;
}

function getCheckPresentation(
  check: ValidationCheck,
  isQuotation?: boolean,
  currency?: string | null
): CheckPresentation {
  const safeCurrency = currency || "INR";
  const delta = check.absolute_delta ?? 0;
  const hasDelta = check.status === "FAIL" || delta > 0.02;
  const diffStr = formatDifference(delta, safeCurrency);

  switch (check.check_code) {
    case "QUOTATION_SUBTOTAL_CONSISTENCY":
      return {
        title: hasDelta
          ? `Component Reconciliation — ${diffStr} discrepancy`
          : "Component Reconciliation — Exact Match",
        simpleExplanation: hasDelta
          ? `Listed charges sum to ${formatCheckValue(check.calculated_value, safeCurrency)} vs stated subtotal ${formatCheckValue(check.expected_value, safeCurrency)} (${diffStr} difference). Ask the dealer to clarify.`
          : "All individual vehicle charges add up to the stated subtotal before offers.",
        expectedLabel: "Stated subtotal",
        calculatedLabel: "Sum of charges",
      };
    case "QUOTATION_NET_TOTAL_CONSISTENCY":
      return {
        title: hasDelta
          ? `Quoted Total Reconciliation — ${diffStr} discrepancy`
          : "Quoted Total Reconciliation — Exact Match",
        simpleExplanation: hasDelta
          ? `Stated subtotal minus offers differs from quoted total by ${diffStr}. Requires verification.`
          : "Subtotal minus all applied discounts and dealer offers equals the final quoted total.",
        expectedLabel: "Quoted total",
        calculatedLabel: "Subtotal − Offers",
      };
    case "ARITHMETIC_LINE_ITEMS_SUM":
      if (isQuotation) {
        return {
          title: hasDelta
            ? `Cost components reconciled — ${diffStr} discrepancy`
            : "Cost components reconciled — Exact Match",
          simpleExplanation: hasDelta
            ? `Constituent charges differ from the stated subtotal by ${diffStr}. Requires verification.`
            : "All component charges and discounts align with the quotation breakdown.",
          expectedLabel: "Stated subtotal",
          calculatedLabel: "Sum of components",
        };
      }
      return {
        title: "Line items add up",
        simpleExplanation: "Sum of itemized lines matches the document subtotal.",
        expectedLabel: "Stated subtotal",
        calculatedLabel: "Sum of line items",
      };
    case "ARITHMETIC_TOTAL_CONSISTENCY":
      return {
        title: isQuotation
          ? (hasDelta ? `Quoted Total Reconciliation — ${diffStr} discrepancy` : "Quoted Total Reconciliation — Exact Match")
          : "Total reconciles",
        simpleExplanation: isQuotation
          ? "The final quoted on-road price matches the subtotal after deducting all offers."
          : "The invoice total matches the sum of subtotal, statutory taxes, and fees.",
        expectedLabel: isQuotation ? "Quoted total" : "Stated total",
        calculatedLabel: "Calculated total",
      };
    case "LINE_ITEM_EXTENSION_MATCH":
      return {
        title: "Quantity × rate matches total",
        simpleExplanation: "Quantity multiplied by unit rate matches the stated extended total.",
        expectedLabel: "Stated item total",
        calculatedLabel: "Quantity × Unit price",
      };
    case "PAYMENT_STATUS_RECONCILIATION":
      return {
        title: "Payment balance reconciles",
        simpleExplanation: "Amount paid and remaining balance due accurately reconcile with the total.",
        expectedLabel: "Stated balance due",
        calculatedLabel: "Total minus amount paid",
      };
    case "ARITHMETIC_TAX_MATCH":
      return {
        title: "Effective tax rate",
        simpleExplanation:
          check.calculated_value === "0.0%" || check.calculated_value === "0%"
            ? `Stated tax is ${formatCurrency(0, safeCurrency)} (effective tax rate 0.0%).`
            : (check.message || "Effective tax rate evaluated against stated subtotal."),
        expectedLabel: "Statutory benchmark",
        calculatedLabel: "Effective tax rate",
      };
    case "DATE_SEQUENCE_CHECK":
      if (check.status === "INCONCLUSIVE") {
        return {
          title: "Dates not stated",
          simpleExplanation: "This document does not specify an explicit issue date or payment due date, so chronological sequence could not be evaluated.",
          expectedLabel: "Due date",
          calculatedLabel: "Issue date",
        };
      }
      if (check.status === "FAIL") {
        return {
          title: "Invalid date sequence",
          simpleExplanation: "The stated due date precedes the document issue date.",
          expectedLabel: "Expected after",
          calculatedLabel: "Stated due date",
        };
      }
      return {
        title: "Document dates in valid sequence",
        simpleExplanation: "Due date is chronologically on or after the document issue date.",
        expectedLabel: "Due date",
        calculatedLabel: "Issue date",
      };
    case "FINANCIAL_CONTENT_VERIFICATION":
      return {
        title: "Financial figures identified",
        simpleExplanation: "Verifiable monetary amounts and commercial commitments detected.",
        expectedLabel: "Commitments",
        calculatedLabel: "Total recognized",
      };
    default:
      return {
        title: check.check_code
          .replace(/_/g, " ")
          .toLowerCase()
          .replace(/^\w/, (c) => c.toUpperCase()),
        simpleExplanation: check.message,
        expectedLabel: "Expected value",
        calculatedLabel: "Calculated value",
      };
  }
}

function formatCheckValue(val: string | number | null | undefined, currency?: string | null): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "number") return formatCurrency(val, currency);
  const num = parseFloat(val);
  if (!isNaN(num) && /^-?\d+(\.\d+)?$/.test(val.trim())) {
    return formatCurrency(num, currency);
  }
  return String(val);
}



export const MathVerification: React.FC<MathVerificationProps> = ({
  checks,
  currency = "INR",
  isQuotation = false,
  quotedTotal,
  subtotal,
  discountTotal,
  onSelectFieldId,
}) => {
  const [expandedCheckId, setExpandedCheckId] = useState<string | null>(null);
  const allPass = checks.length > 0 && checks.every((c) => c.status === "PASS");
  const hasFail = checks.some((c) => c.status === "FAIL");
  const [isSectionOpen, setIsSectionOpen] = useState<boolean>(hasFail);

  const toggleExpand = (id: string) => {
    setExpandedCheckId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="surface-card rounded-2xl p-4 sm:p-6 shadow-card mb-6 border border-white/10 space-y-4">
      {/* Header with Accordion Toggle */}
      <button
        type="button"
        onClick={() => setIsSectionOpen(!isSectionOpen)}
        className="w-full flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3 border-b border-white/10 text-left cursor-pointer hover:opacity-90 transition rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        aria-expanded={isSectionOpen}
      >
        <div className="flex items-center gap-2.5">
          <Calculator className="w-5 h-5 text-brand-400 shrink-0" />
          <div>
            <h3 className="font-bold text-sm sm:text-base text-white flex items-center gap-2">
              <span>Technical Verification Details</span>
              <span className="text-[11px] font-mono text-slate-400 font-normal">
                ({checks.length} code checks)
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic formula proofs and tolerance checks executed on extracted values
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-center">
          {hasFail ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
              <AlertCircle className="w-3.5 h-3.5" />
              Discrepancy Detected
            </span>
          ) : allPass ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-3.5 h-3.5" />
              All Calculations Match (100% Pass)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <AlertCircle className="w-3.5 h-3.5" />
              Verification Needed
            </span>
          )}

          <span className="text-slate-400 hover:text-white p-1">
            {isSectionOpen ? (
              <ChevronDown className="w-4 h-4 text-slate-400 rotate-180 transition-transform" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400 transition-transform" />
            )}
          </span>
        </div>
      </button>

      {/* Verification Checks List (Collapsible) */}
      {isSectionOpen && (
        <div className="flex flex-col gap-2.5 animate-in fade-in duration-200">
        {checks.map((check) => {
          const isPass = check.status === "PASS";
          const isFail = check.status === "FAIL";
          const isInconclusive = check.status === "INCONCLUSIVE";
          const isExpanded = expandedCheckId === check.validation_id;
          const presentation = getCheckPresentation(check, isQuotation, currency);

          const isTaxCheck = check.check_code === "ARITHMETIC_TAX_MATCH";
          const hasExpectedValue = check.expected_value !== null || (isTaxCheck && isPass);
          const displayExpected = isTaxCheck && check.expected_value === null
            ? "≤ 35.0%"
            : formatCheckValue(check.expected_value, currency);

          const expectedFormatted = displayExpected;
          const calculatedFormatted = formatCheckValue(check.calculated_value, currency);
          const differenceFormatted = formatDifference(check.absolute_delta, currency);
          const isZeroDelta =
            check.absolute_delta === 0 ||
            (check.absolute_delta !== null && Math.abs(check.absolute_delta) < 0.01);

          return (
            <div
              key={check.validation_id}
              className={`p-3.5 sm:p-4 rounded-xl border transition ${
                isFail
                  ? "bg-rose-500/10 border-rose-500/30"
                  : isPass
                  ? "bg-slate-900/40 border-white/5"
                  : "bg-white/2 border-white/5 opacity-80"
              }`}
            >
              {/* Primary User-Facing Row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                {/* Left: Icon, Title, and Concise Explanation */}
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5 shrink-0">
                    {isPass ? (
                      <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
                    ) : isFail ? (
                      <XCircle className="w-4 h-4 sm:w-5 sm:h-5 text-rose-400" />
                    ) : (
                      <MinusCircle className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs sm:text-sm font-bold text-white tracking-tight">
                        {presentation.title}
                      </h4>
                      <span
                        className={`text-[9px] font-mono font-extrabold px-1.5 py-0.2 rounded uppercase ${
                          isPass
                            ? "bg-emerald-500/20 text-emerald-400"
                            : isFail
                            ? "bg-rose-500/20 text-rose-400"
                            : "bg-amber-500/20 text-amber-300"
                        }`}
                      >
                        {isPass ? "PASS" : check.status}
                      </span>
                    </div>
                    <p className="text-[11px] sm:text-xs text-slate-300 mt-0.5 leading-relaxed">
                      {presentation.simpleExplanation}
                    </p>
                  </div>
                </div>

                {/* Right: Numbers and Status Pill (Mobile-Friendly Stack) */}
                <div className="shrink-0 flex items-center justify-between sm:justify-end gap-2.5 pl-7 sm:pl-0 pt-1.5 sm:pt-0 border-t sm:border-t-0 border-white/5">
                  {(hasExpectedValue || check.calculated_value !== null) ? (
                    <div className="flex items-center gap-2.5 text-xs font-mono">
                      {check.calculated_value !== null && (
                        <div className="text-left sm:text-right">
                          <span className="text-[9px] text-slate-400 block uppercase font-sans">
                            {presentation.calculatedLabel}
                          </span>
                          <span className="font-semibold text-slate-100">
                            {calculatedFormatted}
                          </span>
                        </div>
                      )}

                      {check.absolute_delta !== null && (
                        <div className="text-left sm:text-right">
                          <span className="text-[9px] text-slate-400 block uppercase font-sans">
                            Diff
                          </span>
                          <span
                            className={`font-semibold ${
                              isZeroDelta ? "text-emerald-400" : "text-rose-400 font-bold"
                            }`}
                          >
                            {differenceFormatted}
                          </span>
                        </div>
                      )}

                      <div>
                        {isPass && (isZeroDelta || check.absolute_delta === null) ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            ✓ Matches
                          </span>
                        ) : isFail ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                            ⚠️ Mismatch
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-300">
                            Verified
                          </span>
                        )}
                      </div>
                    </div>
                  ) : isInconclusive ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-white/5 text-slate-400 border border-white/10">
                      <MinusCircle className="w-3 h-3 text-amber-400" />
                      Not stated on slip
                    </span>
                  ) : null}
                </div>
              </div>

              {/* Expandable Technical Evidence Drawer (Touch Target >= 44px) */}
              <div className="mt-2.5 pt-2 border-t border-white/5">
                <button
                  type="button"
                  onClick={() => toggleExpand(check.validation_id)}
                  className="w-full min-h-[44px] flex items-center justify-between text-xs text-brand-400 hover:text-brand-300 font-medium transition cursor-pointer select-none active:scale-98"
                  aria-expanded={isExpanded}
                >
                  <span className="flex items-center gap-1.5 font-bold tracking-tight">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-brand-400 shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-brand-400 shrink-0" />
                    )}
                    <span>HOW WE VERIFIED THIS</span>
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    {isExpanded ? "Hide Details" : "View Formula & Provenance"}
                  </span>
                </button>

                {isExpanded && (
                  <div className="mt-2 p-3 rounded-xl bg-slate-950/90 border border-white/10 space-y-2 text-xs animate-in fade-in duration-200">
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1.5">
                        <FileCode2 className="w-3.5 h-3.5 text-slate-400" />
                        <span className="text-[10px] uppercase font-bold text-slate-400">
                          Check Code:
                        </span>
                        <code className="text-[11px] font-mono font-bold text-brand-300 bg-brand-500/10 px-1.5 py-0.5 rounded border border-brand-500/20">
                          {check.check_code}
                        </code>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500 truncate max-w-[140px]">
                        ID: {check.validation_id.slice(0, 8)}...
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">
                        Formula & Verification Logic:
                      </span>
                      <p className="font-mono text-[11px] text-slate-300 leading-relaxed bg-white/5 p-2 rounded-lg border border-white/5 break-words">
                        {check.message}
                      </p>
                    </div>

                    <div className="grid grid-cols-3 gap-1.5 font-mono text-[11px]">
                      <div className="p-1.5 rounded bg-white/5">
                        <span className="text-[9px] text-slate-400 block font-sans uppercase">
                          Expected
                        </span>
                        <span className="text-slate-200 font-semibold truncate block">
                          {String(check.expected_value ?? "—")}
                        </span>
                      </div>
                      <div className="p-1.5 rounded bg-white/5">
                        <span className="text-[9px] text-slate-400 block font-sans uppercase">
                          Computed
                        </span>
                        <span className="text-slate-200 font-semibold truncate block">
                          {String(check.calculated_value ?? "—")}
                        </span>
                      </div>
                      <div className="p-1.5 rounded bg-white/5">
                        <span className="text-[9px] text-slate-400 block font-sans uppercase">
                          Δ Delta
                        </span>
                        <span
                          className={`font-semibold truncate block ${
                            check.absolute_delta !== null && check.absolute_delta > 0.02
                              ? "text-rose-400 font-bold"
                              : "text-emerald-400"
                          }`}
                        >
                          {check.absolute_delta !== null ? check.absolute_delta.toFixed(4) : "0.00"}
                        </span>
                      </div>
                    </div>

                    {check.input_field_ids && check.input_field_ids.length > 0 && (
                      <div className="pt-1">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                          Source Field References ({check.input_field_ids.length}):
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {check.input_field_ids.map((fieldId) => (
                            <button
                              key={fieldId}
                              type="button"
                              onClick={() => onSelectFieldId && onSelectFieldId(fieldId)}
                              className="text-[10px] font-mono px-2 py-1 rounded bg-slate-800 hover:bg-brand-500/20 text-slate-300 hover:text-brand-200 border border-white/10 transition cursor-pointer flex items-center gap-1 active:scale-95"
                              title="Highlight on document canvas"
                            >
                              <span>{fieldId}</span>
                              <ExternalLink className="w-2.5 h-2.5 text-brand-400" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        </div>
      )}
    </div>
  );
};
