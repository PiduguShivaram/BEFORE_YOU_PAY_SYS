"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  HelpCircle,
  Calculator,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Copy,
  Check,
  FileText,
  MessageSquare,
  Sparkles,
  TrendingDown,
  Info,
  ExternalLink,
  ClipboardList,
  RotateCcw,
  Upload,
  Plus,
  ChevronDown,
  ChevronUp,
  Eye,
  FileSearch,
  AlertCircle,
  FileCheck,
} from "lucide-react";
import {
  BeforeYouPayFinalSummary,
  FinalDecisionSupportResult,
  EvidenceFirstResult,
  FindingExplanation,
  DecisionFlag,
  FinancialComponent,
  SupportingDocComparison,
  BeforeYouPayChecklistItem,
} from "../lib/types";
import { StatusBadge } from "./ui";
import { EvidencePanel } from "./EvidencePanel";
import { MathVerification } from "./MathVerification";
import { DocumentViewer } from "./DocumentViewer";
import { formatCurrency } from "../lib/utils";

interface BeforeYouPayFinalSummaryViewProps {
  summary: BeforeYouPayFinalSummary;
  result?: FinalDecisionSupportResult | null;
  evidenceResult?: EvidenceFirstResult | null;
  imagePreviewUrl?: string | null;
  documentText?: string;
  onReset?: () => void;
  onAddSupportingDocument?: (file: File) => void;
  onSelectComponent?: (comp: FinancialComponent) => void;
  onSelectLineItem?: (item: any) => void;
  onInspectFieldId?: (fieldId: string, label?: string) => void;
}

