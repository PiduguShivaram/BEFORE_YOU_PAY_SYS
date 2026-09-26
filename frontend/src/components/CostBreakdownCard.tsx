"use client";

import React from "react";
import {
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  Car,
  Check,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { FinancialComponent, ValidationCheck } from "../lib/types";
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
}

export const CostBreakdownCard: React.FC<CostBreakdownCardProps> = ({
  components,
  currency = "INR",
  subtotal,
  discountTotal,
  quotedTotal,
  validationChecks,
  selectedComponentId,
  onSelectComponent,
}) => {
  const charges = components.filter((c) => c.charge_nature === "charge");
  const deductions = components.filter((c) => c.charge_nature === "deduction");

  const computedChargesSum = charges.reduce(
    (sum, c) => sum + Number(c.amount?.normalized_value || 0),
    0
  );
  const computedDeductionsSum = deductions.reduce(
    (sum, c) => sum + Number(c.amount?.normalized_value || 0),
    0
  );

  const subtotalCheck = validationChecks.find(
    (c) => c.check_code === "QUOTATION_SUBTOTAL_CONSISTENCY"
  );
  const netTotalCheck = validationChecks.find(
    (c) => c.check_code === "QUOTATION_NET_TOTAL_CONSISTENCY"
  );

  const isSubtotalPass = subtotalCheck?.status === "PASS";
  const isNetTotalPass = netTotalCheck?.status === "PASS";

  const getCategoryBadge = (cat: string) => {
    switch (cat) {
      case "base_price":
        return { label: "Base Vehicle Price", color: "bg-blue-500/10 text-blue-300 border-blue-500/20" };
      case "tax":
        return { label: "TCS / Tax", color: "bg-purple-500/10 text-purple-300 border-purple-500/20" };
      case "insurance":
        return { label: "Insurance", color: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" };
      case "registration":
        return { label: "R.C. & Road Tax", color: "bg-amber-500/10 text-amber-300 border-amber-500/20" };
      case "warranty":
        return { label: "Warranty", color: "bg-indigo-500/10 text-indigo-300 border-indigo-500/20" };
      case "accessory_or_fee":
        return { label: "Registration Fee", color: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20" };
      case "discount":
        return { label: "Dealer Offer", color: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" };
      default:
        return { label: "Charge", color: "bg-slate-500/10 text-slate-400 border-slate-500/20" };
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-7 border border-white/10 shadow-xl space-y-5">
      {/* Header: Itemized Cost Breakdown */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
              <Car className="w-3.5 h-3.5" />
              VEHICLE QUOTATION BREAKDOWN
            </span>
            <span className="text-xs text-slate-400 font-mono hidden xs:inline">
              Itemized Charges
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
            Quotation Cost Breakdown & Reconciliation
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Tap any row to inspect original handwriting & spatial OCR bounding box
          </p>
        </div>

        {/* Global Status Pill */}
        <div className="shrink-0">
          {isSubtotalPass && isNetTotalPass ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Arithmetic Reconciled (100% Pass)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <AlertCircle className="w-4 h-4 text-amber-400" />
              Requires Verification
            </span>
          )}
        </div>
      </div>

      {/* 1. Constituent Charges Section (Mobile Stacked Rows) */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wider font-bold text-slate-400">
            1. Constituent Charges ({charges.length} items)
          </span>
          <span className="text-[11px] text-brand-400 font-medium hidden sm:inline">
            Tap to view on document canvas
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 divide-y divide-white/5">
          {charges.map((comp) => {
            const badge = getCategoryBadge(comp.category);
            const amt = Number(comp.amount?.normalized_value || 0);
            const isSelected = selectedComponentId === comp.component_id;

            return (
              <div
                key={comp.component_id}
                onClick={() => onSelectComponent && onSelectComponent(comp)}
                className={`min-h-[52px] flex items-center justify-between p-3.5 sm:px-4 cursor-pointer transition active:scale-[0.99] select-none ${
                  isSelected
                    ? "bg-brand-500/20 border-l-4 border-l-brand-400"
                    : "hover:bg-white/5 border-l-4 border-l-transparent"
                }`}
                role="button"
                tabIndex={0}
                aria-label={`Inspect ${comp.name}: ${formatCurrency(amt, currency)}`}
              >
                {/* Left: Name and Category */}
                <div className="flex items-center gap-2.5 min-w-0 pr-2">
                  <span className="w-2 h-2 rounded-full bg-brand-400 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-xs sm:text-sm font-semibold text-slate-100 block truncate">
                      {comp.name}
                    </span>
                    <span
                      className={`inline-block mt-0.5 text-[10px] font-mono px-2 py-0.5 rounded border ${badge.color}`}
                    >
                      {badge.label}
                    </span>
                  </div>
                </div>

                {/* Right: Currency Amount and Inspect cue */}
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
            );
          })}
        </div>
      </div>

      {/* Subtotal / Total Before Offers Card */}
      <div className="p-3.5 sm:p-4 rounded-xl bg-slate-800/40 border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div>
          <span className="text-xs font-semibold text-slate-400 block uppercase tracking-wider">
            Subtotal / Total Before Offers
          </span>
          <p className="text-xs text-slate-400 mt-0.5">
            Sum of listed charges: {formatCurrency(computedChargesSum, currency)}
          </p>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-3 pt-1 sm:pt-0 border-t sm:border-t-0 border-white/5">
          <span className="text-base sm:text-lg font-mono font-extrabold text-white">
            {formatCurrency(subtotal ?? computedChargesSum, currency)}
          </span>
          {isSubtotalPass ? (
            <span className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" /> Sum Matches
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" /> Discrepancy
            </span>
          )}
        </div>
      </div>

      {/* 2. Deductions / Offers Section (Mobile Stacked Rows) */}
      {deductions.length > 0 && (
        <div className="space-y-2.5 pt-1">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider font-bold text-emerald-400 flex items-center gap-1.5">
              <TrendingDown className="w-3.5 h-3.5" />
              2. Discounts & Deductions Applied ({deductions.length} offers)
            </span>
            <span className="text-xs font-mono font-bold text-emerald-400">
              Total Offers: -{formatCurrency(computedDeductionsSum, currency)}
            </span>
          </div>

          <div className="overflow-hidden rounded-xl border border-emerald-500/20 bg-emerald-950/15 divide-y divide-emerald-500/10">
            {deductions.map((comp) => {
              const amt = Number(comp.amount?.normalized_value || 0);
              const isSelected = selectedComponentId === comp.component_id;

              return (
                <div
                  key={comp.component_id}
                  onClick={() => onSelectComponent && onSelectComponent(comp)}
                  className={`min-h-[52px] flex items-center justify-between p-3.5 sm:px-4 cursor-pointer transition active:scale-[0.99] select-none ${
                    isSelected
                      ? "bg-emerald-500/25 border-l-4 border-l-emerald-400"
                      : "hover:bg-emerald-500/10 border-l-4 border-l-transparent"
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-label={`Inspect ${comp.name}: -${formatCurrency(amt, currency)}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 pr-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                    <div className="min-w-0">
                      <span className="text-xs sm:text-sm font-semibold text-emerald-200 block truncate">
                        {comp.name}
                      </span>
                      <span className="text-[10px] text-emerald-400 font-mono">
                        Deduction / Dealer Concession
                      </span>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-sm sm:text-base font-mono font-bold text-emerald-300 block">
                      −{formatCurrency(amt, currency)}
                    </span>
                    <span className="text-[10px] text-emerald-400 font-sans flex items-center justify-end gap-1">
                      <span>Inspect</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Final Quoted Total Payable Card */}
      <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-brand-950/40 via-slate-900/60 to-emerald-950/30 border border-brand-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-xs font-extrabold uppercase tracking-wider text-brand-300 block">
            Final Quoted Total Payable (On-Road)
          </span>
          <p className="text-xs text-slate-300 mt-0.5">
            Formula: Subtotal ({formatCurrency(subtotal ?? computedChargesSum, currency)}) − Offers ({formatCurrency(computedDeductionsSum, currency)})
          </p>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-3 pt-2 sm:pt-0 border-t sm:border-t-0 border-white/5">
          <div className="text-left sm:text-right">
            <span className="text-2xl sm:text-3xl font-mono font-extrabold text-white tracking-tight block">
              {formatCurrency(quotedTotal, currency)}
            </span>
            <span className="text-xs text-emerald-400 font-mono font-bold">
              {isNetTotalPass ? "Net arithmetic verified" : "Requires confirmation"}
            </span>
          </div>

          {isNetTotalPass && (
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
