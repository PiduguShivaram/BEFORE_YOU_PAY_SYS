"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "../components/Navbar";
import { Dropzone } from "../components/Dropzone";
import { PipelineProgress } from "../components/PipelineProgress";
import { VerdictBanner } from "../components/VerdictBanner";
import { DecisionFlags } from "../components/DecisionFlags";
import { MathVerification } from "../components/MathVerification";
import { LineItemsTable } from "../components/LineItemsTable";
import { DocumentViewer } from "../components/DocumentViewer";
import { RagDrawer } from "../components/RagDrawer";
import { OkfModal } from "../components/OkfModal";
import { CostBreakdownCard } from "../components/CostBreakdownCard";
import { ExtraCostAnalysisCard } from "../components/ExtraCostAnalysisCard";
import { PlainLanguageExplanationCard } from "../components/PlainLanguageExplanationCard";
import { PotentialCostReductionCard } from "../components/PotentialCostReductionCard";
import { SmartQuestionsCard } from "../components/SmartQuestionsCard";
import { WaysToReviewCostCard } from "../components/WaysToReviewCostCard";
import {
  DecisionFlag,
  DocumentClassification,
  FinalDecisionSupportResult,
  FinancialComponent,
  OkfRule,
  RagRecord,
} from "../lib/types";
import { analyzeDocumentStream, checkBackendHealth, StreamEvent } from "../lib/api";
import { generateUUID } from "../lib/utils";
import { Shield, Sparkles } from "lucide-react";

