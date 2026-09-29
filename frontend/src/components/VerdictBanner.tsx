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
  ChevronDown,
  ChevronUp,
  FileText,
  MessageSquare,
  FileCheck,
  PlusCircle,
} from "lucide-react";
import {
  FinalDecisionSupportResult,
  FinancialComponent,
  SmartCostReductionQuestion,
} from "../lib/types";
import { formatCurrency } from "../lib/utils";
import { StatusBadge, FinancialValue, Button } from "./ui";
import { BeforeYouPayFinalSummaryView } from "./BeforeYouPayFinalSummaryView";

interface VerdictBannerProps {
  result: FinalDecisionSupportResult;
  onReset: () => void;
  onSelectComponent?: (comp: FinancialComponent) => void;
  onSelectLineItem?: (item: any) => void;
  onAddSupportingDocument?: (file: File) => void;
}

export const VerdictBanner: React.FC<VerdictBannerProps> = ({
  result,
  onReset,
  onSelectComponent,
  onSelectLineItem,
  onAddSupportingDocument,
}) => {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [isExplanationOpen, setIsExplanationOpen] = useState<boolean>(false);
  const [copiedExplanation, setCopiedExplanation] = useState<boolean>(false);
  const [copiedMessage, setCopiedMessage] = useState<boolean>(false);

  const defaultDraft =
    result.suggested_negotiation_message ||
    result.plain_language_explanation?.suggested_message ||
    "";
  const [draftMessage, setDraftMessage] = useState<string>(defaultDraft);
  const supportingFileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    setDraftMessage(
      result.suggested_negotiation_message ||
        result.plain_language_explanation?.suggested_message ||
        ""
    );
  }, [result]);

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

  // Check Line Item discrepancy
  if (lineItemCheckFail) {
    const failedItem = lineItems.find((li) =>
      lineItemCheckFail.message?.includes(String(li.description?.normalized_value))
    );
    const itemName = failedItem?.description?.normalized_value || "Line item";
    const itemAmt = failedItem ? formatCurrency(Number(failedItem.total_price?.normalized_value || 0), currency) : "";
    thingsToReview.push({
      text: `${itemName}${itemAmt ? ` — displayed values do not mathematically explain ${itemAmt}` : " — calculation requires verification"}`,
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
  const activeQuestions: SmartCostReductionQuestion[] = [];
  if (smart_questions.length > 0) {
    const seenQ = new Set<string>();
    smart_questions.forEach((q) => {
      if (!seenQ.has(q.question)) {
        seenQ.add(q.question);
        activeQuestions.push(q);
      }
    });
  }

  if (activeQuestions.length === 0) {
    if (ewComp) {
      activeQuestions.push({
        question_id: "fallback-ew",
        question: `Is the ${formatCurrency(getCompAmount(ewComp), currency)} extended warranty package optional?`,
        reason: "Extended warranty listed as a separate line item.",
        related_charge: ewComp.name,
        amount_involved: getCompAmount(ewComp),
        potential_impact: `Potential amount to review: ${formatCurrency(getCompAmount(ewComp), currency)} if optional.`,
        evidence_source: ewComp.evidence || ewComp.name,
        confidence: 0.9,
        priority_score: 0.9,
        classification: "POTENTIALLY_OPTIONAL",
        suggested_action: "Ask whether the item can be removed or declined.",
      });
    }
    if (insComp) {
      activeQuestions.push({
        question_id: "fallback-ins",
        question: "Can I choose my own insurance provider or policy?",
        reason: "Dealer insurance line item present.",
        related_charge: insComp.name,
        amount_involved: getCompAmount(insComp),
        potential_impact: "Potential amount to review upon independent market comparison.",
        evidence_source: insComp.evidence || insComp.name,
        confidence: 0.9,
        priority_score: 0.85,
        classification: "ALTERNATIVE_AVAILABLE",
        suggested_action: "Ask for alternative products/services/pricing.",
      });
    }
    if (!isComponentPass && componentDiff > 0) {
      activeQuestions.push({
        question_id: "fallback-disc",
        question: `The listed components total ${formatCurrency(listedComponentsSum, currency)}, but the stated subtotal is ${formatCurrency(statedSubtotal, currency)}. Which amount is correct?`,
        reason: "Discrepancy between listed charges and stated subtotal.",
        related_charge: "Subtotal discrepancy",
        amount_involved: componentDiff,
        potential_impact: `Potential amount to review: ${formatCurrency(componentDiff, currency)} discrepancy.`,
        evidence_source: "Subtotal consistency check",
        confidence: 0.95,
        priority_score: 0.95,
        classification: "INCONSISTENT",
        suggested_action: "Ask the provider to explain/reconcile the difference.",
      });
    }
  }

  const topQuestions = activeQuestions.slice(0, 5);

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
    <div className="rounded-2xl border border-white/10 bg-app-card p-5 sm:p-7 shadow-card space-y-6">
      {/* ── HEADER: BEFORE YOU PAY ── */}
      <div className="flex items-center justify-between pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-400" />
          <h1 className="text-xs sm:text-sm font-extrabold uppercase tracking-widest text-brand-400">
            BEFORE YOU PAY
          </h1>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={onReset}
          aria-label="Scan Another Document"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Scan Another</span>
        </Button>
      </div>

      {/* ── PHASE 6: BEFORE YOU PAY FINAL DECISION SUMMARY ── */}
      {result.before_you_pay_summary ? (
        <BeforeYouPayFinalSummaryView
          summary={result.before_you_pay_summary}
          result={result}
          evidenceResult={result.evidence_first_result}
          onReset={onReset}
          onSelectComponent={onSelectComponent}
          onSelectLineItem={onSelectLineItem}
          onAddSupportingDocument={onAddSupportingDocument}
        />
      ) : (
        <>
          {/* ── FINAL QUOTED TOTAL & STATUS ── */}
          <div className="p-5 rounded-xl bg-app-cardSubtle border border-white/8 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-slate-400 block mb-1">
              FINAL QUOTED TOTAL
            </span>
            <FinancialValue
              amount={finalQuotedTotal}
              currency={currency}
              variant="hero"
            />
          </div>

          <div>
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400 block mb-1">
              STATUS
            </span>
            <StatusBadge
              status={
                lineItemCheckFail || !isComponentPass || !isQuotedTotalPass || substantiveFindings.length > 0
                  ? "REQUIRES_VERIFICATION"
                  : "PASS"
              }
              label={statusLabel}
              size="md"
            />
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

      {/* ── PLAIN-LANGUAGE EXPLANATION TOGGLE (INTEGRATED) ── */}
      {result?.plain_language_explanation && (
        <div className="rounded-2xl border border-indigo-500/25 bg-indigo-950/20 overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => setIsExplanationOpen(!isExplanationOpen)}
            className="w-full p-3.5 sm:p-4 flex items-center justify-between text-left hover:bg-white/5 transition"
            aria-expanded={isExplanationOpen}
          >
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-indigo-400 shrink-0" />
              <div>
                <span className="text-xs sm:text-sm font-bold text-white block">
                  Plain-Language Summary
                </span>
                <span className="text-[11px] text-slate-300 line-clamp-1">
                  {result.plain_language_explanation.quoted_amount_sentence}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-mono font-semibold text-indigo-300 hidden sm:inline">
                {isExplanationOpen ? "Hide explanation" : "Read explanation"}
              </span>
              {isExplanationOpen ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </div>
          </button>

          {isExplanationOpen && (
            <div className="p-4 pt-1 border-t border-indigo-500/20 space-y-3 text-xs sm:text-sm animate-in fade-in duration-200">
              <div className="space-y-2 pt-2">
                {result.plain_language_explanation.base_price_sentence && (
                  <div className="flex items-start gap-2 text-slate-200">
                    <span className="text-slate-400 shrink-0">•</span>
                    <span>{result.plain_language_explanation.base_price_sentence}</span>
                  </div>
                )}
                {result.plain_language_explanation.charge_breakdown_sentences?.map((s, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-slate-200">
                    <span className="text-sky-400 shrink-0">•</span>
                    <span>{s}</span>
                  </div>
                ))}
                {result.plain_language_explanation.offers_sentence && (
                  <div className="flex items-start gap-2 text-emerald-300 font-medium">
                    <span className="text-emerald-400 shrink-0">•</span>
                    <span>{result.plain_language_explanation.offers_sentence}</span>
                  </div>
                )}
                {result.plain_language_explanation.discrepancy_sentence && (
                  <div className="flex items-start gap-2 text-amber-300 font-medium">
                    <span className="text-amber-400 shrink-0">⚠️</span>
                    <span>{result.plain_language_explanation.discrepancy_sentence}</span>
                  </div>
                )}
              </div>

              {result.plain_language_explanation.clarification_items?.length > 0 && (
                <div className="pt-2 border-t border-white/10 space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    {result.plain_language_explanation.clarification_heading || "Questions to Clarify"}
                  </span>
                  {result.plain_language_explanation.clarification_items.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-slate-300">
                      <span className="text-cyan-400 shrink-0">?</span>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={async () => {
                    if (result.plain_language_explanation?.full_explanation) {
                      await navigator.clipboard.writeText(result.plain_language_explanation.full_explanation);
                      setCopiedExplanation(true);
                      setTimeout(() => setCopiedExplanation(false), 2000);
                    }
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10"
                >
                  {copiedExplanation ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-400" />
                      <span>Copy Explanation</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── CORE 2-COLUMN GRID: WHAT YOU ARE PAYING FOR + COST CHECKS ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* 1. WHAT YOU ARE PAYING FOR / ITEMIZED FINANCIAL LINES */}
        <div className="p-4 sm:p-5 rounded-xl bg-app-cardSubtle border border-white/8 space-y-3">
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
                    onClick={() => onSelectLineItem && onSelectLineItem(item)}
                    className={`flex items-center justify-between py-1.5 border-b border-white/5 last:border-0 ${
                      onSelectLineItem ? "cursor-pointer hover:bg-white/5 rounded px-1 transition" : ""
                    }`}
                  >
                    <span className="text-slate-300 font-medium truncate pr-2">
                      • {desc}
                    </span>
                    <FinancialValue
                      amount={amt}
                      currency={currency}
                      variant="item"
                      className="shrink-0"
                    />
                  </div>
                );
              })
            ) : chargeItems.length > 0 ? (
              chargeItems.map((comp) => {
                const amt = getCompAmount(comp);
                const label = comp.normalized_label || comp.normalized_name || comp.name;
                const freq = comp.billing_frequency;
                const optDisp = comp.optionality_display || comp.charge_status_display;
                return (
                  <div
                    key={comp.component_id}
                    onClick={() => onSelectComponent && onSelectComponent(comp)}
                    className={`flex items-center justify-between py-1.5 border-b border-white/5 last:border-0 ${
                      onSelectComponent ? "cursor-pointer hover:bg-white/5 rounded px-1 transition" : ""
                    }`}
                  >
                    <div className="flex items-center gap-1.5 truncate pr-2">
                      <span className="text-slate-300 font-medium truncate">
                        • {label}
                      </span>
                      {freq && (
                        <span className="text-[10px] px-1 py-0.2 rounded bg-indigo-500/10 text-indigo-300 font-mono">
                          {freq}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {optDisp && !optDisp.toLowerCase().includes("mandatory") && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                          {optDisp.replace("Status: ", "")}
                        </span>
                      )}
                      <FinancialValue
                        amount={amt}
                        currency={currency}
                        variant="item"
                        className="shrink-0"
                      />
                    </div>
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
        <div className="p-4 sm:p-5 rounded-xl bg-app-cardSubtle border border-white/8 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Calculator className="w-4 h-4 text-indigo-400" />
              COST CHECK & CALCULATION
            </h3>
            {result.semantic_financial_structure?.formula_representation && (
              <span className="text-[10px] text-slate-400 font-mono hidden sm:inline-block max-w-[200px] truncate" title={result.semantic_financial_structure.formula_representation}>
                {result.semantic_financial_structure.formula_representation}
              </span>
            )}
          </div>

          {/* COST CHECK */}
          {hasLineItems ? (
            <div className="space-y-1.5 p-3 rounded-lg bg-app-cardInset border border-white/4 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-bold uppercase tracking-wider text-[10px] text-slate-300">
                  COST CHECK
                </span>
                <StatusBadge
                  status={lineItemCheckFail ? "REQUIRES_VERIFICATION" : "PASS"}
                  label={lineItemCheckFail ? "Requires verification" : "Pass"}
                  size="sm"
                />
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Itemized subtotal:</span>
                <FinancialValue amount={itemizedSubtotal} currency={currency} variant="item" />
              </div>
              {shippingAmt > 0 && (
                <div className="flex justify-between text-slate-300 font-mono">
                  <span className="font-sans text-slate-400">Shipping:</span>
                  <FinancialValue amount={shippingAmt} currency={currency} variant="item" />
                </div>
              )}
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Tax:</span>
                <FinancialValue amount={taxAmt} currency={currency} variant="item" />
              </div>
              <div className="flex justify-between text-white font-mono font-bold pt-1 border-t border-white/10">
                <span className="font-sans text-slate-300">Calculated total:</span>
                <FinancialValue amount={finalQuotedTotal} currency={currency} variant="item" className="font-bold text-white" />
              </div>
            </div>
          ) : (
            <div className="space-y-1.5 p-3 rounded-lg bg-app-cardInset border border-white/4 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span className="font-bold uppercase tracking-wider text-[10px] text-slate-300">
                  1. COMPONENT RECONCILIATION
                </span>
                <StatusBadge
                  status={isComponentPass ? "PASS" : "REQUIRES_VERIFICATION"}
                  label={isComponentPass ? "Pass" : "Requires verification"}
                  size="sm"
                />
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Listed components:</span>
                <FinancialValue amount={listedComponentsSum} currency={currency} variant="item" />
              </div>
              <div className="flex justify-between text-slate-300 font-mono">
                <span className="font-sans text-slate-400">Stated subtotal:</span>
                <FinancialValue amount={statedSubtotal} currency={currency} variant="item" />
              </div>
              {!isComponentPass && componentDiff > 0 && (
                <div className="flex justify-between text-amber-300 font-mono font-bold pt-1 border-t border-amber-500/20">
                  <span className="font-sans">Difference:</span>
                  <FinancialValue amount={componentDiff} currency={currency} variant="discrepancy" />
                </div>
              )}
            </div>
          )}

          {/* DISCOUNT CONTEXT / OFFERS */}
          {hasLineItems ? (
            discountAmt > 0 && (
              <div className="p-3 rounded-lg bg-app-cardInset border border-indigo-500/20 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold uppercase tracking-wider text-[10px] text-indigo-300 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-indigo-400" />
                    DISCOUNT CONTEXT
                  </span>
                  <FinancialValue amount={discountAmt} currency={currency} variant="deduction" />
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
            <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20 text-xs">
              <span className="font-bold uppercase tracking-wider text-[11px] text-emerald-400 flex items-center gap-1.5">
                <TrendingDown className="w-3.5 h-3.5" />
                OFFERS / DISCOUNTS
              </span>
              <FinancialValue
                amount={offersSum}
                currency={currency}
                variant="deduction"
                fallbackText="₹0"
              />
            </div>
          )}

          {/* FINAL CALCULATION / QUOTED-TOTAL RECONCILIATION */}
          <div className="space-y-1.5 p-3 rounded-lg bg-app-cardInset border border-white/6 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold uppercase tracking-wider text-[10px] text-indigo-300">
                {hasLineItems ? "FINAL CALCULATION" : "2. QUOTED-TOTAL RECONCILIATION"}
              </span>
              <StatusBadge
                status={isQuotedTotalPass ? "PASS" : "REQUIRES_VERIFICATION"}
                label={isQuotedTotalPass ? "Exact match" : "Verify calculation"}
                size="sm"
              />
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
              <FinancialValue amount={finalQuotedTotal} currency={currency} variant="item" className="font-bold text-white text-sm" />
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
              Evidence-backed discovery questions
            </span>
          </div>

          <div className="space-y-2.5">
            {topQuestions.map((q, idx) => {
              const isCopied = copiedIdx === idx;
              const qText = q.question;
              const action = q.suggested_action;
              const evidence = q.ocr_line || q.evidence_source;
              const classification = q.classification;

              return (
                <div
                  key={q.question_id || idx}
                  className="p-3.5 rounded-xl bg-slate-900/80 border border-white/10 hover:border-white/20 transition space-y-2"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <span className="w-5 h-5 rounded-full bg-brand-500/20 text-brand-300 font-mono text-xs flex items-center justify-center shrink-0 mt-0.5 font-bold">
                        {idx + 1}
                      </span>
                      <div className="space-y-1">
                        <p className="text-xs sm:text-sm font-medium text-slate-100 leading-snug">
                          &ldquo;{qText}&rdquo;
                        </p>
                        {action && (
                          <div className="flex items-center gap-1.5 text-[11px] text-brand-300 font-medium pt-0.5">
                            <span className="px-1.5 py-0.5 rounded bg-brand-500/15 border border-brand-500/25 text-[10px] uppercase tracking-wider font-semibold">
                              Action
                            </span>
                            <span>{action}</span>
                          </div>
                        )}
                        {evidence && (
                          <p className="text-[10px] text-slate-400 font-mono truncate max-w-xl">
                            Source: {evidence}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {classification && (
                        <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                          {classification.replace(/_/g, " ")}
                        </span>
                      )}
                      <button
                        onClick={() => handleCopyQuestion(idx, qText)}
                        className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition font-medium border ${
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
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 5. SUGGESTED NEGOTIATION MESSAGE ── */}
      {draftMessage && (
        <div className="p-4 sm:p-5 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-indigo-400 shrink-0" />
              <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-indigo-300">
                SUGGESTED NEGOTIATION MESSAGE
              </h3>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
              User-Editable Draft
            </span>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            A polite, evidence-grounded draft generated from actual document findings. You can edit this directly before copying.
          </p>

          <div className="space-y-2">
            <textarea
              value={draftMessage}
              onChange={(e) => setDraftMessage(e.target.value)}
              rows={4}
              className="w-full text-xs sm:text-sm p-3 rounded-xl bg-slate-950/80 border border-indigo-500/20 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-400 font-sans leading-relaxed resize-y"
              aria-label="Suggested draft message"
            />

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
              <span className="text-[10px] text-slate-500 italic">
                * Before You Pay helps you question and understand charges. You remain the final decision-maker.
              </span>

              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(draftMessage);
                  setCopiedMessage(true);
                  setTimeout(() => setCopiedMessage(false), 2000);
                }}
                className={`self-end sm:self-auto flex items-center gap-1.5 text-xs px-3.5 py-1.5 rounded-lg transition font-medium border ${
                  copiedMessage
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                    : "bg-indigo-600/30 hover:bg-indigo-600/40 text-indigo-200 border-indigo-500/40"
                }`}
              >
                {copiedMessage ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Copied Draft</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-indigo-300" />
                    <span>Copy Draft Message</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )}

      {/* ── 6. SECOND SCAN & CONTEXTUAL COMPARISON ── */}
      <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/60 border border-white/10 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <h3 className="text-xs sm:text-sm font-extrabold uppercase tracking-wider text-slate-200">
              SECOND SCAN &amp; SUPPORTING CONTEXT
            </h3>
          </div>
          {result.supporting_document_context && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              Supporting Record Active
            </span>
          )}
        </div>

        {result.supporting_document_context ? (
          <div className="space-y-2.5 text-xs sm:text-sm">
            {/* Supporting doc metadata */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-emerald-500/20 text-slate-300 space-y-1">
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-300">
                <span>
                  Supporting Document
                  {result.supporting_document_analysis?.supporting_document_type
                    ? ` · ${result.supporting_document_analysis.supporting_document_type.charAt(0).toUpperCase() + result.supporting_document_analysis.supporting_document_type.slice(1)}`
                    : ""}
                </span>
                <span className="font-mono text-[10px] text-slate-400 uppercase">
                  {result.supporting_document_context.source_type || "Context"}
                </span>
              </div>
              {result.supporting_document_analysis && (
                <div className="text-[11px] text-slate-400 space-y-0.5 pt-0.5">
                  <p>
                    {result.supporting_document_analysis.supporting_line_count} lines scanned ·{" "}
                    {result.supporting_document_analysis.chunks_indexed} chunks indexed ·{" "}
                    {result.supporting_document_analysis.retrieved_chunks_count} retrieved for comparison
                  </p>
                  {result.supporting_document_analysis.supporting_preview && (
                    <p className="italic text-slate-500 line-clamp-2">
                      &ldquo;{result.supporting_document_analysis.supporting_preview}&rdquo;
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Contextual findings from Phase 2 comparison */}
            {(result.contextual_findings && result.contextual_findings.length > 0) ||
            (result.supporting_document_analysis?.findings && result.supporting_document_analysis.findings.length > 0) ? (
              <div className="space-y-2">
                <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider block">
                  CONTEXTUAL FINDINGS ({(result.contextual_findings?.length || 0) + (result.supporting_document_analysis?.findings?.length || 0)} identified)
                </span>
                {[
                  ...(result.contextual_findings || []),
                  ...(result.supporting_document_analysis?.findings || []),
                ]
                  // Deduplicate by finding_id
                  .filter((f, i, arr) => arr.findIndex((x) => x.finding_id === f.finding_id) === i)
                  .map((finding, idx) => (
                    <div
                      key={finding.finding_id || idx}
                      className={`p-3 rounded-xl border space-y-1.5 text-xs ${
                        finding.finding_type === "PRICE_VARIANCE"
                          ? "bg-orange-950/20 border-orange-500/30"
                          : finding.finding_type === "POTENTIAL_OVERLAP"
                          ? "bg-amber-950/20 border-amber-500/30"
                          : "bg-slate-950/40 border-white/10"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-bold text-slate-200 leading-tight">{finding.title}</span>
                        <span
                          className={`shrink-0 text-[9px] font-mono px-1.5 py-0.5 rounded uppercase ${
                            finding.finding_type === "PRICE_VARIANCE"
                              ? "bg-orange-500/15 text-orange-300"
                              : finding.finding_type === "POTENTIAL_OVERLAP"
                              ? "bg-amber-500/15 text-amber-300"
                              : "bg-slate-700/60 text-slate-300"
                          }`}
                        >
                          {finding.finding_type.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">{finding.description}</p>

                      {finding.primary_amount != null && finding.supporting_amount != null && (
                        <div className="flex items-center gap-3 pt-0.5 text-[11px] font-mono">
                          <span className="text-slate-400">
                            Primary:{" "}
                            <span className="text-slate-200">
                              {formatCurrency(finding.primary_amount)}
                            </span>
                          </span>
                          <span className="text-slate-600">vs</span>
                          <span className="text-slate-400">
                            Supporting:{" "}
                            <span className="text-slate-200">
                              {formatCurrency(finding.supporting_amount)}
                            </span>
                          </span>
                          {finding.delta_amount != null && finding.delta_amount > 0 && (
                            <span className="text-orange-300">
                              Δ {formatCurrency(finding.delta_amount)}
                            </span>
                          )}
                        </div>
                      )}

                      {finding.what_to_verify && finding.what_to_verify.length > 0 && (
                        <div className="pt-0.5">
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                            VERIFY
                          </p>
                          <ul className="space-y-0.5 text-slate-400">
                            {finding.what_to_verify.map((item, i) => (
                              <li key={i} className="leading-relaxed">
                                • {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {finding.questions_to_ask && finding.questions_to_ask.length > 0 && (
                        <div className="pt-0.5">
                          <p className="text-[10px] font-bold text-blue-400 uppercase tracking-wider mb-1">
                            ASK THE SELLER
                          </p>
                          <ul className="space-y-0.5 text-blue-300">
                            {finding.questions_to_ask.map((q, i) => (
                              <li key={i} className="italic leading-relaxed">
                                &ldquo;{q}&rdquo;
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="flex items-center gap-2 pt-0.5">
                        <div className="flex-1 bg-slate-700/40 rounded-full h-1">
                          <div
                            className="h-1 rounded-full bg-emerald-500/60"
                            style={{ width: `${Math.round(finding.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {Math.round(finding.confidence * 100)}% match
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            ) : (result.reasoning_claims || []).filter((c) => c.type === "potential_overlap").length > 0 ? (
              <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-1.5 text-xs">
                <span className="font-bold text-amber-300 uppercase tracking-wider text-[10px] block">
                  POTENTIAL COVERAGE OVERLAP DETECTED
                </span>
                {(result.reasoning_claims || [])
                  .filter((c) => c.type === "potential_overlap")
                  .map((claim, idx) => (
                    <p key={idx} className="text-slate-200 leading-relaxed">
                      • {claim.description}
                    </p>
                  ))}
              </div>
            ) : (
              <div className="p-2.5 rounded-xl bg-slate-950/40 border border-white/5 text-slate-400 text-xs">
                No contradictory terms or duplicate charges detected between primary and supporting documents.
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-950/40 border border-white/5">
            <div className="text-xs text-slate-400 space-y-0.5">
              <p className="text-slate-200 font-medium">
                Cross-reference an existing warranty, insurance, or prior quote?
              </p>
              <p className="text-[11px] text-slate-400">
                Upload a secondary document to check for coverage overlaps before you pay.
              </p>
            </div>

            <input
              type="file"
              ref={supportingFileInputRef}
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0] && onAddSupportingDocument) {
                  onAddSupportingDocument(e.target.files[0]);
                }
              }}
            />

            <button
              type="button"
              onClick={() => supportingFileInputRef.current?.click()}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-slate-200 hover:text-white border border-white/10 text-xs font-semibold transition"
            >
              <PlusCircle className="w-3.5 h-3.5 text-brand-400" />
              <span>+ Add Supporting Document</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