export const BeforeYouPayFinalSummaryView: React.FC<BeforeYouPayFinalSummaryViewProps> = ({
  summary,
  result,
  evidenceResult,
  imagePreviewUrl,
  documentText,
  onReset = () => {},
  onAddSupportingDocument,
  onSelectComponent,
  onSelectLineItem,
  onInspectFieldId,
}) => {
  const {
    hero,
    reconciliation,
    financial_summary = [],
    attention_items = [],
    ways_to_review_cost,
    supporting_document_context = [],
    questions_to_ask = [],
    suggested_message = "",
    checklist,
    completeness,
  } = summary;

  // Active flag for DocumentViewer bounding-box overlay
  const [activeFlag, setActiveFlag] = useState<DecisionFlag | null>(null);

  // Expanded evidence drawer for attention items
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);

  // Progressive disclosure: Show top 3 vs all questions
  const [showAllQuestions, setShowAllQuestions] = useState<boolean>(false);

  // Progressive disclosure: Expandable cost review opportunities
  const [expandedOpportunityId, setExpandedOpportunityId] = useState<string | null>(null);

  // Technical verification collapsible toggle (default: false / collapsed)
  const [isTechVerificationOpen, setIsTechVerificationOpen] = useState<boolean>(false);

  // Copy feedback states
  const [copiedQuestionIdx, setCopiedQuestionIdx] = useState<number | null>(null);
  const [copiedMessage, setCopiedMessage] = useState<boolean>(false);
  const [editableMessage, setEditableMessage] = useState<string>(suggested_message);

  // DOM Refs for smooth in-page navigation
  const sellerMessageRef = useRef<HTMLDivElement>(null);
  const supportingFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setEditableMessage(suggested_message);
  }, [suggested_message]);

  // Build a map of finding explanations for quick lookup
  const findingExplanationsMap = new Map<string, FindingExplanation>();
  if (evidenceResult?.finding_explanations) {
    for (const exp of evidenceResult.finding_explanations) {
      findingExplanationsMap.set(exp.finding_id, exp);
    }
  }

  // Normalise nested arrays that the backend may omit
  const safeReconciliation = {
    ...reconciliation,
    reconciliation_notes: reconciliation?.reconciliation_notes ?? [],
  };
  const safeWaysToReview = ways_to_review_cost
    ? { ...ways_to_review_cost, opportunities: ways_to_review_cost.opportunities ?? [] }
    : null;

  const handleCopyQuestion = (q: string, idx: number) => {
    navigator.clipboard.writeText(q);
    setCopiedQuestionIdx(idx);
    setTimeout(() => setCopiedQuestionIdx(null), 2000);
  };

  const handleCopyMessage = () => {
    navigator.clipboard.writeText(editableMessage);
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
  };

  const scrollToSellerMessage = () => {
    if (sellerMessageRef.current) {
      sellerMessageRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const handleSupportingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0] && onAddSupportingDocument) {
      onAddSupportingDocument(e.target.files[0]);
    }
  };

  // Focus and highlight in document viewer
  const handleHighlightEvidence = (
    fieldId?: string,
    label?: string,
    boundingBox?: any
  ) => {
    if (boundingBox) {
      setActiveFlag({
        flag_id: fieldId || "manual_flag",
        claim_type: "requires_verification",
        label: label || "Document Evidence",
        message: label || "Inspected document region",
        severity: "INFO",
        field_ids: fieldId ? [fieldId] : [],
        bounding_boxes: [boundingBox],
      });
    } else if (fieldId && onInspectFieldId) {
      onInspectFieldId(fieldId, label);
    }

    // On mobile, scroll to viewer
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      const viewer = document.getElementById("document-evidence-viewer");
      if (viewer) {
        viewer.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  // Readiness badge styling
  const getReadinessConfig = (state: string) => {
    switch (state) {
      case "READY_FOR_FINAL_VERIFICATION":
        return {
          label: "Ready for Final Verification",
          bgColor: "bg-emerald-950/40 border-emerald-500/40 text-emerald-300",
          icon: ShieldCheck,
          accent: "text-emerald-400",
          bannerBorder: "border-emerald-500/30",
        };
      case "INCOMPLETE_INFORMATION":
        return {
          label: "Incomplete Information",
          bgColor: "bg-slate-900/60 border-slate-700/60 text-slate-300",
          icon: HelpCircle,
          accent: "text-slate-400",
          bannerBorder: "border-slate-700/40",
        };
      case "REQUIRES_VERIFICATION":
      default:
        return {
          label: "Requires Verification",
          bgColor: "bg-amber-950/40 border-amber-500/40 text-amber-300",
          icon: ShieldAlert,
          accent: "text-amber-400",
          bannerBorder: "border-amber-500/30",
        };
    }
  };

  const readiness = getReadinessConfig(hero.readiness_state);
  const ReadinessIcon = readiness.icon;

  // Semantic audit and truthful representation for Checklist Items (Phase 10.1 Requirement 9)
  const getChecklistItemPresentation = (chk: BeforeYouPayChecklistItem) => {
    if (chk.key === "component_calculations_checked") {
      if (safeReconciliation.subtotal_reconciled && chk.status === "VERIFIED") {
        return {
          title: "Component totals reconciled",
          status: "VERIFIED",
          detail: chk.detail || "All itemized breakdown figures sum up to stated subtotal.",
        };
      } else {
        return {
          title: "Component arithmetic requires review",
          status: "REQUIRES_VERIFICATION",
          detail:
            chk.detail ||
            "Discrepancy detected between component sum and stated subtotal.",
        };
      }
    }

    if (chk.key === "quoted_total_verified") {
      if (safeReconciliation.quoted_total_reconciled && chk.status === "VERIFIED") {
        return {
          title: "Quoted total reconciled",
          status: "VERIFIED",
          detail: chk.detail || "Final quoted total matches expected mathematical reconciliation.",
        };
      } else {
        return {
          title: "Quoted total requires verification",
          status: "REQUIRES_VERIFICATION",
          detail:
            chk.detail ||
            "Quoted total requires verification against constituent charges and deductions.",
        };
      }
    }

    return {
      title: chk.title,
      status: chk.status,
      detail: chk.detail,
    };
  };

  const getChecklistStatusBadge = (status: string) => {
    switch (status) {
      case "VERIFIED":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Verified
          </span>
        );
      case "REQUIRES_VERIFICATION":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Needs Review
          </span>
        );
      case "PENDING_USER_ACTION":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Action Needed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            N/A
          </span>
        );
    }
  };

  // Truthfully calculate verified count based on actual reconciled state
  const verifiedChecklistCount = checklist.items.reduce((acc, item) => {
    const pres = getChecklistItemPresentation(item);
    return pres.status === "VERIFIED" ? acc + 1 : acc;
  }, 0);

  return (
    <div className="w-full space-y-6 text-slate-200">
      {/* ── TOP CONTROL BAR ── */}
      <div className="flex items-center justify-between pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 shrink-0" aria-hidden="true" />
          <h2 className="text-xs sm:text-sm font-extrabold uppercase tracking-widest text-indigo-400">
            Before You Pay &bull; Decision Support
          </h2>
          {result?.document?.document_type && (
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              {result.document.document_type}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition cursor-pointer focus-visible:ring-2 focus-visible:ring-indigo-500"
          aria-label="Scan Another Document"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400 shrink-0" aria-hidden="true" />
          <span>Scan Another</span>
        </button>
      </div>

      {/* ── RESPONSIVE 2-COLUMN LAYOUT (DESKTOP) / SEQUENTIAL STACK (MOBILE) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ══════════════════════════════════════════════════════
            LEFT / MAIN COLUMN: Decision Flow & Financial Analysis
            ══════════════════════════════════════════════════════ */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. DECISION HERO (Phase 10.1 Refinement) */}
          <div
            className={`p-6 sm:p-7 rounded-2xl border ${readiness.bannerBorder} bg-slate-900/80 backdrop-blur-md shadow-2xl transition-all space-y-4`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <ReadinessIcon className={`w-5 h-5 ${readiness.accent} shrink-0`} aria-hidden="true" />
                  <span className="text-xs uppercase tracking-wider font-bold opacity-80 text-slate-300">
                    Before You Pay
                  </span>
                </div>

                <div className="flex items-baseline gap-3 flex-wrap">
                  <h1 className="text-3xl sm:text-4xl md:text-5xl font-black font-mono tracking-tight text-white">
                    {hero.formatted_total}
                  </h1>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wide uppercase bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    {hero.payment_status}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2.5 text-xs">
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${readiness.bgColor}`}
                  >
                    {readiness.label}
                  </span>

                  <span className="text-slate-400 font-medium">
                    Review Status: <strong className="text-slate-200">{hero.review_status}</strong>
                  </span>

                  {hero.balance_due != null && (
                    <span className="text-slate-400 font-medium">
                      &bull; Balance Due:{" "}
                      <strong className="text-slate-200 font-mono">
                        {hero.formatted_balance_due || hero.formatted_total}
                      </strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Summary Pill */}
              <div className="flex flex-col items-start sm:items-end justify-center shrink-0 border-t sm:border-t-0 border-slate-800 pt-3 sm:pt-0">
                <div className="text-xs text-slate-400 font-mono">
                  Checklist: <span className="text-emerald-400 font-bold">{verifiedChecklistCount}</span> of {checklist.total_count} verified
                </div>
                <div className="w-32 bg-slate-800 h-2 rounded-full overflow-hidden mt-1.5 border border-slate-700/50">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${checklist.total_count > 0 ? (verifiedChecklistCount / checklist.total_count) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Primary Attention Banner Callout with Direct Action Triggers */}
            {attention_items.length > 0 ? (
              <div className="p-4 rounded-xl bg-slate-950/80 border border-amber-500/40 space-y-2.5 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-amber-300">
                          {attention_items[0].title}
                        </span>
                        {attention_items[0].formatted_amount && (
                          <span className="font-mono font-bold text-amber-400 px-1.5 py-0.2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px]">
                            {attention_items[0].formatted_amount} discrepancy
                          </span>
                        )}
                      </div>
                      <p className="text-slate-300 mt-1 leading-relaxed">
                        {attention_items[0].reason}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80 flex-wrap">
                  <button
                    type="button"
                    onClick={scrollToSellerMessage}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 border border-brand-500/40 transition cursor-pointer"
                  >
                    <MessageSquare className="w-3 h-3 shrink-0" aria-hidden="true" />
                    <span>Ask Seller</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      const firstExp = findingExplanationsMap.get(attention_items[0].item_id);
                      handleHighlightEvidence(
                        undefined,
                        attention_items[0].title,
                        firstExp?.evidence?.[0]?.bounding_box
                      );
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition cursor-pointer"
                  >
                    <Eye className="w-3 h-3 text-cyan-400 shrink-0" aria-hidden="true" />
                    <span>View Evidence</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/25 flex items-center gap-2.5 text-xs text-emerald-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
                <span>All calculations and stated totals reconcile mathematically.</span>
              </div>
            )}
          </div>

          {/* 2. WHAT NEEDS ATTENTION (Compact cards with direct inspection actions) */}
          {attention_items.length > 0 && (
            <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
                  <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                    What Needs Attention ({attention_items.length})
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400">Prioritized decision checks</span>
              </div>

              <div className="space-y-3">
                {attention_items.map((item) => {
                  const explanation = findingExplanationsMap.get(item.item_id);
                  const isExpanded = expandedFindingId === item.item_id;

                  return (
                    <div
                      key={item.item_id}
                      className="p-4 rounded-xl bg-slate-950/70 border-l-4 border-l-amber-500 border border-slate-800/80 space-y-2.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              {item.category}
                            </span>
                            <h4 className="text-sm font-bold text-white">{item.title}</h4>
                          </div>
                          <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                            {item.reason}
                          </p>
                        </div>

                        {item.formatted_amount && (
                          <span className="text-sm font-bold font-mono text-amber-400 shrink-0">
                            {item.formatted_amount}
                          </span>
                        )}
                      </div>

                      {/* Action & Evidence Toolbar */}
                      <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between flex-wrap gap-2 text-xs">
                        <div className="text-cyan-300 font-medium text-[11px]">
                          Action: {item.action_or_question}
                        </div>

                        <div className="flex items-center gap-2">
                          {explanation?.evidence?.[0]?.bounding_box && (
                            <button
                              type="button"
                              onClick={() =>
                                handleHighlightEvidence(
                                  undefined,
                                  item.title,
                                  explanation.evidence[0].bounding_box
                                )
                              }
                              className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800/60 border border-slate-700/50 cursor-pointer"
                              aria-label={`Inspect evidence on document for ${item.title}`}
                            >
                              <Eye className="w-3 h-3 text-cyan-400 shrink-0" aria-hidden="true" />
                              <span>Inspect Evidence</span>
                            </button>
                          )}

                          {explanation && (
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedFindingId(isExpanded ? null : item.item_id)
                              }
                              className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 px-2 py-1 rounded bg-indigo-500/10 border border-indigo-500/20 cursor-pointer"
                              aria-expanded={isExpanded}
                            >
                              <span>{isExpanded ? "Hide Details" : "Show Proof"}</span>
                              {isExpanded ? (
                                <ChevronUp className="w-3 h-3 shrink-0" aria-hidden="true" />
                              ) : (
                                <ChevronDown className="w-3 h-3 shrink-0" aria-hidden="true" />
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Expanded Phase 7 Evidence Panel */}
                      {isExpanded && explanation && (
                        <div className="mt-3 pt-3 border-t border-slate-800">
                          <EvidencePanel explanation={explanation} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 3. THREE-TIER FINANCIAL RECONCILIATION (Phase 10.1 Refinement with Mathematical Equations) */}
          <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Calculator className="w-4 h-4 text-cyan-400 shrink-0" aria-hidden="true" />
                <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                  Three-Tier Financial Reconciliation
                </h3>
              </div>
              <span
                className={`text-xs px-2.5 py-0.5 rounded font-mono font-semibold ${
                  safeReconciliation.subtotal_reconciled &&
                  safeReconciliation.quoted_total_reconciled
                    ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/50"
                    : "bg-amber-950/60 text-amber-400 border border-amber-800/50"
                }`}
              >
                {safeReconciliation.subtotal_reconciled &&
                safeReconciliation.quoted_total_reconciled
                  ? "Reconciliation: Reconciled"
                  : "Requires Verification"}
              </span>
            </div>

            {/* Independent Tiers Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
              {/* Tier 1: Listed Components */}
              <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] uppercase text-slate-400 font-bold tracking-wider">
                      Tier 1: Listed Components
                    </span>
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded border ${
                        safeReconciliation.subtotal_reconciled
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}
                    >
                      {safeReconciliation.subtotal_reconciled ? "RECONCILED" : "REQUIRES VERIFICATION"}
                    </span>
                  </div>
                  <div className="text-xl font-bold font-mono text-white mt-1.5">
                    {safeReconciliation.formatted_component_total}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    {safeReconciliation.component_count} charges listed
                    {safeReconciliation.unreadable_component_count > 0 &&
                      ` (${safeReconciliation.unreadable_component_count} unreadable)`}
                  </div>
                </div>

                <div className="mt-3 text-[11px] font-mono border-t border-slate-800/60 pt-2 text-slate-400 space-y-1">
                  <div className="flex items-center justify-between">
                    <span>Stated Subtotal:</span>
                    <span className="font-semibold text-slate-200">
                      {safeReconciliation.formatted_stated_subtotal || safeReconciliation.formatted_component_total}
                    </span>
                  </div>
                  {!safeReconciliation.subtotal_reconciled && safeReconciliation.formatted_discrepancy && (
                    <div className="flex items-center justify-between text-amber-400">
                      <span>Subtotal Diff:</span>
                      <span className="font-bold">{safeReconciliation.formatted_discrepancy}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Tier 2: Offers & Deductions */}
              <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] uppercase text-slate-400 font-bold tracking-wider">
                      Tier 2: Offers & Deductions
                    </span>
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded border ${
                        safeReconciliation.offers_count > 0
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {safeReconciliation.offers_count > 0 ? "APPLIED" : "NONE DETECTED"}
                    </span>
                  </div>
                  <div className="text-xl font-bold font-mono text-emerald-400 mt-1.5">
                    {safeReconciliation.formatted_offers_total}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    {safeReconciliation.offers_count} deductions / discounts
                  </div>
                </div>

                <div className="mt-3 text-[11px] font-mono flex items-center justify-between border-t border-slate-800/60 pt-2 text-slate-400">
                  <span>Kept strictly separate</span>
                  <span className="text-emerald-400 font-medium">Applied to subtotal</span>
                </div>
              </div>

              {/* Tier 3: Quoted Total */}
              <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] uppercase text-slate-400 font-bold tracking-wider">
                      Tier 3: Quoted Total
                    </span>
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded border ${
                        safeReconciliation.quoted_total_reconciled
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}
                    >
                      {safeReconciliation.quoted_total_reconciled ? "RECONCILED" : "REQUIRES VERIFICATION"}
                    </span>
                  </div>
                  <div className="text-xl font-bold font-mono text-white mt-1.5">
                    {safeReconciliation.formatted_quoted_total}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Expected: Subtotal &minus; Offers
                  </div>
                </div>

                <div className="mt-3 text-[11px] font-mono flex items-center justify-between border-t border-slate-800/60 pt-2">
                  <span className="text-slate-400">Net Delta:</span>
                  <span
                    className={
                      safeReconciliation.discrepancy_amount
                        ? "text-amber-400 font-bold"
                        : "text-emerald-400 font-semibold"
                    }
                  >
                    {safeReconciliation.formatted_discrepancy || "₹0.00"}
                  </span>
                </div>
              </div>
            </div>

            {/* Compact Mathematical Equations */}
            <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs font-mono space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-bold font-sans">
                Deterministic Mathematical Proof
              </div>

              {/* Equation A: Stated Subtotal - Offers = Quoted Total */}
              <div className="flex items-center gap-2 flex-wrap text-slate-300">
                <span className="text-slate-400 font-sans">Quoted Total Equation:</span>
                <span className="text-white font-semibold">
                  {safeReconciliation.formatted_stated_subtotal || safeReconciliation.formatted_component_total}
                </span>
                <span className="text-slate-500 font-sans">(Subtotal)</span>
                <span className="text-amber-400">&minus;</span>
                <span className="text-emerald-400 font-semibold">
                  {safeReconciliation.formatted_offers_total}
                </span>
                <span className="text-slate-500 font-sans">(Offers)</span>
                <span className="text-cyan-400">=</span>
                <span className="text-white font-bold">
                  {safeReconciliation.formatted_quoted_total}
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded font-sans uppercase font-bold ${
                    safeReconciliation.quoted_total_reconciled
                      ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
                      : "text-amber-400 bg-amber-500/10 border border-amber-500/20"
                  }`}
                >
                  {safeReconciliation.quoted_total_reconciled ? "PASS" : "FAIL"}
                </span>
              </div>

              {/* Equation B: Listed Components vs Stated Subtotal */}
              <div className="flex items-center gap-2 flex-wrap text-slate-300 pt-1.5 border-t border-slate-800/60">
                <span className="text-slate-400 font-sans">Component Sum Verification:</span>
                <span className="text-white font-semibold">
                  {safeReconciliation.formatted_component_total}
                </span>
                <span className="text-slate-500 font-sans">(Components Sum)</span>
                <span className="text-slate-400 font-sans">vs</span>
                <span className="text-white font-semibold">
                  {safeReconciliation.formatted_stated_subtotal || safeReconciliation.formatted_component_total}
                </span>
                <span className="text-slate-500 font-sans">(Stated Subtotal)</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded font-sans uppercase font-bold ${
                    safeReconciliation.subtotal_reconciled
                      ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
                      : "text-amber-400 bg-amber-500/10 border border-amber-500/20"
                  }`}
                >
                  {safeReconciliation.subtotal_reconciled ? "PASS" : "REQUIRES VERIFICATION"}
                </span>
              </div>
            </div>

            {/* Reconciliation Notes */}
            {safeReconciliation.reconciliation_notes.length > 0 && (
              <div className="text-xs text-slate-400 font-mono space-y-1 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/50">
                {safeReconciliation.reconciliation_notes.map((note, idx) => (
                  <p key={idx} className="flex items-start gap-1.5">
                    <span className="text-cyan-400" aria-hidden="true">&bull;</span> {note}
                  </p>
                ))}
              </div>
            )}
          </div>

          {/* 4. WAYS TO REVIEW THIS COST (Compact with Progressive Disclosure) */}
          {safeWaysToReview && safeWaysToReview.opportunities.length > 0 && (
            <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
                  <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                    Ways to Review This Cost ({safeWaysToReview.opportunities.length})
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400 hidden sm:inline">
                  Potential amount to review &bull; No guaranteed savings
                </span>
              </div>

              {/* Compact Review List with Expandable Disclosure */}
              <div className="space-y-2">
                {safeWaysToReview.opportunities.map((opp) => {
                  const isExpanded = expandedOpportunityId === opp.opportunity_id;
                  return (
                    <div
                      key={opp.opportunity_id}
                      className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs space-y-2 transition-all"
                    >
                      <div className="flex items-center justify-between gap-3 flex-wrap sm:flex-nowrap">
                        <div className="flex items-center gap-2 flex-wrap min-w-0">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                            {opp.category}
                          </span>
                          <span className="font-semibold text-slate-200 truncate">
                            {opp.component}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 shrink-0 ml-auto">
                          <div className="text-right">
                            <span className="text-xs font-bold font-mono text-emerald-400 block">
                              {opp.formatted_potential_amount || opp.formatted_amount}
                            </span>
                            <span className="text-[10px] text-slate-500 block">
                              Potential to review
                            </span>
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              setExpandedOpportunityId(isExpanded ? null : opp.opportunity_id)
                            }
                            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition cursor-pointer"
                            aria-expanded={isExpanded}
                            aria-label={`Toggle details for ${opp.component}`}
                          >
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 shrink-0" aria-hidden="true" />
                            ) : (
                              <ChevronDown className="w-4 h-4 shrink-0" aria-hidden="true" />
                            )}
                          </button>
                        </div>
                      </div>

                      <div className="text-[11px] text-cyan-300 font-medium">
                        &bull; Action: {opp.suggested_action}
                      </div>

                      {/* Expandable Explanation Details */}
                      {isExpanded && (
                        <div className="pt-2 border-t border-slate-800 text-slate-300 leading-relaxed text-xs space-y-1.5 animate-in fade-in duration-150">
                          <p>{opp.explanation}</p>
                          {opp.evidence && (
                            <div className="text-slate-400 text-[11px] bg-slate-900/70 p-2 rounded border border-slate-800">
                              <span className="font-bold text-slate-300 font-mono">Evidence: </span>
                              {opp.evidence}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <p className="text-[11px] text-slate-500 mt-2 italic font-sans">
                Disclaimer: {safeWaysToReview.disclaimer}
              </p>
            </div>
          )}

          {/* 5. QUESTIONS TO ASK & EDITABLE SELLER MESSAGE */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Questions to Ask */}
            <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-2">
                  <div className="flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
                    <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                      Questions to Ask ({questions_to_ask.length})
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-400">
                    {showAllQuestions ? `Showing all ${questions_to_ask.length}` : `Top 3 questions`}
                  </span>
                </div>

                {/* Question Items (Top 3 by default, or all when expanded) */}
                <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
                  {(showAllQuestions ? questions_to_ask : questions_to_ask.slice(0, 3)).map((q, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold text-amber-400 font-mono">
                          Q{idx + 1}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopyQuestion(q, idx)}
                          className="inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-white px-2 py-0.5 rounded bg-slate-800 cursor-pointer"
                          aria-label={`Copy question ${idx + 1}`}
                        >
                          {copiedQuestionIdx === idx ? (
                            <>
                              <Check className="w-2.5 h-2.5 text-emerald-400 shrink-0" aria-hidden="true" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-2.5 h-2.5 shrink-0" aria-hidden="true" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                      <p className="text-slate-200 font-medium leading-relaxed">{q}</p>
                    </div>
                  ))}
                </div>

                {questions_to_ask.length > 3 && (
                  <button
                    type="button"
                    onClick={() => setShowAllQuestions(!showAllQuestions)}
                    className="w-full mt-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 transition cursor-pointer text-center"
                    aria-expanded={showAllQuestions}
                  >
                    {showAllQuestions
                      ? "Show Top 3 Questions"
                      : `Show all ${questions_to_ask.length} questions`}
                  </button>
                )}
              </div>
            </div>

            {/* Editable Seller Message */}
            <div
              ref={sellerMessageRef}
              className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm flex flex-col justify-between space-y-3"
            >
              <div>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-2">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-cyan-400 shrink-0" aria-hidden="true" />
                    <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                      Message to Seller
                    </h3>
                  </div>

                  <button
                    type="button"
                    onClick={handleCopyMessage}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold transition cursor-pointer"
                    aria-label="Copy entire message to clipboard"
                  >
                    {copiedMessage ? (
                      <>
                        <Check className="w-3 h-3 shrink-0" aria-hidden="true" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3 shrink-0" aria-hidden="true" />
                        <span>Copy Message</span>
                      </>
                    )}
                  </button>
                </div>

                <p className="text-xs text-slate-400 mb-2">
                  User-controlled message draft. Review, edit, and send via your preferred channel.
                </p>

                <textarea
                  value={editableMessage}
                  onChange={(e) => setEditableMessage(e.target.value)}
                  rows={9}
                  className="w-full p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-brand-500/60 font-sans leading-relaxed resize-none"
                  placeholder="Generated message to send to provider..."
                  aria-label="Editable seller message"
                />
              </div>

              <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500">
                <span>{editableMessage.length} characters</span>
                <span className="text-cyan-400">Ready to send</span>
              </div>
            </div>
          </div>

          {/* 6. CANONICAL FINANCIAL BREAKDOWN */}
          {financial_summary.length > 0 && (
            <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-purple-400 shrink-0" aria-hidden="true" />
                  <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                    Canonical Financial Breakdown ({financial_summary.length} items)
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400">Preserved original states</span>
              </div>

              <div className="divide-y divide-slate-800/60 font-mono text-xs">
                {financial_summary.map((item, idx) => (
                  <div key={idx} className="py-2.5 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-slate-200 font-medium font-sans">{item.name}</span>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                        [{item.canonical_category}]
                      </span>
                      {item.amount_state &&
                        item.amount_state !== "PRESENT" &&
                        item.amount_state !== "ZERO" && (
                          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
                            [{item.amount_state}]
                          </span>
                        )}
                    </div>
                    <div
                      className={
                        item.is_deduction
                          ? "text-emerald-400 font-bold"
                          : "text-white font-semibold"
                      }
                    >
                      {item.formatted_amount}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ══════════════════════════════════════════════════════
            RIGHT / SECONDARY COLUMN (Desktop Sticky):
            Checklist, Supporting Scan, Document Viewer & Evidence
            ══════════════════════════════════════════════════════ */}
        <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto pr-1">
          {/* 7. BEFORE YOU PAY CHECKLIST (Truthful verification semantics) */}
          <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
                <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                  Before You Pay Checklist
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {verifiedChecklistCount} of {checklist.total_count} verified
              </span>
            </div>

            <div className="space-y-2">
              {checklist.items.map((chk) => {
                const itemPresentation = getChecklistItemPresentation(chk);
                return (
                  <div
                    key={chk.key}
                    className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start justify-between gap-2.5"
                  >
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5">
                        {itemPresentation.status === "VERIFIED" ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
                        ) : itemPresentation.status === "REQUIRES_VERIFICATION" ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" aria-hidden="true" />
                        ) : (
                          <HelpCircle className="w-3.5 h-3.5 text-blue-400 shrink-0" aria-hidden="true" />
                        )}
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-slate-200">
                          {itemPresentation.title}
                        </h4>
                        <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                          {itemPresentation.detail}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {getChecklistStatusBadge(itemPresentation.status)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 8. INFORMATION COMPLETENESS */}
          <div className="p-4 rounded-xl border border-slate-800/60 bg-slate-950/40 text-xs">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                  Information Completeness
                </span>
                <span className="text-slate-500 text-[10px] italic">
                  {completeness.completeness_note}
                </span>
              </div>
              <div className="flex items-center gap-2 font-mono text-[11px] flex-wrap">
                <span
                  className={`px-2 py-0.5 rounded border ${
                    completeness.is_complete_to_calculate
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}
                >
                  Calculate: {completeness.is_complete_to_calculate ? "✓ Complete" : "⚠️ Incomplete"}
                </span>
                <span
                  className={`px-2 py-0.5 rounded border ${
                    completeness.is_complete_to_explain
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}
                >
                  Explain: {completeness.is_complete_to_explain ? "✓ Complete" : "⚠️ Incomplete"}
                </span>
                <span
                  className={`px-2 py-0.5 rounded border ${
                    completeness.is_complete_to_verify
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}
                >
                  Verify: {completeness.is_complete_to_verify ? "✓ Complete" : "⚠️ Incomplete"}
                </span>
              </div>
            </div>
          </div>

          {/* 9. COMPARE ANOTHER DOCUMENT (Supporting Document Experience) */}
          <div className="p-5 rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-blue-400 shrink-0" aria-hidden="true" />
                <h3 className="text-xs font-bold tracking-wider uppercase text-slate-300">
                  Compare Another Document
                </h3>
              </div>
              <input
                ref={supportingFileInputRef}
                type="file"
                className="hidden"
                accept="image/*,application/pdf"
                onChange={handleSupportingFileChange}
              />
              <button
                type="button"
                onClick={() => supportingFileInputRef.current?.click()}
                className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium cursor-pointer transition"
                aria-label="Add Supporting Document"
              >
                <Plus className="w-3 h-3 shrink-0" aria-hidden="true" />
                <span>Add Doc</span>
              </button>
            </div>

            {supporting_document_context && supporting_document_context.length > 0 ? (
              <div className="space-y-3">
                {supporting_document_context.map((docComp, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-blue-400">{docComp.title}</span>
                      <span className="text-[10px] text-slate-400 font-mono uppercase">
                        [{docComp.comparison_type}]
                      </span>
                    </div>
                    <p className="text-slate-300 leading-snug">{docComp.finding_description}</p>
                    <div className="text-slate-400 text-[11px] italic bg-slate-900/60 p-2 rounded border border-slate-800/60">
                      Excerpt: &ldquo;{docComp.supporting_document_text}&rdquo;
                    </div>
                    <div className="text-cyan-300 font-medium text-[11px]">
                      Action: {docComp.action_guidance}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-slate-950/50 border border-dashed border-slate-800 text-center space-y-2">
                <FileSearch className="w-6 h-6 text-slate-500 mx-auto" aria-hidden="true" />
                <p className="text-xs text-slate-400 leading-relaxed">
                  Compare an existing warranty, insurance policy, or prior quote to uncover
                  overlapping fees and uncredited discounts.
                </p>
                <button
                  type="button"
                  onClick={() => supportingFileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-semibold cursor-pointer"
                >
                  <Upload className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  <span>Upload Supporting Scan</span>
                </button>
              </div>
            )}
          </div>

          {/* 10. SOURCE DOCUMENT EVIDENCE VIEWER */}
          <div id="document-evidence-viewer" className="rounded-xl overflow-hidden">
            <DocumentViewer
              documentText={
                result?.raw_ocr_lines && result.raw_ocr_lines.length > 0
                  ? result.raw_ocr_lines.join("\n")
                  : documentText || ""
              }
              ocrLines={result?.ocr_lines || null}
              selectedFlag={activeFlag}
              imagePreviewUrl={imagePreviewUrl || null}
              onReturnToSummary={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            />
          </div>
        </div>
      </div>

      {/* ── 11. TECHNICAL VERIFICATION DETAILS (Collapsible Lower in Hierarchy) ── */}
      {result?.validation_checks && result.validation_checks.length > 0 && (
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 backdrop-blur-sm overflow-hidden">
          <button
            type="button"
            onClick={() => setIsTechVerificationOpen(!isTechVerificationOpen)}
            className="w-full flex items-center justify-between p-4 text-left cursor-pointer hover:bg-slate-800/40 transition focus-visible:ring-2 focus-visible:ring-indigo-500"
            aria-expanded={isTechVerificationOpen}
          >
            <div className="flex items-center gap-2.5">
              <Calculator className="w-4 h-4 text-indigo-400 shrink-0" aria-hidden="true" />
              <div>
                <h3 className="text-xs font-bold tracking-wider uppercase text-slate-200">
                  Technical Mathematical Verification ({result.validation_checks.length} code checks)
                </h3>
                <p className="text-[11px] text-slate-400">
                  Deterministic Python formula proofs and tolerance checks
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-indigo-400 font-mono">
                {isTechVerificationOpen ? "Hide Checks" : "Inspect Checks"}
              </span>
              {isTechVerificationOpen ? (
                <ChevronUp className="w-4 h-4 text-slate-400 shrink-0" aria-hidden="true" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" aria-hidden="true" />
              )}
            </div>
          </button>

          {isTechVerificationOpen && (
            <div className="p-4 border-t border-slate-800 bg-slate-950/50">
              <MathVerification
                checks={result.validation_checks}
                currency={result.document?.currency || "INR"}
                isQuotation={
                  result.document?.document_type === "quotation" ||
                  Boolean(result.document?.cost_breakdown?.length)
                }
                quotedTotal={
                  result.document?.total_amount?.normalized_value != null
                    ? Number(result.document.total_amount.normalized_value)
                    : null
                }
                subtotal={
                  result.document?.subtotal?.normalized_value != null
                    ? Number(result.document.subtotal.normalized_value)
                    : null
                }
                discountTotal={
                  result.document?.discount_amount?.normalized_value != null
                    ? Number(result.document.discount_amount.normalized_value)
                    : null
                }
                onSelectFieldId={onInspectFieldId}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
