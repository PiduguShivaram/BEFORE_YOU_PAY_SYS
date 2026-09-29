"use client";

import React from "react";
import {
  Car,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  ExternalLink,
  Layers,
  Calculator,
} from "lucide-react";
import {
  FinancialComponent,
  SmartCostReductionQuestion,
  ValidationCheck,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";
import { StatusBadge, FinancialValue } from "./ui";

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
}) => {

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
    <div className="surface-card rounded-2xl p-5 sm:p-6 border border-white/10 shadow-card space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wider uppercase bg-brand-500/15 text-brand-400 border border-brand-500/30">
              <Car className="w-3.5 h-3.5" />
              FINANCIAL BREAKDOWN
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Vehicle Quotation
            </span>
          </div>
          <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Cost Breakdown &amp; Reconciliation
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Clear separation of listed charges, stated totals, and independent reconciliation checks.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-2">
          {!isComponentReconciliationPass ? (
            <StatusBadge status="REQUIRES_VERIFICATION" label="Component Discrepancy" />
          ) : isQuotedTotalReconciliationPass ? (
            <StatusBadge status="PASS" label="Reconciled" />
          ) : (
            <StatusBadge status="REQUIRES_VERIFICATION" label="Verify Total" />
          )}
        </div>
      </div>

      {/* ── 1. WHAT YOU ARE PAYING FOR ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
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
                    ? "bg-brand-500/15 border-l-4 border-l-brand-400"
                    : "hover:bg-white/[0.04] border-l-4 border-l-transparent"
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
                    <FinancialValue
                      amount={amt}
                      currency={currency}
                      variant="item"
                    />
                    <span className="text-[10px] text-brand-400 font-sans flex items-center justify-end gap-1 mt-0.5">
                      <span>Inspect</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </span>
                  </div>
                </div>

                {/* Expanded Details when row is selected */}
                {isSelected && (comp.document_states || comp.system_knows || comp.requires_confirmation) && (
                  <div className="mt-2.5 pt-2.5 border-t border-white/10 grid grid-cols-1 gap-1.5 text-xs">
                    {comp.document_states && (
                      <div className="bg-slate-950/70 rounded-lg p-2.5 border border-white/5">
                        <span className="font-bold text-slate-400 uppercase tracking-wider text-[10px] block">
                          Document states
                        </span>
                        <p className="text-slate-200 mt-0.5">{comp.document_states}</p>
                      </div>
                    )}
                    {comp.system_knows && (
                      <div className="bg-slate-950/70 rounded-lg p-2.5 border border-white/5">
                        <span className="font-bold text-brand-400 uppercase tracking-wider text-[10px] block">
                          System knows
                        </span>
                        <p className="text-slate-200 mt-0.5">{comp.system_knows}</p>
                      </div>
                    )}
                    {comp.requires_confirmation && (
                      <div className="bg-amber-950/30 rounded-lg p-2.5 border border-amber-500/20">
                        <span className="font-bold text-amber-300 uppercase tracking-wider text-[10px] block">
                          Requires confirmation
                        </span>
                        <p className="text-amber-200 mt-0.5">{comp.requires_confirmation}</p>
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
        <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Calculator className="w-4 h-4 text-brand-400" />
          TOTALS &amp; DEDUCTIONS
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* LISTED COMPONENT TOTAL */}
          <div className="p-3.5 rounded-xl bg-app-cardSubtle border border-app-borderSubtle flex flex-col justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              LISTED COMPONENT TOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <FinancialValue
                amount={listedComponentTotal}
                currency={currency}
                variant="subtotal"
              />
              <span className="text-[11px] text-slate-400 font-sans">
                Sum of {chargeItems.length} charges
              </span>
            </div>
          </div>

          {/* STATED SUBTOTAL */}
          <div className="p-3.5 rounded-xl bg-app-cardSubtle border border-app-borderSubtle flex flex-col justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              STATED SUBTOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <FinancialValue
                amount={statedSubtotal}
                currency={currency}
                variant={statedSubtotal != null ? "subtotal" : "unknown"}
              />
              <span className="text-[11px] text-slate-400 font-sans">
                On quotation
              </span>
            </div>
          </div>

          {/* OFFERS / DISCOUNTS */}
          <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20 flex flex-col justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
              OFFERS / DISCOUNTS
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <FinancialValue
                amount={discountsSum}
                currency={currency}
                variant="deduction"
              />
              <span className="text-[11px] text-emerald-400/80 font-sans">
                {discountItems.length} offer{discountItems.length !== 1 ? "s" : ""} applied
              </span>
            </div>
          </div>

          {/* FINAL QUOTED TOTAL */}
          <div className="p-3.5 rounded-xl bg-slate-900 border border-brand-500/40 shadow-sm flex flex-col justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-300">
              FINAL QUOTED TOTAL
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <FinancialValue
                amount={quotedTotal}
                currency={currency}
                variant="hero"
              />
              <span className="text-[11px] text-brand-300/80 font-sans">
                Final payable amount
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

