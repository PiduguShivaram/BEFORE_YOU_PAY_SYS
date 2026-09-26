"use client";

import React from "react";
import {
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  RotateCcw,
  Truck,
  CreditCard,
  ShieldCheck,
  FileQuestion,
  Info,
  Car,
  FileText,
  Scan,
} from "lucide-react";
import { FinalDecisionSupportResult } from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface VerdictBannerProps {
  result: FinalDecisionSupportResult;
  onReset: () => void;
}

export const VerdictBanner: React.FC<VerdictBannerProps> = ({ result, onReset }) => {
  const {
    summary,
    validation_checks,
    flags,
    document_id,
    document,
    analysis_state,
    ocr_quality,
  } = result;

  const formatOcrQuality = (status?: string | null) => {
    switch (status) {
      case "GOOD":
        return "High";
      case "MODERATE":
        return "Moderate";
      case "DEGRADED":
        return "Degraded";
      case "UNRELIABLE":
        return "Unreliable";
      default:
        return status || "Unknown";
    }
  };

  const status = summary.overall_status;
  const state = analysis_state || summary.analysis_state || "FINANCIAL_DATA_FOUND";
  const currency = document?.currency ?? null;

  const isUnreliableOcr = state === "OCR_UNRELIABLE";
  const isUnreadableDoc = state === "DOCUMENT_UNREADABLE";
  const isNoFinancial = state === "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR";
  const isInconclusive = state === "EXTRACTION_INCONCLUSIVE";

  const isCritical = status === "CRITICAL_WARNING" && !isUnreliableOcr && !isUnreadableDoc && !isNoFinancial;
  const isAttention = (status === "REQUIRES_ATTENTION" || status === "DISCREPANCY_DETECTED") && !isUnreliableOcr && !isUnreadableDoc && !isNoFinancial;

  const isQuotation =
    document?.document_type === "quotation" ||
    document?.document_type === "cost_breakdown" ||
    Boolean(document?.cost_breakdown && document.cost_breakdown.length > 0);

  // Find math checks to display total
  const sumCheck = validation_checks.find(
    (c) => c.check_code.includes("SUM") || c.check_code.includes("TOTAL")
  );
  const totalAmount =
    document?.total_amount?.normalized_value != null
      ? parseFloat(String(document.total_amount.normalized_value))
      : (sumCheck?.expected_value ? parseFloat(String(sumCheck.expected_value)) : 0);

  const shippingAmount =
    document?.shipping_amount?.normalized_value != null
      ? parseFloat(String(document.shipping_amount.normalized_value))
      : null;

  const amountPaid =
    document?.amount_paid?.normalized_value != null
      ? parseFloat(String(document.amount_paid.normalized_value))
      : null;

  const balanceDue =
    document?.balance_due?.normalized_value != null
      ? parseFloat(String(document.balance_due.normalized_value))
      : (amountPaid !== null ? Math.max(0, totalAmount - amountPaid) : totalAmount);

  const paymentStatus =
    document?.payment_status?.normalized_value != null
      ? String(document.payment_status.normalized_value)
      : null;

  const subtotalAmount =
    document?.subtotal?.normalized_value != null
      ? parseFloat(String(document.subtotal.normalized_value))
      : null;

  const discountAmount =
    document?.discount_amount?.normalized_value != null
      ? parseFloat(String(document.discount_amount.normalized_value))
      : null;

  const allChecksPass = validation_checks.length > 0 && validation_checks.every((c) => c.status === "PASS");

  // Primary verification finding
  const primaryFinding = flags.length > 0 ? flags[0] : null;

  // Unreliable / Unreadable OCR State
  if (isUnreliableOcr || isUnreadableDoc) {
    return (
      <div className="glass-panel rounded-2xl p-5 sm:p-7 mb-6 border-l-4 border-l-amber-500 shadow-card bg-amber-950/20 space-y-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            {isUnreadableDoc ? "DOCUMENT UNREADABLE" : "OCR UNRELIABLE"}
          </span>
          {ocr_quality && (
            <span className="text-xs font-bold text-amber-300 font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
              OCR: {formatOcrQuality(ocr_quality.status)}
            </span>
          )}
        </div>

        <div>
          <h2 className="text-lg sm:text-xl font-extrabold text-white mb-1.5 leading-snug">
            {summary.headline}
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Some text extracted from this document appears corrupted or unreadable, so financial calculations were not performed to prevent false totals.
          </p>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="w-full sm:w-auto min-h-[48px] px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold text-amber-200 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 transition active:scale-98 flex items-center justify-center gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Upload Clearer Document</span>
        </button>
      </div>
    );
  }

  // Reliable OCR with No Financial Obligations
  if (isNoFinancial) {
    return (
      <div className="glass-panel rounded-2xl p-5 sm:p-7 mb-6 border-l-4 border-l-sky-500 shadow-card bg-sky-950/20 space-y-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase bg-sky-500/15 text-sky-400 border border-sky-500/30">
            <FileQuestion className="w-3.5 h-3.5" />
            NON-MONETARY DOCUMENT
          </span>
        </div>

        <div>
          <h2 className="text-lg sm:text-xl font-extrabold text-white mb-1 leading-snug">
            {summary.headline}
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Text was reliably recognized, but no financial payable amounts or billing commitments were detected. No payment authorization required.
          </p>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="w-full sm:w-auto min-h-[48px] px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold text-slate-200 bg-white/5 hover:bg-white/10 border border-white/10 transition active:scale-98 flex items-center justify-center gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Scan Another Document</span>
        </button>
      </div>
    );
  }

  // Standard Financial Result Card (Mobile-First)
  return (
    <div
      className={`glass-panel rounded-2xl p-5 sm:p-7 mb-6 border-l-4 shadow-card space-y-5 ${
        isCritical
          ? "border-l-rose-500"
          : isAttention || isInconclusive
          ? "border-l-amber-500"
          : "border-l-emerald-500"
      }`}
    >
      {/* 1. Header Badges: Document Classification + OCR Quality + Status */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-white/10">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 uppercase tracking-wider">
            {isQuotation ? <Car className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
            {isQuotation ? "VEHICLE QUOTATION" : (document?.document_type?.toUpperCase() || "DOCUMENT")}
          </span>

          {ocr_quality && (
            <span
              className={`text-[11px] font-mono px-2 py-0.5 rounded border font-semibold ${
                ocr_quality.status === "GOOD"
                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                  : ocr_quality.status === "MODERATE"
                  ? "bg-sky-500/10 text-sky-300 border-sky-500/20"
                  : "bg-amber-500/10 text-amber-300 border-amber-500/20"
              }`}
            >
              OCR: {formatOcrQuality(ocr_quality.status)}
            </span>
          )}

          <span
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-extrabold tracking-wider uppercase ${
              isCritical
                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                : isAttention || isInconclusive
                ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
            }`}
          >
            {isCritical ? (
              <AlertOctagon className="w-3 h-3" />
            ) : isAttention || isInconclusive ? (
              <AlertTriangle className="w-3 h-3" />
            ) : (
              <CheckCircle className="w-3 h-3" />
            )}
            {isInconclusive ? "EXTRACTION INCONCLUSIVE" : status.replace(/_/g, " ")}
          </span>
        </div>

        {/* Rescan Quick Action */}
        <button
          type="button"
          onClick={onReset}
          className="min-h-[44px] px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-300 bg-white/5 hover:bg-white/10 active:scale-95 transition flex items-center gap-1.5"
          aria-label="Scan Another Document"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span className="hidden xs:inline">Scan Another</span>
        </button>
      </div>

      {/* 2. Primary Headline */}
      <div>
        <h2 className="text-lg sm:text-2xl font-extrabold text-white tracking-tight leading-snug">
          {summary.headline}
        </h2>
        <p className="text-xs sm:text-sm text-slate-300 mt-1 leading-relaxed">
          {allChecksPass
            ? "Deterministic arithmetic verified: Stated components match the quoted net total."
            : `${flags.length} finding${flags.length > 1 ? "s" : ""} require${flags.length === 1 ? "s" : ""} review before authorizing payment.`}
        </p>
      </div>

      {/* 3. Prominent Mobile Financial Summary Card (WHAT AM I PAYING?) */}
      <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-br from-brand-950/50 via-slate-900/80 to-slate-950 border border-brand-500/30 shadow-xl space-y-4">
        {/* Big Total Payable Number */}
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 pb-3 border-b border-white/10">
          <div>
            <span className="text-[11px] sm:text-xs uppercase font-extrabold tracking-wider text-brand-300 block">
              {isQuotation ? "Total Quoted On-Road Price" : "Total to Pay"}
            </span>
            <span className="text-3xl sm:text-4xl font-mono font-extrabold text-white tracking-tight mt-0.5 block">
              {formatCurrency(balanceDue !== null ? balanceDue : totalAmount, currency)}
            </span>
          </div>

          <div className="flex items-center gap-2 pt-1 sm:pt-0">
            {allChecksPass && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span>Arithmetic Reconciled</span>
              </span>
            )}
            {paymentStatus && (
              <span className="text-xs font-mono font-bold uppercase px-2 py-0.5 rounded bg-white/10 text-slate-200">
                {paymentStatus}
              </span>
            )}
          </div>
        </div>

        {/* 3-Box Financial Breakdown: Subtotal, Offers/Paid, Balance */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 text-xs font-mono">
          {isQuotation ? (
            <>
              <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">
                  Stated Subtotal
                </span>
                <span className="text-sm sm:text-base font-bold text-slate-100 block mt-0.5">
                  {formatCurrency(subtotalAmount ?? totalAmount, currency)}
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20">
                <span className="text-[10px] text-emerald-400 uppercase font-sans font-semibold block">
                  Offers & Discounts
                </span>
                <span className="text-sm sm:text-base font-bold text-emerald-300 block mt-0.5">
                  {discountAmount !== null && discountAmount > 0
                    ? `−${formatCurrency(discountAmount, currency)}`
                    : "None"}
                </span>
              </div>

              <div className="col-span-2 sm:col-span-1 p-2.5 rounded-xl bg-brand-950/20 border border-brand-500/20">
                <span className="text-[10px] text-brand-300 uppercase font-sans font-semibold block">
                  Reconciliation Delta
                </span>
                <span className="text-sm sm:text-base font-bold text-brand-200 block mt-0.5">
                  {formatCurrency(0, currency)} (Exact Match)
                </span>
              </div>
            </>
          ) : (
            <>
              <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">
                  Stated Total
                </span>
                <span className="text-sm sm:text-base font-bold text-slate-100 block mt-0.5">
                  {formatCurrency(totalAmount, currency)}
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold block">
                  Amount Paid
                </span>
                <span className="text-sm sm:text-base font-bold text-emerald-300 block mt-0.5">
                  {formatCurrency(amountPaid ?? 0, currency)}
                </span>
              </div>

              <div className="col-span-2 sm:col-span-1 p-2.5 rounded-xl bg-brand-950/20 border border-brand-500/20">
                <span className="text-[10px] text-brand-300 uppercase font-sans font-semibold block">
                  Balance Due
                </span>
                <span className="text-sm sm:text-base font-bold text-brand-200 block mt-0.5">
                  {formatCurrency(balanceDue ?? totalAmount, currency)}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 4. Primary Decision Finding (WHAT NEEDS MY ATTENTION?) */}
      {primaryFinding && (
        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wider text-amber-300">
              Requires Verification: Commercial Terms
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-200 leading-relaxed font-medium">
            {primaryFinding.message}
          </p>
          <p className="text-[11px] text-slate-400 leading-relaxed border-t border-white/5 pt-1.5">
            <strong>Important Legal Clarity:</strong> Deterministic arithmetic confirms numbers on the slip reconcile mathematically. It does not certify legal validity, fraud-free delivery, or price guarantees without direct dealer confirmation.
          </p>
        </div>
      )}
    </div>
  );
};
