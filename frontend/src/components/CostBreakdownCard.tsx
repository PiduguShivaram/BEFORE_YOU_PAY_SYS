"use client";

import React, { useState } from "react";
import {
  Car,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  ExternalLink,
  Layers,
  HelpCircle,
  Copy,
  Check,
  Calculator,
  ShieldCheck,
} from "lucide-react";
import {
  FinancialComponent,
  SmartCostReductionQuestion,
  ValidationCheck,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface CostBreakdownCardProps {
  components: FinancialComponent[];
  currency?: string | null;
  subtotal?: number | null;
  discountTotal?: number | null;
  quotedTotal: number;
  validationChecks: ValidationCheck[];
  selectedComponentId?: string | null;
  onSelectComponent?: (comp: FinancialComponent) => void;
  smartQuestions?: SmartCostReductionQuestion[];
}

export const CostBreakdownCard: React.FC<CostBreakdownCardProps> = ({
  components,
  currency = "INR",
  subtotal: propSubtotal,
  discountTotal: propDiscountTotal,
  quotedTotal,
  validationChecks,
  selectedComponentId,
  onSelectComponent,
  smartQuestions,
}) => {
  const [copiedQuestionIdx, setCopiedQuestionIdx] = useState<number | null>(null);

  const getAmount = (comp: FinancialComponent): number => {
    return Number(comp.amount?.normalized_value || 0);
  };

  // Separate constituent charges from deductions and aggregate components
  const chargeItems: FinancialComponent[] = [];
  const discountItems: FinancialComponent[] = [];
  let foundSubtotalComp: FinancialComponent | null = null;

  components.forEach((c) => {
    const cat = (c.category || "").toLowerCase();
    const nature = (c.charge_nature || "").toLowerCase();
    const name = (c.normalized_name || c.name || "").toLowerCase();

    // Deductions / Offers
    if (
      nature === "deduction" ||
      cat === "offer" ||
      cat === "discount" ||
      name.includes("offer") ||
      name.includes("discount") ||
      name.includes("rebate") ||
      name.includes("concession")
    ) {
      discountItems.push(c);
      return;
    }

    // Subtotal aggregate component
    if (cat === "subtotal" || cat === "base_subtotal" || name === "subtotal" || name === "stated subtotal") {
      foundSubtotalComp = c;
      return;
    }

    // Skip total or balance due aggregate components from line charges
    if (cat === "total" || cat === "amount_paid" || cat === "balance_due") {
      return;
    }

    // Constituent charges (What you are paying for)
    chargeItems.push(c);
  });

  // Calculate Listed Component Total
  const listedComponentTotal = chargeItems.reduce((acc, c) => acc + getAmount(c), 0);

  // Determine Stated Subtotal (from props, from document subtotal component, or fallback)
  const statedSubtotal =
    propSubtotal != null
      ? propSubtotal
      : foundSubtotalComp
      ? getAmount(foundSubtotalComp)
      : null;

  // Determine Total Discounts
  const discountsSum =
    propDiscountTotal != null && propDiscountTotal > 0
      ? propDiscountTotal
      : discountItems.reduce((acc, c) => acc + getAmount(c), 0);

  // ── 1. Component Reconciliation (Listed components vs Stated subtotal) ──
  const subtotalCheck = validationChecks.find(
    (c) => c.check_code === "QUOTATION_SUBTOTAL_CONSISTENCY"
  );
  const componentDelta =
    subtotalCheck?.absolute_delta != null
      ? subtotalCheck.absolute_delta
      : statedSubtotal != null
      ? Math.round(Math.abs(listedComponentTotal - statedSubtotal) * 100) / 100
      : 0;

  // Component reconciliation PASS only when difference <= 0.02
  const isComponentReconciliationPass =
    subtotalCheck != null
      ? subtotalCheck.status === "PASS"
      : statedSubtotal != null
      ? componentDelta <= 0.02
      : true;

  // ── 2. Quoted-Total Reconciliation (Subtotal - discounts + additions vs final quoted total) ──
  const netTotalCheck = validationChecks.find(
    (c) =>
      c.check_code === "QUOTATION_NET_TOTAL_CONSISTENCY" ||
      c.check_code === "ARITHMETIC_TOTAL_CONSISTENCY"
  );
  const baseForNet = statedSubtotal != null ? statedSubtotal : listedComponentTotal;
  const calculatedNetTotal = Math.round((baseForNet - discountsSum) * 100) / 100;
  const quotedTotalDelta =
    netTotalCheck?.absolute_delta != null
      ? netTotalCheck.absolute_delta
      : Math.round(Math.abs(calculatedNetTotal - quotedTotal) * 100) / 100;

  const isQuotedTotalReconciliationPass =
    netTotalCheck != null
      ? netTotalCheck.status === "PASS"
      : quotedTotalDelta <= 0.02;

  // Derive questions from smart_questions or defaults
  const paymentQuestions: string[] = [];
  if (smartQuestions && smartQuestions.length > 0) {
    smartQuestions.slice(0, 5).forEach((q) => {
      if (!paymentQuestions.includes(q.question)) {
        paymentQuestions.push(q.question);
      }
    });
  }

  // Fallbacks if smart_questions not provided
  if (paymentQuestions.length === 0) {
    paymentQuestions.push(
      "Is the extended warranty package optional?",
      "Are these accessories required for vehicle delivery?",
      "Can I choose my own insurer or insurance policy?",
      "What service does the dealer handling charge cover, and is it mandatory?",
      "Does the offer already appear in the final quoted total?"
    );
  }

  const handleCopyQuestion = (idx: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedQuestionIdx(idx);
    setTimeout(() => setCopiedQuestionIdx(null), 2000);
  };

  const getStatusBadge = (comp: FinancialComponent) => {
    const status = comp.charge_status_display || (comp.charge_status ? String(comp.charge_status) : null);
    if (status) return status;

    const opt = (comp.optionality_status || "").toLowerCase();
    const cat = (comp.category || "").toLowerCase();

    if (opt === "confirmed_mandatory" || cat === "tcs" || cat === "gst" || cat === "tax") {
      return "Mandatory by law";
    }
    if (cat === "ex_showroom_price" || cat === "base_price") {
      return "Required by seller/contract";
    }
    if (
      opt === "potentially_optional" ||
      opt === "confirmed_optional" ||
      cat === "extended_warranty" ||
      cat === "accessory" ||
      cat === "accessory_package"
    ) {
      return "Potentially optional";
    }
    if (cat === "handling_fee" || cat === "logistics_fee") {
      return "Potentially negotiable";
    }
    return null;
  };

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-6 border border-white/10 shadow-2xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
              <Car className="w-3.5 h-3.5" />
              FINANCIAL BREAKDOWN
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Vehicle Quotation
            </span>
          </div>
          <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Cost Breakdown & Reconciliation
          </h2>
          <p className="text-xs text-slate-400">
            Clear separation of listed charges, stated totals, and independent reconciliation checks.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-2">
          {!isComponentReconciliationPass ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              Component Discrepancy
            </span>
          ) : isQuotedTotalReconciliationPass ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Reconciled
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              Verify Total
            </span>
          )}
        </div>
      </div>

      {/* ── 1. WHAT YOU ARE PAYING FOR ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand-400" />
            WHAT YOU ARE PAYING FOR
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            {chargeItems.length} charge component{chargeItems.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 divide-y divide-white/5">
          {chargeItems.map((comp) => {
            const amt = getAmount(comp);
            const isSelected = selectedComponentId === comp.component_id;
            const badge = getStatusBadge(comp);
            const label = comp.normalized_label || comp.normalized_name || comp.name;

            return (
              <div
                key={comp.component_id}
                onClick={() => onSelectComponent && onSelectComponent(comp)}
                className={`p-3.5 sm:px-4 cursor-pointer transition select-none ${
                  isSelected
                    ? "bg-brand-500/20 border-l-4 border-l-brand-400"
                    : "hover:bg-white/5 border-l-4 border-l-transparent"
                }`}
                role="button"
                tabIndex={0}
                aria-label={`Inspect ${label}`}
              >
                <div className="flex items-center justify-between min-h-[36px]">
                  <div className="min-w-0 pr-3">
                    <span className="text-xs sm:text-sm font-semibold text-slate-100 block truncate">
                      {label}
                    </span>
                    {badge && (
                      <span className="inline-block mt-1 text-[10px] font-mono px-2 py-0.5 rounded border bg-slate-800/80 text-slate-300 border-white/10">
                        {badge}
                      </span>
                    )}
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-sm sm:text-base font-mono font-bold text-white block">
                      {formatCurrency(amt, currency)}
                    </span>
                    <span className="text-[10px] text-brand-400 font-sans flex items-center justify-end gap-1">
                      <span>Inspect</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </span>
                  </div>
                </div>

                {/* Expanded Details when row is selected */}
                {isSelected && (comp.document_states || comp.system_knows || comp.requires_confirmation) && (
                  <div className="mt-2.5 pt-2.5 border-t border-white/10 grid grid-cols-1 gap-1.5 text-xs">
                    {comp.document_states && (
                      <div className="bg-slate-950/70 rounded-lg p-2 border border-white/5">
                        <span className="font-bold text-slate-400 uppercase tracking-wider text-[10px] block">
                          Document states
                        </span>
                        <p className="text-slate-200">{comp.document_states}</p>
                      </div>
                    )}
                    {comp.system_knows && (
                      <div className="bg-slate-950/70 rounded-lg p-2 border border-white/5">
                        <span className="font-bold text-blue-400 uppercase tracking-wider text-[10px] block">
                          System knows
                        </span>
                        <p className="text-slate-200">{comp.system_knows}</p>
                      </div>
                    )}
                    {comp.requires_confirmation && (
                      <div className="bg-amber-950/40 rounded-lg p-2 border border-amber-500/20">
                        <span className="font-bold text-amber-300 uppercase tracking-wider text-[10px] block">
                          Requires confirmation
                        </span>
                        <p className="text-amber-200">{comp.requires_confirmation}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── 2. SEPARATELY SHOWN TOTALS & DEDUCTIONS ── */}
      <div className="space-y-3 pt-2">
        <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Calculator className="w-4 h-4 text-indigo-400" />
          TOTALS & DEDUCTIONS
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* LISTED COMPONENT TOTAL */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-white/10 flex flex-col justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
              LISTED COMPONENT TOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-lg sm:text-xl font-mono font-bold text-white">
                {formatCurrency(listedComponentTotal, currency)}
              </span>
              <span className="text-[10px] text-slate-400 font-sans">
                Sum of {chargeItems.length} charges
              </span>
            </div>
          </div>

          {/* STATED SUBTOTAL */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-white/10 flex flex-col justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
              STATED SUBTOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-lg sm:text-xl font-mono font-bold text-white">
                {statedSubtotal != null
                  ? formatCurrency(statedSubtotal, currency)
                  : "Not stated"}
              </span>
              <span className="text-[10px] text-slate-400 font-sans">
                On quotation
              </span>
            </div>
          </div>

          {/* OFFERS / DISCOUNTS */}
          <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20 flex flex-col justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <TrendingDown className="w-3 h-3 text-emerald-400" />
              OFFERS / DISCOUNTS
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-lg sm:text-xl font-mono font-bold text-emerald-400">
                {discountsSum > 0 ? `−${formatCurrency(discountsSum, currency)}` : "₹0"}
              </span>
              <span className="text-[10px] text-emerald-400/80 font-sans">
                {discountItems.length} offer{discountItems.length !== 1 ? "s" : ""} applied
              </span>
            </div>
          </div>

          {/* FINAL QUOTED TOTAL */}
          <div className="p-3.5 rounded-xl bg-gradient-to-r from-indigo-950/40 via-slate-900 to-indigo-950/40 border-2 border-indigo-500/40 flex flex-col justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-indigo-300">
              FINAL QUOTED TOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl sm:text-2xl font-mono font-extrabold text-white">
                {formatCurrency(quotedTotal, currency)}
              </span>
              <span className="text-[10px] text-indigo-300 font-sans">
                Final payable amount
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. RECONCILIATION CHECKS (SEPARATE & UNMERGED) ── */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            RECONCILIATION CHECKS
          </h3>
          <span className="text-[11px] text-slate-400 font-sans">
            Independent mathematical verifications
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {/* Check 1: Component Reconciliation */}
          <div
            className={`p-4 rounded-xl border transition ${
              isComponentReconciliationPass
                ? "bg-slate-900/60 border-emerald-500/30"
                : "bg-amber-950/20 border-amber-500/40"
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-white">
                  1. Component Reconciliation
                </h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Listed components vs stated subtotal
                </p>
              </div>

              {isComponentReconciliationPass ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  PASS
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                  REQUIRES VERIFICATION
                </span>
              )}
            </div>

            <div className="space-y-1.5 pt-2 border-t border-white/5 text-xs font-mono">
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-400 font-sans">Listed components sum:</span>
                <span>{formatCurrency(listedComponentTotal, currency)}</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-400 font-sans">Stated subtotal:</span>
                <span>
                  {statedSubtotal != null ? formatCurrency(statedSubtotal, currency) : "Not stated"}
                </span>
              </div>
              {!isComponentReconciliationPass && componentDelta > 0 && (
                <div className="flex justify-between text-amber-300 font-bold pt-1 border-t border-amber-500/20">
                  <span className="font-sans">Component discrepancy:</span>
                  <span>{formatCurrency(componentDelta, currency)}</span>
                </div>
              )}
            </div>

            <p className="text-[11px] text-slate-300 mt-2.5 leading-snug">
              {isComponentReconciliationPass
                ? "The listed financial components mathematically equal the stated subtotal."
                : `A discrepancy of ${formatCurrency(
                    componentDelta,
                    currency
                  )} exists between the listed components and stated subtotal. Ask the dealer to clarify which figure is correct.`}
            </p>
          </div>

          {/* Check 2: Quoted-Total Reconciliation */}
          <div
            className={`p-4 rounded-xl border transition ${
              isQuotedTotalReconciliationPass
                ? "bg-slate-900/60 border-emerald-500/30"
                : "bg-amber-950/20 border-amber-500/40"
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-white">
                  2. Quoted-Total Reconciliation
                </h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Subtotal − discounts + additions vs final quoted total
                </p>
              </div>

              {isQuotedTotalReconciliationPass ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  PASS
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                  REQUIRES VERIFICATION
                </span>
              )}
            </div>

            <div className="space-y-1.5 pt-2 border-t border-white/5 text-xs font-mono">
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-400 font-sans">Base subtotal:</span>
                <span>{formatCurrency(baseForNet, currency)}</span>
              </div>
              <div className="flex justify-between text-emerald-400">
                <span className="text-slate-400 font-sans">Offers / deductions:</span>
                <span>−{formatCurrency(discountsSum, currency)}</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-400 font-sans">Calculated net total:</span>
                <span>{formatCurrency(calculatedNetTotal, currency)}</span>
              </div>
              <div className="flex justify-between text-white font-bold pt-1 border-t border-white/10">
                <span className="text-slate-400 font-sans">Final quoted total:</span>
                <span>{formatCurrency(quotedTotal, currency)}</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-300 mt-2.5 leading-snug">
              {isQuotedTotalReconciliationPass
                ? "The final quoted total reconciles exactly with stated subtotal minus applicable discounts."
                : `A discrepancy of ${formatCurrency(
                    quotedTotalDelta,
                    currency
                  )} exists between the calculated net amount and final quoted total.`}
            </p>
          </div>
        </div>
      </div>

      {/* ── 4. PAYMENT QUESTIONS ── */}
      {paymentQuestions.length > 0 && (
        <div className="pt-2 space-y-3 border-t border-white/10">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <HelpCircle className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-slate-200">
                PAYMENT QUESTIONS
              </h4>
              <p className="text-[11px] text-slate-400">
                Questions to ask the seller before authorizing payment:
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {paymentQuestions.map((qText, idx) => {
              const isCopied = copiedQuestionIdx === idx;
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-white/5 hover:border-white/10 transition"
                >
                  <div className="flex items-start gap-2.5 pr-2">
                    <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono text-xs flex items-center justify-center shrink-0 mt-0.5 font-bold">
                      {idx + 1}
                    </span>
                    <p className="text-xs sm:text-sm font-medium text-slate-200 leading-snug">
                      {qText}
                    </p>
                  </div>

                  <button
                    onClick={() => handleCopyQuestion(idx, qText)}
                    className={`shrink-0 flex items-center gap-1 text-[11px] px-2 py-1 rounded-md transition font-medium ${
                      isCopied
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                    }`}
                    title="Copy question"
                  >
                    {isCopied ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3 text-slate-400" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