export default function Home() {
  const [userId, setUserId] = useState<string>("");
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [streamEvent, setStreamEvent] = useState<StreamEvent | null>(null);
  const [result, setResult] = useState<FinalDecisionSupportResult | null>(null);
  const [documentText, setDocumentText] = useState<string>("");
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [selectedFlag, setSelectedFlag] = useState<DecisionFlag | null>(null);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);

  // Modals state
  const [isRagOpen, setIsRagOpen] = useState<boolean>(false);
  const [isOkfOpen, setIsOkfOpen] = useState<boolean>(false);
  const [ragRecords, setRagRecords] = useState<RagRecord[]>([]);

  // Curated OKF Rules from rules.json
  const okfRules: OkfRule[] = [
    {
      rule_id: "OKF-VERIF-MATH-01",
      rule_name: "Line Item Sum Integrity",
      category: "verification_rule",
      summary: "Sum of itemized components must equal stated subtotal.",
      source_reference: "GAAP & International Accounting Standards",
      version: "1.0.0",
      guidance: "Flag any discrepancy where line item extensions do not reconcile with stated subtotal.",
    },
    {
      rule_id: "OKF-RENEW-CLAUSE-01",
      rule_name: "Automatic Renewal and Notice Period Requirement",
      category: "comparison_rule",
      summary: "Subscription agreements must explicitly disclose auto-renewal notice windows.",
      source_reference: "FTC Negative Option Rule & Consumer Protection Standards",
      version: "1.0.0",
      guidance: "Identify auto-renewal clauses lacking at least a 30-day prior written notice requirement.",
    },
    {
      rule_id: "OKF-FEE-DISCLOSURE-01",
      rule_name: "Undisclosed Ancillary Surcharge",
      category: "verification_rule",
      summary: "Processing or platform surcharges must be itemized before payment.",
      source_reference: "Truth in Lending & Consumer Financial Protection Standards",
      version: "1.0.0",
      guidance: "Flag any general surcharge or administrative fee not detailed in original quotation.",
    },
    {
      rule_id: "OKF-VERIF-TAX-01",
      rule_name: "Tax Rate and Surcharge Compliance",
      category: "verification_rule",
      summary: "Applied tax amounts must reconcile with applicable statutory rates.",
      source_reference: "Statutory Commercial Sales Tax Codes",
      version: "1.0.0",
      guidance: "Verify whether taxes match stated rates. Tax rates exceeding 35% require verification.",
    },
    {
      rule_id: "OKF-WARRANTY-SCOPE-01",
      rule_name: "Warranty Deductible and Limitations",
      category: "document_concept",
      summary: "Extended warranty coverage often excludes consumable parts or imposes deductibles.",
      source_reference: "Magnuson-Moss Warranty Act & Commercial Practice",
      version: "1.0.0",
      guidance: "Highlight limitations, pre-existing condition exclusions, or required deductibles.",
    },
    {
      rule_id: "OKF-CANCEL-FEE-01",
      rule_name: "Early Termination and Restocking Penalties",
      category: "terminology",
      summary: "Service contracts often impose liquidated damages or restocking penalties.",
      source_reference: "Uniform Commercial Code (UCC) § 2-718",
      version: "1.0.0",
      guidance: "Review early termination fees that exceed 20% of remaining agreement balance.",
    },
  ];

  // Initialize client user ID and load RAG records
  useEffect(() => {
    let savedId = localStorage.getItem("byp_user_id");
    if (!savedId) {
      savedId = generateUUID();
      localStorage.setItem("byp_user_id", savedId);
    }
    setUserId(savedId);

    const savedRecords = localStorage.getItem("byp_rag_records");
    if (savedRecords) {
      try {
        setRagRecords(JSON.parse(savedRecords));
      } catch {
        // ignore
      }
    }

    // Health check probe with periodic polling
    const pollHealth = () => {
      checkBackendHealth()
        .then(() => setIsBackendHealthy(true))
        .catch(() => setIsBackendHealthy(false));
    };
    pollHealth();
    const intervalId = setInterval(pollHealth, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const handleUpdateUserId = (newId: string) => {
    setUserId(newId);
    localStorage.setItem("byp_user_id", newId);
  };

  const handleRecordAdded = (record: RagRecord) => {
    const updated = [record, ...ragRecords];
    setRagRecords(updated);
    localStorage.setItem("byp_rag_records", JSON.stringify(updated));
  };

  // Upload & Analyze Handler
  const handleFileSelect = async (file: File, docType: DocumentClassification) => {
    setIsProcessing(true);
    setResult(null);
    setSelectedFlag(null);
    setSelectedComponentId(null);
    setStreamEvent(null);

    // Create image preview if image
    if (file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setImagePreviewUrl(url);
    } else {
      setImagePreviewUrl(null);
    }

    // Read plain text if uploaded file is readable
    try {
      if (file.type.startsWith("text/")) {
        const text = await file.text();
        setDocumentText(text);
      } else {
        setDocumentText("");
      }
    } catch {
      setDocumentText("");
    }

    try {
      const data = await analyzeDocumentStream(file, userId, docType, (event) => {
        setStreamEvent(event);
      });
      setResult(data);
    } catch (err: any) {
      alert(`Document Analysis Rejected: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
    }
    setResult(null);
    setSelectedFlag(null);
    setSelectedComponentId(null);
    setDocumentText("");
    setImagePreviewUrl(null);
    setStreamEvent(null);
  };

  const handleSelectComponent = (comp: FinancialComponent) => {
    setSelectedComponentId(comp.component_id);
    if (comp.amount?.provenance?.bounding_box) {
      setSelectedFlag({
        flag_id: comp.component_id,
        claim_type: "requires_verification",
        label: comp.name,
        message: `${comp.name}: ${comp.amount.normalized_value}`,
        severity: "INFO",
        field_ids: [comp.amount.field_id],
        bounding_boxes: [comp.amount.provenance.bounding_box],
      });
    }

    // Smoothly scroll to document evidence viewer
    setTimeout(() => {
      const viewer = document.getElementById("document-evidence-viewer");
      if (viewer) {
        viewer.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 50);
  };

  const handleReturnToSummary = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Parse extracted items from document result or fallback text
  const extractedItems = React.useMemo(() => {
    // 1. Direct structured line items from AI / OCR
    if (result?.document?.line_items && result.document.line_items.length > 0) {
      return result.document.line_items.map((item, idx) => {
        const itemDesc = String(item.description?.normalized_value || `Item ${idx + 1}`);
        const extCheck = result.validation_checks?.find(
          (c) =>
            c.check_code === "LINE_ITEM_EXTENSION_MATCH" &&
            (c.input_field_ids?.includes(item.total_price?.field_id) ||
              c.message?.toLowerCase().includes(itemDesc.toLowerCase()))
        );
        let status: "PASS" | "REQUIRES_VERIFICATION" | undefined = undefined;
        if (extCheck) {
          status = extCheck.status === "PASS" ? "PASS" : "REQUIRES_VERIFICATION";
        }
        return {
          description: itemDesc,
          amount: Number(
            item.total_price?.normalized_value ??
              Number(item.quantity?.normalized_value || 1) * Number(item.unit_price?.normalized_value || 0)
          ),
          unitPrice: item.unit_price?.normalized_value != null ? Number(item.unit_price.normalized_value) : null,
          quantity: item.quantity?.normalized_value != null ? Number(item.quantity.normalized_value) : null,
          mrp: item.mrp?.normalized_value != null ? Number(item.mrp.normalized_value) : null,
          discount: item.discount?.normalized_value != null ? Number(item.discount.normalized_value) : null,
          linePointer: `Line ${idx + 1}`,
          status,
        };
      });
    }
    if (result) return [];

    // 2. Fallback to raw text parsing only if manual text without result
    const textToParse = documentText || "";
    if (!textToParse) return [];

    const lines = textToParse.split("\n");
    const currencyPattern =
      /(?:[\$€£₹¥]|USD|EUR|GBP|INR)?\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}|[\$€£₹¥]\s*[0-9]+(?:\.[0-9]{2})?)/g;

    const items: { description: string; amount: number; linePointer: string }[] = [];
    lines.forEach((l, idx) => {
      const matches = l.match(currencyPattern);
      if (matches && !/total|subtotal|tax/i.test(l)) {
        const rawAmount = matches[matches.length - 1].replace(/[^\d.]/g, "");
        const num = parseFloat(rawAmount);
        if (!isNaN(num) && num > 0) {
          const desc = l.replace(currencyPattern, "").replace(/[:\-]/g, "").trim() || `Item ${idx + 1}`;
          items.push({
            description: desc,
            amount: num,
            linePointer: `Line ${idx + 1}`,
          });
        }
      }
    });
    return items;
  }, [result, documentText]);

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col pb-24 md:pb-16 selection:bg-brand-500/30">
      {/* 1. Mobile Header & Application Identity */}
      <Navbar
        userId={userId}
        onUpdateUserId={handleUpdateUserId}
        ragCount={ragRecords.length}
        onOpenRag={() => setIsRagOpen(true)}
        onOpenOkf={() => setIsOkfOpen(true)}
        isBackendHealthy={isBackendHealthy}
        onTriggerScan={() => {
          handleReset();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />

      <main className="max-w-6xl mx-auto w-full px-3.5 sm:px-6 lg:px-8 space-y-5">
        {/* Hero Section (Compact for Mobile) */}
        {!result && (
          <div className="text-center max-w-xl mx-auto pt-2 pb-1 space-y-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
              <span>Strict Source Provenance • Deterministic Arithmetic</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
              Audit Before You Pay
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed max-w-md mx-auto">
              Scan any quotation, invoice, or bill. Verifies mathematical consistency, detects ancillary charges, and cross-references your prior terms.
            </p>
          </div>
        )}

        {/* 2. Primary Scan Document Action / Upload Flow */}
        {!result ? (
          <>
            <Dropzone onFileSelect={handleFileSelect} isProcessing={isProcessing} />
            <PipelineProgress isProcessing={isProcessing} currentEvent={streamEvent} />
          </>
        ) : (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* 3, 4, 5. Verdict Banner (Document Status + Financial Commitment + Decision Finding) */}
            <VerdictBanner result={result} onReset={handleReset} />

            {/* Results Hierarchy */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Primary Column (Cost Breakdown, Flags, Arithmetic Verification) */}
              <div className="lg:col-span-7 space-y-6">
                {/* Phase 8: Plain-Language Financial Explanation */}
                {result?.plain_language_explanation && (
                  <PlainLanguageExplanationCard
                    explanation={result.plain_language_explanation}
                  />
                )}

                {/* 6. Cost Breakdown (Stacked Mobile Rows with Tap-to-Inspect) */}
                {result?.document?.cost_breakdown && result.document.cost_breakdown.length > 0 && (
                  <CostBreakdownCard
                    components={result.document.cost_breakdown}
                    currency={result.document.currency}
                    subtotal={
                      result.document.subtotal?.normalized_value != null
                        ? Number(result.document.subtotal.normalized_value)
                        : null
                    }
                    discountTotal={
                      result.document.discount_amount?.normalized_value != null
                        ? Number(result.document.discount_amount.normalized_value)
                        : null
                    }
                    quotedTotal={Number(result.document.total_amount?.normalized_value || 0)}
                    validationChecks={result.validation_checks}
                    selectedComponentId={selectedComponentId}
                    onSelectComponent={handleSelectComponent}
                    smartQuestions={result.smart_questions}
                  />
                )}

                {/* Phase 7: Potential Cost Reduction Summary */}
                {result?.cost_reduction_summary && (
                  <PotentialCostReductionCard
                    summary={result.cost_reduction_summary}
                    currency={result.document?.currency}
                  />
                )}

                {/* Potential Extra Costs & Cost Reduction Analysis */}
                {result?.extra_cost_analysis && result.extra_cost_analysis.flagged_costs && result.extra_cost_analysis.flagged_costs.length > 0 && (
                  <ExtraCostAnalysisCard
                    analysis={result.extra_cost_analysis}
                    currency={result.document?.currency}
                  />
                )}

                {/* Phase 5: Ways to Review This Cost */}
                {result?.document?.cost_breakdown && result.document.cost_breakdown.length > 0 && (
                  <WaysToReviewCostCard
                    components={result.document.cost_breakdown}
                    extraCostAnalysis={result.extra_cost_analysis}
                    smartQuestions={result.smart_questions}
                    validationChecks={result.validation_checks}
                    currency={result.document?.currency}
                  />
                )}

                {/* Questions to ask before paying */}
                {result?.smart_questions && result.smart_questions.length > 0 && (
                  <SmartQuestionsCard
                    questions={result.smart_questions}
                    currency={result.document?.currency}
                  />
                )}

                {/* Additional Decision Findings if multiple exist */}
                {result.flags.length > 1 && (
                  <DecisionFlags
                    flags={result.flags}
                    selectedFlagId={selectedFlag?.flag_id ?? null}
                    onSelectFlag={(flag) => {
                      setSelectedFlag(flag);
                      setTimeout(() => {
                        const viewer = document.getElementById("document-evidence-viewer");
                        if (viewer) {
                          viewer.scrollIntoView({ behavior: "smooth", block: "start" });
                        }
                      }, 50);
                    }}
                  />
                )}

                {/* 7 & 9. Arithmetic Verification Summary & Expandable Technical Evidence */}
                <MathVerification
                  checks={result.validation_checks}
                  currency={result.document?.currency}
                  isQuotation={
                    result.document?.document_type === "quotation" ||
                    result.document?.document_type === "cost_breakdown" ||
                    Boolean(result.document?.cost_breakdown && result.document.cost_breakdown.length > 0)
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
                  onSelectFieldId={(fieldId) => {
                    const comp = result.document?.cost_breakdown?.find(
                      (c) => c.amount?.field_id === fieldId
                    );
                    if (comp?.amount?.provenance?.bounding_box) {
                      setSelectedComponentId(comp.component_id);
                      setSelectedFlag({
                        flag_id: comp.component_id,
                        claim_type: "requires_verification",
                        label: comp.name,
                        message: `${comp.name}: ${comp.amount.normalized_value}`,
                        severity: "INFO",
                        field_ids: [comp.amount.field_id],
                        bounding_boxes: [comp.amount.provenance.bounding_box],
                      });
                      setTimeout(() => {
                        const viewer = document.getElementById("document-evidence-viewer");
                        if (viewer) {
                          viewer.scrollIntoView({ behavior: "smooth", block: "start" });
                        }
                      }, 50);
                      return;
                    }
                    const item = result.document?.line_items?.find(
                      (li) => li.total_price?.field_id === fieldId || li.unit_price?.field_id === fieldId
                    );
                    const box = item?.total_price?.provenance?.bounding_box || item?.unit_price?.provenance?.bounding_box;
                    if (box) {
                      setSelectedFlag({
                        flag_id: fieldId,
                        claim_type: "requires_verification",
                        label: item?.description?.normalized_value ? String(item.description.normalized_value) : fieldId,
                        message: `Field ${fieldId}`,
                        severity: "INFO",
                        field_ids: [fieldId],
                        bounding_boxes: [box],
                      });
                      setTimeout(() => {
                        const viewer = document.getElementById("document-evidence-viewer");
                        if (viewer) {
                          viewer.scrollIntoView({ behavior: "smooth", block: "start" });
                        }
                      }, 50);
                    }
                  }}
                />

                {/* Line items table for invoices/bills without cost breakdowns */}
                {extractedItems.length > 0 && (!result?.document?.cost_breakdown || result.document.cost_breakdown.length === 0) && (
                  <LineItemsTable items={extractedItems} currency={result?.document?.currency} />
                )}
              </div>

              {/* 8. Source Document Evidence Column (Mobile Viewport Responsive) */}
              <div className="lg:col-span-5">
                <DocumentViewer
                  documentText={
                    result?.raw_ocr_lines && result.raw_ocr_lines.length > 0
                      ? result.raw_ocr_lines.join("\n")
                      : documentText
                  }
                  ocrLines={result?.ocr_lines}
                  selectedFlag={selectedFlag}
                  imagePreviewUrl={imagePreviewUrl}
                  onReturnToSummary={handleReturnToSummary}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 10. Secondary Actions: RAG Past Records Drawer */}
      <RagDrawer
        isOpen={isRagOpen}
        onClose={() => setIsRagOpen(false)}
        userId={userId}
        records={ragRecords}
        onRecordAdded={handleRecordAdded}
      />

      {/* OKF Rules Catalog Modal */}
      <OkfModal
        isOpen={isOkfOpen}
        onClose={() => setIsOkfOpen(false)}
        rules={okfRules}
      />

      {/* Non-committal Legal Disclaimer */}
      <footer className="mt-12 pt-6 border-t border-white/10 text-center text-[11px] text-slate-500 max-w-lg mx-auto px-4 leading-relaxed">
        <strong>Automated Decision Support:</strong> Uses spatial OCR geometry and deterministic Python arithmetic. Does not constitute formal legal or tax counsel. Final payment authorization rests with you.
      </footer>
    </div>
  );
}
