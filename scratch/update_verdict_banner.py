banner_code = """\"use client\";

import React from \"react\";
import {
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  RotateCcw,
  Truck,
  CreditCard,
  ShieldCheck,
  FileQuestion,
  Sparkles,
  HelpCircle,
} from \"lucide-react\";
import { FinalDecisionSupportResult } from \"../lib/types\";
import { formatCurrency } from \"../lib/utils\";

interface VerdictBannerProps {
  result: FinalDecisionSupportResult;
  onReset: () => void;
}

export const VerdictBanner: React.FC<VerdictBannerProps> = ({ result, onReset }) => {
  const { summary, validation_checks, flags, document_id, document, analysis_state, ocr_quality } = result;
  const status = summary.overall_status;
  const state = analysis_state || summary.analysis_state || \"FINANCIAL_DATA_FOUND\";
  const currency = document?.currency ?? null;

  const isUnreliableOcr = state === \"OCR_UNRELIABLE\";
  const isUnreadableDoc = state === \"DOCUMENT_UNREADABLE\";
  const isNoFinancial = state === \"NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR\";
  const isInconclusive = state === \"EXTRACTION_INCONCLUSIVE\";

  const isCritical = status === \"CRITICAL_WARNING\" && !isUnreliableOcr && !isUnreadableDoc && !isNoFinancial;
  const isAttention = (status === \"REQUIRES_ATTENTION\" || status === \"DISCREPANCY_DETECTED\") && !isUnreliableOcr && !isUnreadableDoc && !isNoFinancial;

  // Find math checks to display total
  const sumCheck = validation_checks.find(
    (c) => c.check_code.includes(\"SUM\") || c.check_code.includes(\"TOTAL\")
  );
  const totalAmount =
    document?.total_amount?.normalized_value != null
      ? parseFloat(String(document.total_amount.normalized_value))
      : (sumCheck?.expected_value ? parseFloat(String(sumCheck.expected_value)) : 0);
  const calculatedSum = sumCheck?.calculated_value != null ? parseFloat(String(sumCheck.calculated_value)) : null;

  const shippingAmount = document?.shipping_amount?.normalized_value != null
    ? parseFloat(String(document.shipping_amount.normalized_value))
    : null;

  const amountPaid = document?.amount_paid?.normalized_value != null
    ? parseFloat(String(document.amount_paid.normalized_value))
    : null;

  const balanceDue = document?.balance_due?.normalized_value != null
    ? parseFloat(String(document.balance_due.normalized_value))
    : (amountPaid !== null ? Math.max(0, totalAmount - amountPaid) : totalAmount);

  const paymentStatus = document?.payment_status?.normalized_value != null
    ? String(document.payment_status.normalized_value)
    : null;

  // Special Visual Styling for Unreliable / Unreadable OCR
  if (isUnreliableOcr || isUnreadableDoc) {
    return (
      <div className=\"glass-panel rounded-2xl p-6 sm:p-8 mb-8 border-l-4 shadow-card border-l-amber-500 shadow-amber bg-amber-950/20\">
        <div className=\"flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6\">
          <div className=\"max-w-2xl\">
            <div className=\"flex items-center gap-2 mb-2\">
              <span className=\"inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold tracking-wider uppercase bg-amber-500/15 text-amber-400 border border-amber-500/30\">
                <AlertTriangle className=\"w-3.5 h-3.5\" />
                {isUnreadableDoc ? \"DOCUMENT UNREADABLE\" : \"OCR UNRELIABLE\"}
              </span>
              <span className=\"text-xs text-slate-500 font-mono\">
                Doc ID: {document_id.slice(0, 8)}...
              </span>
              {ocr_quality && (
                <span className=\"text-xs font-bold text-amber-300 font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20\">
                  Score: {Math.round(ocr_quality.score * 100)}%
                </span>
              )}
            </div>

            <h2 className=\"text-xl sm:text-2xl font-extrabold text-white mb-2 leading-tight\">
              {summary.headline}
            </h2>

            <p className=\"text-sm text-slate-300 leading-relaxed mb-4\">
              Some text extracted from this document appears corrupted or unreadable, so financial analysis was not performed.
              <span className=\"block mt-1 font-semibold text-amber-300\">
                Try uploading a clearer image or higher-resolution PDF.
              </span>
            </p>

            {ocr_quality?.reasons && ocr_quality.reasons.length > 0 && (
              <div className=\"flex flex-wrap items-center gap-2 pt-1\">
                {ocr_quality.reasons.map((r, i) => (
                  <span key={i} className=\"text-[11px] font-mono px-2.5 py-1 rounded bg-slate-900/80 text-slate-400 border border-white/5\">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className=\"flex flex-col sm:flex-row lg:flex-col items-start lg:items-end justify-between gap-4 w-full lg:w-auto pt-4 lg:pt-0 border-t lg:border-t-0 border-white/10\">
            <div className=\"text-left lg:text-right\">
              <span className=\"text-xs uppercase font-semibold text-slate-400 tracking-wider block\">
                Financial Status
              </span>
              <span className=\"text-2xl sm:text-3xl font-mono font-bold text-amber-400 tracking-tight\">
                Analysis Bypassed
              </span>
              <span className=\"text-xs text-slate-400 block mt-0.5\">
                Safety gate prevented false zero
              </span>
            </div>

            <button
              onClick={onReset}
              className=\"flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-amber-200 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 transition active:scale-95 shadow-sm\"
            >
              <RotateCcw className=\"w-3.5 h-3.5\" />
              <span>Upload Clearer Document</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Visual Styling for Reliable OCR with No Financial Obligations
  if (isNoFinancial) {
    return (
      <div className=\"glass-panel rounded-2xl p-6 sm:p-8 mb-8 border-l-4 shadow-card border-l-sky-500 shadow-sky bg-sky-950/20\">
        <div className=\"flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6\">
          <div className=\"max-w-2xl\">
            <div className=\"flex items-center gap-2 mb-2\">
              <span className=\"inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold tracking-wider uppercase bg-sky-500/15 text-sky-400 border border-sky-500/30\">
                <FileQuestion className=\"w-3.5 h-3.5\" />
                RELIABLE OCR • NO FINANCIAL OBLIGATIONS
              </span>
              <span className=\"text-xs text-slate-500 font-mono\">
                Doc ID: {document_id.slice(0, 8)}...
              </span>
            </div>

            <h2 className=\"text-xl sm:text-2xl font-extrabold text-white mb-2 leading-tight\">
              {summary.headline}
            </h2>

            <p className=\"text-sm text-slate-300 leading-relaxed mb-4\">
              Document text was reliably recognized, but no financial amounts, itemized line items, or billing commitments were identified. The document does not require payment authorization.
            </p>
          </div>

          <div className=\"flex flex-col sm:flex-row lg:flex-col items-start lg:items-end justify-between gap-4 w-full lg:w-auto pt-4 lg:pt-0 border-t lg:border-t-0 border-white/10\">
            <div className=\"text-left lg:text-right\">
              <span className=\"text-xs uppercase font-semibold text-slate-400 tracking-wider block\">
                Total Payable
              </span>
              <span className=\"text-3xl sm:text-4xl font-mono font-extrabold text-slate-300 tracking-tight\">
                None
              </span>
              <span className=\"text-xs text-slate-400 block mt-0.5\">
                Non-monetary document
              </span>
            </div>

            <button
              onClick={onReset}
              className=\"flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-slate-200 bg-white/5 hover:bg-white/10 border border-white/10 transition active:scale-95\"
            >
              <RotateCcw className=\"w-3.5 h-3.5\" />
              <span>Scan Another Document</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Standard Financial Result Banner
  return (
    <div
      className={`glass-panel rounded-2xl p-6 sm:p-8 mb-8 border-l-4 shadow-card ${
        isCritical
          ? \"border-l-rose-500 shadow-rose\"
          : isAttention || isInconclusive
          ? \"border-l-amber-500 shadow-amber\"
          : \"border-l-emerald-500 shadow-emerald\"
      }`}
    >
      <div className=\"flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6\">
        {/* Left: Status & Headline */}
        <div className=\"max-w-2xl\">
          <div className=\"flex items-center gap-2 mb-2\">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold tracking-wider uppercase ${
                isCritical
                  ? \"bg-rose-500/15 text-rose-400 border border-rose-500/30\"
                  : isAttention || isInconclusive
                  ? \"bg-amber-500/15 text-amber-400 border border-amber-500/30\"
                  : \"bg-emerald-500/15 text-emerald-400 border border-emerald-500/30\"
              }`}
            >
              {isCritical ? (
                <AlertOctagon className=\"w-3.5 h-3.5\" />
              ) : isAttention || isInconclusive ? (
                <AlertTriangle className=\"w-3.5 h-3.5\" />
              ) : (
                <CheckCircle className=\"w-3.5 h-3.5\" />
              )}
              {isInconclusive ? \"EXTRACTION INCONCLUSIVE\" : status.replace(/_/g, \" \")}
            </span>
            <span className=\"text-xs text-slate-500 font-mono\">
              Doc ID: {document_id.slice(0, 8)}...
            </span>
            {currency && (
              <span className=\"text-xs font-bold text-slate-400 font-mono px-2 py-0.5 rounded bg-white/5 border border-white/10\">
                {currency}
              </span>
            )}
            {ocr_quality && (
              <span className=\"text-xs font-mono text-slate-400 px-2 py-0.5 rounded bg-white/5 border border-white/10\">
                OCR Quality: {ocr_quality.status}
              </span>
            )}
          </div>

          <h2 className=\"text-xl sm:text-2xl font-extrabold text-white mb-2 leading-tight\">
            {summary.headline}
          </h2>

          <p className=\"text-sm text-slate-300 leading-relaxed mb-4\">
            {flags.length === 0
              ? \"All arithmetic extensions reconcile with stated subtotals and no terms require immediate attention.\"
              : `${flags.length} finding${flags.length > 1 ? \"s\" : \"\"} require${flags.length === 1 ? \"s\" : \"\"} user verification before authorizing payment commitment.`}
          </p>

          {/* Quick Financial Overview Badges */}
          <div className=\"flex flex-wrap items-center gap-3 pt-2\">
            {shippingAmount !== null && (
              <div className=\"inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-sky-500/10 border border-sky-500/20 text-xs font-mono text-sky-300\">
                <Truck className=\"w-3.5 h-3.5 text-sky-400\" />
                <span>Shipping: {formatCurrency(shippingAmount, currency)}</span>
              </div>
            )}
            {amountPaid !== null && (
              <div className=\"inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-300\">
                <CreditCard className=\"w-3.5 h-3.5 text-emerald-400\" />
                <span>Paid: {formatCurrency(amountPaid, currency)}</span>
              </div>
            )}
            {balanceDue !== null && (
              <div className=\"inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-brand-500/10 border border-brand-500/20 text-xs font-mono text-brand-300 font-bold\">
                <ShieldCheck className=\"w-3.5 h-3.5 text-brand-400\" />
                <span>Balance Due: {formatCurrency(balanceDue, currency)}</span>
              </div>
            )}
            {paymentStatus && totalAmount > 0 && (
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-bold uppercase tracking-wider ${
                paymentStatus === \"paid\"
                  ? \"bg-emerald-500/15 border border-emerald-500/30 text-emerald-300\"
                  : paymentStatus === \"partial\"
                  ? \"bg-amber-500/15 border border-amber-500/30 text-amber-300\"
                  : \"bg-rose-500/15 border border-rose-500/30 text-rose-300\"
              }`}>
                <span>Status: {paymentStatus}</span>
              </div>
            )}
          </div>
        </div>

        {/* Right: Numbers & Action */}
        <div className=\"flex flex-col sm:flex-row lg:flex-col items-start lg:items-end justify-between gap-4 w-full lg:w-auto pt-4 lg:pt-0 border-t lg:border-t-0 border-white/10\">
          <div className=\"text-left lg:text-right\">
            <span className=\"text-xs uppercase font-semibold text-slate-400 tracking-wider block\">
              Total Payable
            </span>
            <span className=\"text-3xl sm:text-4xl font-mono font-extrabold text-white tracking-tight\">
              {formatCurrency(balanceDue !== null ? balanceDue : totalAmount, currency)}
            </span>
            {calculatedSum !== null && (
              <span className=\"text-xs font-mono text-slate-400 block mt-0.5\">
                Stated Bill Total: {formatCurrency(totalAmount, currency)}
              </span>
            )}
          </div>

          <button
            onClick={onReset}
            className=\"flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-slate-200 bg-white/5 hover:bg-white/10 border border-white/10 transition active:scale-95\"
          >
            <RotateCcw className=\"w-3.5 h-3.5\" />
            <span>Scan Another Document</span>
          </button>
        </div>
      </div>
    </div>
  );
};
"""

with open("frontend/src/components/VerdictBanner.tsx", "w", encoding="utf-8") as f:
    f.write(banner_code)
print("Updated frontend/src/components/VerdictBanner.tsx successfully")
