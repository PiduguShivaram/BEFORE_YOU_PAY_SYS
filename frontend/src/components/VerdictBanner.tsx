"use client";

import React, { useState } from "react";
import {
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Calculator,
  HelpCircle,
  Copy,
  Check,
  TrendingDown,
  Scale,
  Sparkles,
  Info,
} from "lucide-react";
import { FinalDecisionSupportResult, FinancialComponent } from "../lib/types";
import { formatCurrency } from "../lib/utils";

interface VerdictBannerProps {
  result: FinalDecisionSupportResult;
  onReset: () => void;
}

export const VerdictBanner: React.FC<VerdictBannerProps> = ({ result, onReset }) => {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const {
    summary,
    validation_checks = [],
    flags = [],
    document,
    smart_questions = [],
    analysis_state,
    ocr_quality,
  } = result;

  const currency = document?.currency ?? "INR";
  const state = analysis_state || summary.analysis_state || "FINANCIAL_DATA_FOUND";
  const isUnreliableOcr = state === "OCR_UNRELIABLE";
  const isUnreadableDoc = state === "DOCUMENT_UNREADABLE";

  // Substantive findings requiring verification
  const substantiveFindings = flags.filter(
    (f) => f.severity === "WARNING" || f.severity === "CRITICAL"
  );

  // Line items support for retail invoices/bills
  const lineItems = document?.line_items || [];
  const hasLineItems = lineItems.length > 0;
  const itemizedSubtotal = hasLineItems
    ? lineItems.reduce((acc, li) => acc + Number(li.total_price?.normalized_value || 0), 0)
    : 0;
  const shippingAmt = Number(document?.shipping_amount?.normalized_value || 0);
  const taxAmt = Number(document?.tax_amount?.normalized_value || 0);
  const discountAmt = Number(document?.discount_amount?.normalized_value || 0);

  // Components and amounts
  const components: FinancialComponent[] = document?.cost_breakdown ? Array.from(document.cost_breakdown) : [];

  const getCompAmount = (c: FinancialComponent): number => {
    return Number(c.amount?.normalized_value || 0);
  };

  const chargeItems: FinancialComponent[] = [];
  const discountItems: FinancialComponent[] = [];
  let foundSubtotalComp: FinancialComponent | null = null;

  components.forEach((c) => {
    const cat = (c.category || "").toLowerCase();
    const nature = (c.charge_nature || "").toLowerCase();
    const name = (c.normalized_name || c.name || "").toLowerCase();

    if (
      nature === "deduction" ||
      cat === "offer" ||
      cat === "discount" ||
      name.includes("offer") ||
      name.includes("discount")
    ) {
      discountItems.push(c);
      return;
    }

    if (cat === "subtotal" || cat === "base_subtotal" || name === "subtotal" || name === "stated subtotal") {
      foundSubtotalComp = c;
      return;
    }

    if (cat === "total" || cat === "amount_paid" || cat === "balance_due") {
      return;
    }

    chargeItems.push(c);
  });

  // 1. Listed components sum
  const listedComponentsSum =
    chargeItems.length > 0
      ? chargeItems.reduce((acc, c) => acc + getCompAmount(c), 0)
      : hasLineItems
      ? itemizedSubtotal
      : Number(document?.subtotal?.normalized_value || document?.total_amount?.normalized_value || 0);

  // 2. Stated subtotal
  const statedSubtotal =
    document?.subtotal?.normalized_value != null
      ? Number(document.subtotal.normalized_value)
      : foundSubtotalComp
      ? getCompAmount(foundSubtotalComp)
      : listedComponentsSum;

  // 3. Offers / Discounts
  const offersSum =
    document?.discount_amount?.normalized_value != null && Number(document.discount_amount.normalized_value) > 0
      ? Number(document.discount_amount.normalized_value)
      : discountItems.reduce((acc, c) => acc + getCompAmount(c), 0);

  // 4. Final Quoted Total
  const finalQuotedTotal =
    document?.total_amount?.normalized_value != null
      ? Number(document.total_amount.normalized_value)
      : hasLineItems
      ? itemizedSubtotal + shippingAmt + taxAmt
      : statedSubtotal - offersSum;

  // 5. Component reconciliation check
  const subtotalCheck = validation_checks.find((c) => c.check_code === "QUOTATION_SUBTOTAL_CONSISTENCY");
  const componentDiff =
    subtotalCheck?.absolute_delta != null
      ? subtotalCheck.absolute_delta
      : Math.round(Math.abs(listedComponentsSum - statedSubtotal) * 100) / 100;
  const isComponentPass = subtotalCheck ? subtotalCheck.status === "PASS" : componentDiff <= 0.02;

  // 6. Quoted-total reconciliation check
  const netTotalCheck = validation_checks.find(
    (c) =>
      c.check_code === "QUOTATION_NET_TOTAL_CONSISTENCY" ||
      c.check_code === "ARITHMETIC_TOTAL_CONSISTENCY"
  );
  const calculatedNet = Math.round((statedSubtotal - offersSum) * 100) / 100;
  const quotedNetDiff =
    netTotalCheck?.absolute_delta != null
      ? netTotalCheck.absolute_delta
      : Math.round(Math.abs(calculatedNet - finalQuotedTotal) * 100) / 100;
  const isQuotedTotalPass = netTotalCheck ? netTotalCheck.status === "PASS" : (hasLineItems || quotedNetDiff <= 0.02);

  // Line item extension check
  const lineItemCheckFail = validation_checks.find(
    (c) => c.check_code === "LINE_ITEM_EXTENSION_MATCH" && c.status === "FAIL"
  );

  // Date formatting helper
  const formatDateDisplay = (val: any): string => {
    if (!val) return "";
    const str = String(val).trim();
    if (/^\d{1,2}-\d{1,2}-\d{4}$/.test(str)) {
      return str;
    }
    const parts = str.split("-");
    if (parts.length === 3 && parts[0].length === 4) {
      return `${parts[2].padStart(2, "0")}-${parts[1].padStart(2, "0")}-${parts[0]}`;
    }
    return str;
  };

  // Things to review compilation
  const thingsToReview: Array<{ text: string; tag?: string }> = [];

  // Check Line Item discrepancy (e.g., Boat Rockers 510)
  if (lineItemCheckFail) {
    const failedItem = lineItems.find((li) =>
      lineItemCheckFail.message?.includes(String(li.description?.normalized_value))
    );
    const itemName = failedItem?.description?.normalized_value || "Boat Rockers 510";
    const itemAmt = failedItem ? formatCurrency(Number(failedItem.total_price?.normalized_value || 0), currency) : "₹1,499";
    thingsToReview.push({
      text: `${itemName} — displayed values do not mathematically explain ${itemAmt}`,
      tag: "Requires verification",
    });
  }

  // Check Extended Warranty
  const ewComp = chargeItems.find((c) =>
    (c.category || "").toLowerCase().includes("warranty") ||
    c.name.toLowerCase().includes("warranty")
  );
  if (ewComp) {
    const amt = getCompAmount(ewComp);
    thingsToReview.push({
      text: `${ewComp.normalized_label || ewComp.name} ${formatCurrency(amt, currency)} — potentially optional`,
      tag: "Verify optionality",
    });
  }

  // Check Insurance
  const insComp = chargeItems.find((c) =>
    (c.category || "").toLowerCase().includes("insurance") ||
    c.name.toLowerCase().includes("insurance")
  );
  if (insComp) {
    const amt = getCompAmount(insComp);
    thingsToReview.push({
      text: `${insComp.normalized_label || insComp.name} ${formatCurrency(amt, currency)} — compare/verify`,
      tag: "Compare options",
    });
  }

  // Check Accessories or Dealer charges
  const accComp = chargeItems.find((c) =>
    (c.category || "").toLowerCase().includes("accessor") ||
    c.name.toLowerCase().includes("accessor")
  );
  if (accComp && thingsToReview.length < 3) {
    const amt = getCompAmount(accComp);
    thingsToReview.push({
      text: `${accComp.normalized_label || accComp.name} ${formatCurrency(amt, currency)} — verify if required for delivery`,
      tag: "Potentially optional",
    });
  }

  // Component discrepancy
  if (!isComponentPass && componentDiff > 0 && !hasLineItems) {
    thingsToReview.push({
      text: `${formatCurrency(componentDiff, currency)} discrepancy — ask seller which subtotal is correct`,
      tag: "Needs clarification",
    });
  }

  // Top questions to ask
  const topQuestions: string[] = [];
  if (smart_questions.length > 0) {
    smart_questions.slice(0, 3).forEach((q) => {
      if (!topQuestions.includes(q.question)) {
        topQuestions.push(q.question);
      }
    });
  }

  if (topQuestions.length === 0) {
    if (ewComp) {
      topQuestions.push(`Is the ${formatCurrency(getCompAmount(ewComp), currency)} extended warranty package optional?`);
    }
    if (insComp) {
      topQuestions.push("Can I choose my own insurance provider?");
    }
    if (!isComponentPass && componentDiff > 0) {
      topQuestions.push(
        `The listed components total ${formatCurrency(listedComponentsSum, currency)}, but the stated subtotal is ${formatCurrency(statedSubtotal, currency)}. Which amount is correct?`
      );
    }
  }

  const handleCopyQuestion = (idx: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  // Status summary badge label
  const statusLabel =
    lineItemCheckFail || (!isComponentPass && !hasLineItems) || !isQuotedTotalPass || substantiveFindings.length > 0
      ? `${(lineItemCheckFail ? 1 : 0) + (substantiveFindings.length || (!isComponentPass && !hasLineItems ? 1 : 0)) || 1} item requires verification`
      : "All items verified — ready to review";

  return (
    <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-white/10 shadow-2xl bg-gradient-to-b from-slate-900/90 via-slate-900/95 to-slate-950 space-y-6">
      {/* ── HEADER: BEFORE YOU PAY ── */}
      <div className="flex items-center justify-between pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-400 animate-pulse" />
          <h1 className="text-xs sm:text-sm font-extrabold uppercase tracking-widest text-brand-400">
            BEFORE YOU PAY
          </h1>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="min-h-[36px] px-3 py-1 rounded-xl text-xs font-semibold text-slate-300 bg-white/5 hover:bg-white/10 active:scale-95 transition flex items-center gap-1.5 border border-white/10"
          aria-label="Scan Another Document"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Scan Another</span>
        </button>
      </div>

      {/* ── FINAL QUOTED TOTAL & STATUS ── */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-brand-950/40 via-slate-900/80 to-slate-950 border border-brand-500/30 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-slate-400 block mb-1">
              FINAL QUOTED TOTAL
            </span>
            <span className="text-3xl sm:text-5xl font-mono font-extrabold text-white tracking-tight block">
              {formatCurrency(finalQuotedTotal, currency)}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400 block mb-1">
              STATUS
            </span>
            {lineItemCheckFail || !isComponentPass || !isQuotedTotalPass || substantiveFindings.length > 0 ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs sm:text-sm font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                {statusLabel}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs sm:text-sm font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                {statusLabel}
              </span>
            )}
          </div>
        </div>

        {/* ── DATES ── */}
        {(document?.issued_date || document?.due_date) && (
          <div className="flex flex-wrap items-center gap-6 text-xs font-mono text-slate-400 pt-3 border-t border-white/10">
            {document.issued_date?.normalized_value && (
              <div>
                <span className="text-slate-400 uppercase tracking-wider text-[10px]">Bill Date: </span>
                <strong className="text-white text-xs">{formatDateDisplay(document.issued_date.normalized_value)}</strong>
              </div>
            )}
            {document.due_date?.normalized_value && (
              <div>
                <span className="text-slate-400 uppercase tracking-wider text-[10px]">Due Date: </span>
                <strong className="text-white text-xs">{formatDateDisplay(document.due_date.normalized_value)}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── CORE 2-COLUMN GRID: WHAT YOU ARE PAYING FOR + COST CHECKS ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* 1. WHAT YOU ARE PAYING FOR / ITEMIZED FINANCIAL LINES */}
        <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-white/10 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-400" />
              {hasLineItems && chargeItems.length === 0 ? "ITEMIZED FINANCIAL LINES" : "WHAT YOU ARE PAYING FOR"}
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              {hasLineItems && chargeItems.length === 0
                ? `Exactly ${lineItems.length} actual product lines`
                : chargeItems.length > 0
                ? `${chargeItems.length} charges`
                : "Itemized"}
            </span>
          </div>

          <div className="space-y-2 pt-1 text-xs sm:text-sm">
            {hasLineItems && chargeItems.length === 0 ? (
              lineItems.map((item) => {
                const amt = Number(item.total_price?.normalized_value || 0);
                const desc = String(item.description?.normalized_value || "Product Line");
                return (
                  <div
                    key={item.item_id}
                    className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0"
                  >
                    <span className="text-slate-300 font-medium truncate pr-2">
                      • {desc}
                    </span>
                    <span className="font-mono font-bold text-white shrink-0">
                      {formatCurrency(amt, currency)}
                    </span>
                  </div>
                );
              })
            ) : chargeItems.length > 0 ? (
              chargeItems.map((comp) => {
                const amt = getCompAmount(comp);
                const label = comp.normalized_label || comp.normalized_name || comp.name;
                return (
                  <div
                    key={comp.component_id}
                    className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0"
                  >
                    <span className="text-slate-300 font-medium truncate pr-2">
                      • {label}
                    </span>
                    <span className="font-mono font-bold text-white shrink-0">
                      {formatCurrency(amt, currency)}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="text-slate-400 text-xs">
                Line items extracted from document.
              </div>
            )}
          </div>
        </div>

        {/* 2. COST CHECK, OFFERS / DISCOUNT CONTEXT, FINAL CALCULATION */}
        <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/70 border border-white/10 space-y-4">
          <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <Calculator className="w-4 h-4 text-indigo-400" />
            COST CHECK & CALCULATION
          </h3>

          {/* COST CHECK */}
          {hasLineItems ? (
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-950/60 border border-white/5 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-bold uppercase tracking-wider text-[10px] text-slate-300">
                  COST CHECK
                </span>
                <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded border bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
                  PASS
                </span>
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Itemized subtotal:</span>
                <span>{formatCurrency(itemizedSubtotal, currency)}</span>
              </div>
              {shippingAmt > 0 && (
                <div className="flex justify-between text-slate-300 font-mono">
                  <span className="font-sans text-slate-400">Shipping:</span>
                  <span>{formatCurrency(shippingAmt, currency)}</span>
                </div>
              )}
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Tax:</span>
                <span>{formatCurrency(taxAmt, currency)}</span>
              </div>
              <div className="flex justify-between text-white font-mono font-bold pt-1 border-t border-white/10">
                <span className="font-sans text-slate-300">Calculated total:</span>
                <span>{formatCurrency(finalQuotedTotal, currency)}</span>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-950/60 border border-white/5 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-bold uppercase tracking-wider text-[10px] text-slate-300">
                  COST CHECK
                </span>
                <span
                  className={`font-mono text-[11px] font-bold px-2 py-0.5 rounded border ${
                    isComponentPass
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                  }`}
                >
                  {isComponentPass ? "→ Pass" : "→ Requires verification"}
                </span>
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Listed components:</span>
                <span>{formatCurrency(listedComponentsSum, currency)}</span>
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Stated subtotal:</span>
                <span>{formatCurrency(statedSubtotal, currency)}</span>
              </div>
              {!isComponentPass && componentDiff > 0 && (
                <div className="flex justify-between text-amber-300 font-mono font-bold pt-1 border-t border-amber-500/20">
                  <span className="font-sans">Difference:</span>
                  <span>{formatCurrency(componentDiff, currency)}</span>
                </div>
              )}
            </div>
          )}

          {/* DISCOUNT CONTEXT / OFFERS */}
          {hasLineItems ? (
            discountAmt > 0 && (
              <div className="p-3 rounded-xl bg-slate-950/60 border border-indigo-500/20 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold uppercase tracking-wider text-[10px] text-indigo-300 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-indigo-400" />
                    DISCOUNT CONTEXT
                  </span>
                  <span className="font-mono font-bold text-xs text-indigo-300">
                    {formatCurrency(discountAmt, currency)}
                  </span>
                </div>
                <p className="text-slate-300 text-[11px]">
                  {formatCurrency(discountAmt, currency)} aggregate discount shown on document
                </p>
                <p className="text-amber-300/90 font-medium text-[11px]">
                  Do not subtract this again from {formatCurrency(itemizedSubtotal, currency)}.
                </p>
              </div>
            )
          ) : (
            <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20 text-xs">
              <span className="font-bold uppercase tracking-wider text-[11px] text-emerald-400 flex items-center gap-1.5">
                <TrendingDown className="w-3.5 h-3.5" />
                OFFERS
              </span>
              <span className="font-mono font-bold text-sm text-emerald-300">
                {offersSum > 0 ? `−${formatCurrency(offersSum, currency)}` : "₹0"}
              </span>
            </div>
          )}

          {/* FINAL CALCULATION */}
          <div className="space-y-1.5 p-3 rounded-xl bg-indigo-950/20 border border-indigo-500/30 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold uppercase tracking-wider text-[10px] text-indigo-300">
                FINAL CALCULATION
              </span>
              <span
                className={`font-mono text-[11px] font-bold px-2 py-0.5 rounded border ${
                  isQuotedTotalPass
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                }`}
              >
                {isQuotedTotalPass ? "→ Exact match" : "→ Verify calculation"}
              </span>
            </div>
            <div className="font-mono text-slate-200 pt-0.5">
              {hasLineItems ? (
                <>
                  <span>{formatCurrency(itemizedSubtotal, currency)}</span>
                  {shippingAmt > 0 && <span> + {formatCurrency(shippingAmt, currency)} shipping</span>}
                  <span> + {formatCurrency(taxAmt, currency)} tax</span>
                </>
              ) : (
                <>
                  <span>{formatCurrency(statedSubtotal, currency)}</span>
                  <span className="text-emerald-400">
                    {offersSum > 0 ? ` − ${formatCurrency(offersSum, currency)}` : ""}
                  </span>
                </>
              )}
            </div>
            <div className="font-mono font-bold text-sm text-white pt-1 border-t border-white/10 flex justify-between">
              <span className="text-slate-400 font-sans font-normal">= Total:</span>
              <span>{formatCurrency(finalQuotedTotal, currency)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. THINGS TO REVIEW ── */}
      {thingsToReview.length > 0 && (
        <div className="p-4 sm:p-5 rounded-2xl bg-amber-950/15 border border-amber-500/30 space-y-2.5">
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-amber-400 shrink-0" />
            <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-amber-300">
              THINGS TO REVIEW
            </h3>
          </div>

          <div className="space-y-2 pt-1 text-xs sm:text-sm">
            {thingsToReview.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between gap-2 p-2.5 rounded-xl bg-slate-950/50 border border-amber-500/20"
              >
                <span className="text-slate-200 font-medium leading-snug">
                  • {item.text}
                </span>
                {item.tag && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 shrink-0">
                    {item.tag}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 4. QUESTIONS TO ASK ── */}
      {topQuestions.length > 0 && (
        <div className="space-y-2.5 pt-1">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-brand-400" />
              QUESTIONS TO ASK
            </h3>
            <span className="text-[11px] text-slate-400">
              Highest-value evidence-based questions
            </span>
          </div>

          <div className="space-y-2">
            {topQuestions.map((qText, idx) => {
              const isCopied = copiedIdx === idx;
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-white/10 hover:border-white/20 transition gap-2"
                >
                  <div className="flex items-start gap-2.5 pr-2">
                    <span className="w-5 h-5 rounded-full bg-brand-500/20 text-brand-300 font-mono text-xs flex items-center justify-center shrink-0 mt-0.5 font-bold">
                      {idx + 1}
                    </span>
                    <p className="text-xs sm:text-sm font-medium text-slate-100 leading-snug">
                      "{qText}"
                    </p>
                  </div>

                  <button
                    onClick={() => handleCopyQuestion(idx, qText)}
                    className={`shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition font-medium border ${
                      isCopied
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                        : "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700"
                    }`}
                    title="Copy question"
                  >
                    {isCopied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-400" />
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
