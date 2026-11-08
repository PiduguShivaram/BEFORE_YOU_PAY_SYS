"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "../components/Navbar";
import { Dropzone } from "../components/Dropzone";
import { PipelineProgress } from "../components/PipelineProgress";
import { VerdictBanner } from "../components/VerdictBanner";
import { BeforeYouPayFinalSummaryView } from "../components/BeforeYouPayFinalSummaryView";
import { MathVerification } from "../components/MathVerification";
import { LineItemsTable } from "../components/LineItemsTable";
import { DocumentViewer } from "../components/DocumentViewer";
import { RagDrawer } from "../components/RagDrawer";
import { OkfModal } from "../components/OkfModal";
import { CostBreakdownCard } from "../components/CostBreakdownCard";
import { WaysToReviewCostCard } from "../components/WaysToReviewCostCard";
import { MobileFailureRecovery, MobileFailureState } from "../components/MobileFailureRecovery";
import { MultiQuoteUploadDropzone } from "../components/MultiQuoteUploadDropzone";
import { MultiQuoteComparisonCard } from "../components/MultiQuoteComparisonCard";
import { DealerResponseParserCard } from "../components/DealerResponseParserCard";
import {
  DecisionFlag,
  DocumentClassification,
  FinalDecisionSupportResult,
  FinancialComponent,
  MultiQuoteComparisonResult,
  DealerResponseAnalysisResult,
  OkfRule,
  RagRecord,
} from "../lib/types";
import {
  analyzeDocument,
  analyzeDocumentStream,
  checkBackendHealth,
  clearAuthToken,
  createFreshSession,
  getCurrentUserProfile,
  StreamEvent,
} from "../lib/api";
import {
  saveAnalysisToCache,
  enqueueOfflineAudit,
  CachedAnalysisRecord,
} from "../lib/offlineStore";
import { generateUUID } from "../lib/utils";
import { Shield, Sparkles, Scale, FileSearch, MessageSquareQuote, Box } from "lucide-react";
import { Spatial3DCanvas } from "../components/Spatial3DCanvas";
import { Holographic3DScanner } from "../components/Holographic3DScanner";
import { SpatialHUD3D } from "../components/SpatialHUD3D";
import { Card3D } from "../components/Card3D";
import { SpatialCursor3D } from "../components/SpatialCursor3D";
import { OnDeviceAnalysisCard } from "../components/OnDeviceAnalysisCard";
import { runOnDeviceOfflineAnalysis } from "../lib/offlineOcrWorker";
import { OfflineAnalysisResult, analyzeOfflineText } from "../lib/offlineAnalysisEngine";

export default function Home() {
  const [spatialMode, setSpatialMode] = useState<"antigravity" | "cyber" | "minimal">("antigravity");
  const [showHologram, setShowHologram] = useState<boolean>(true);
  const [userId, setUserId] = useState<string>("");
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [streamEvent, setStreamEvent] = useState<StreamEvent | null>(null);
  const [result, setResult] = useState<FinalDecisionSupportResult | null>(null);
  const [primaryFile, setPrimaryFile] = useState<File | null>(null);
  const [primaryDocType, setPrimaryDocType] = useState<DocumentClassification>("other");
  const [documentText, setDocumentText] = useState<string>("");
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [selectedFlag, setSelectedFlag] = useState<DecisionFlag | null>(null);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<MobileFailureState | null>(null);
  const [appMode, setAppMode] = useState<"audit" | "compare" | "dealer_response">("audit");
  const [multiQuoteResult, setMultiQuoteResult] = useState<MultiQuoteComparisonResult | null>(null);
  const [cachedDealerResult, setCachedDealerResult] = useState<DealerResponseAnalysisResult | null>(null);
  const [offlineRefreshTrigger, setOfflineRefreshTrigger] = useState<number>(0);
  const [onDeviceResult, setOnDeviceResult] = useState<OfflineAnalysisResult | null>(null);
  const [isOnDeviceRunning, setIsOnDeviceRunning] = useState<boolean>(false);
  const abortControllerRef = React.useRef<AbortController | null>(null);


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

  // Initialize authenticated tenant session and load verified profile
  useEffect(() => {
    const initTenantSession = async () => {
      try {
        const profile = await getCurrentUserProfile();
        if (profile?.user_id) {
          setUserId(profile.user_id);
          localStorage.setItem("byp_user_id", profile.user_id);
          return;
        }
      } catch {}
      const savedId = localStorage.getItem("byp_user_id");
      if (savedId) {
        setUserId(savedId);
      } else {
        const fresh = await createFreshSession().catch(() => null);
        if (fresh) {
          setUserId(fresh.user_id);
          localStorage.setItem("byp_user_id", fresh.user_id);
        } else {
          const fallback = generateUUID();
          setUserId(fallback);
          localStorage.setItem("byp_user_id", fallback);
        }
      }
    };
    initTenantSession();

    const savedRecords = localStorage.getItem("byp_rag_records");
    if (savedRecords) {
      try {
        setRagRecords(JSON.parse(savedRecords));
      } catch {
        // ignore
      }
    }

    if (typeof window !== "undefined") {
      (window as any).__BYP_OFFLINE_ENGINE__ = {
        analyzeOfflineText,
        runOnDeviceOfflineAnalysis,
      };
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

  const handleNewSession = async () => {
    try {
      const fresh = await createFreshSession();
      setUserId(fresh.user_id);
      localStorage.setItem("byp_user_id", fresh.user_id);
      handleReset();
    } catch (e) {
      console.warn("Failed to create fresh verified session:", e);
    }
  };

  const handleUpdateUserId = (newId: string) => {
    clearAuthToken();
    setUserId(newId);
    localStorage.setItem("byp_user_id", newId);
  };

  const handleRecordAdded = (record: RagRecord) => {
    const updated = [record, ...ragRecords];
    setRagRecords(updated);
    localStorage.setItem("byp_rag_records", JSON.stringify(updated));
  };

  // Upload & Analyze Handler with request cancellation and race condition protection
  const handleFileSelect = async (
    file: File,
    docType: DocumentClassification,
    supportingFile?: File | null
  ) => {
    if (isProcessing) return;

    // Abort any prior in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsProcessing(true);
    setResult(null);
    setSelectedFlag(null);
    setSelectedComponentId(null);
    setStreamEvent(null);
    setAnalysisError(null);
    setPrimaryFile(file);
    setPrimaryDocType(docType);

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
      let data: FinalDecisionSupportResult;
      try {
        data = await analyzeDocumentStream(
          file,
          userId,
          docType,
          (event) => {
            if (!controller.signal.aborted) {
              setStreamEvent(event);
            }
          },
          supportingFile,
          controller.signal
        );
      } catch (streamErr: any) {
        if (streamErr?.name === "AbortError" || controller.signal.aborted) return;
        console.warn("SSE stream failed, falling back to direct POST /analyze", streamErr);
        data = await analyzeDocument(file, userId, docType, supportingFile, controller.signal);
      }
      if (!controller.signal.aborted) {
        setResult(data);
        try {
          await saveAnalysisToCache({
            id: generateUUID(),
            type: "single_analysis",
            title: `Audit: ${file.name}`,
            filename: file.name,
            docType: docType,
            timestamp: new Date().toISOString(),
            currency: data.document?.currency || data.semantic_financial_structure?.currency || "INR",
            totalAmount: Number(data.document?.total_amount?.normalized_value || data.semantic_financial_structure?.stated_total || 0),
            statusVerdict: data.flags?.[0]?.severity || "COMPLETED",
            discrepancyCount: data.flags?.length || 0,
            resultPayload: data,
          });
          setOfflineRefreshTrigger((prev) => prev + 1);
        } catch (cacheErr) {
          console.warn("Could not save report to IndexedDB cache:", cacheErr);
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError" || controller.signal.aborted) {
        return;
      }

      // If user is offline or network error, execute genuine on-device WebWorker analysis and queue in local IndexedDB
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        setIsProcessing(false);
        setIsOnDeviceRunning(true);
        try {
          const offlineRes = await runOnDeviceOfflineAnalysis(file, (pct, statusText) => {
            setStreamEvent({
              stage: "spatial_ocr",
              status: "processing",
              progress: pct,
              message: statusText,
            });
          });
          setOnDeviceResult(offlineRes);
          setIsOnDeviceRunning(false);
          setStreamEvent(null);

          const fileBlobs = [{ name: file.name, type: file.type, blob: file }];
          if (supportingFile) {
            fileBlobs.push({ name: supportingFile.name, type: supportingFile.type, blob: supportingFile });
          }
          await enqueueOfflineAudit({
            id: generateUUID(),
            type: "single_analysis",
            filename: file.name,
            files: fileBlobs,
            params: { userId, docType },
            createdAt: new Date().toISOString(),
            status: "pending",
            retryCount: 0,
          });
          setOfflineRefreshTrigger((prev) => prev + 1);
          return;
        } catch (queueErr) {
          console.warn("Could not complete offline on-device analysis:", queueErr);
          setIsOnDeviceRunning(false);
          setStreamEvent(null);
        }

        setAnalysisError({
          title: "Offline Mode Active",
          message:
            "Device is currently offline. This document has been queued in your local IndexedDB and will automatically analyze as soon as connection is restored.",
          onRetry: () => handleFileSelect(file, docType, supportingFile),
          onRetake: () => {
            setAnalysisError(null);
            handleReset();
          },
          onChooseFile: () => {
            setAnalysisError(null);
            handleReset();
          },
        });
        return;
      }

      setAnalysisError({
        title: "Document Analysis Rejected",
        message:
          err.message ||
          "Document could not be verified by the 7-stage engine. Please ensure the scan is clear, flat, and legible.",
        onRetry: () => handleFileSelect(file, docType, supportingFile),
        onRetake: () => {
          setAnalysisError(null);
          handleReset();
        },
        onChooseFile: () => {
          setAnalysisError(null);
          handleReset();
        },
      });
    } finally {
      if (!controller.signal.aborted) {
        setIsProcessing(false);
      }
    }
  };

  const handleAddSupportingDocument = async (supportingFile: File) => {
    if (!primaryFile || isProcessing) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsProcessing(true);
    setStreamEvent(null);
    setAnalysisError(null);
    try {
      let data: FinalDecisionSupportResult;
      try {
        data = await analyzeDocumentStream(
          primaryFile,
          userId,
          primaryDocType,
          (event) => {
            if (!controller.signal.aborted) {
              setStreamEvent(event);
            }
          },
          supportingFile,
          controller.signal
        );
      } catch (streamErr: any) {
        if (streamErr?.name === "AbortError" || controller.signal.aborted) return;
        console.warn("SSE stream fallback to direct POST /analyze for supporting doc", streamErr);
        data = await analyzeDocument(primaryFile, userId, primaryDocType, supportingFile, controller.signal);
      }
      if (!controller.signal.aborted) {
        setResult(data);
      }
    } catch (err: any) {
      if (err?.name === "AbortError" || controller.signal.aborted) {
        return;
      }
      setAnalysisError({
        title: "Supporting Document Analysis Failed",
        message: err.message || "Failed to compare with supporting document.",
        onRetry: () => handleAddSupportingDocument(supportingFile),
        onChooseFile: () => setAnalysisError(null),
      });
    } finally {
      if (!controller.signal.aborted) {
        setIsProcessing(false);
      }
    }
  };

  const handleReset = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
    }
    setPrimaryFile(null);
    setResult(null);
    setSelectedFlag(null);
    setSelectedComponentId(null);
    setDocumentText("");
    setImagePreviewUrl(null);
    setStreamEvent(null);
    setAnalysisError(null);
    setIsProcessing(false);
    setOnDeviceResult(null);
    setIsOnDeviceRunning(false);
  };

  const handleLoadCachedAnalysis = (record: CachedAnalysisRecord) => {
    handleReset();
    if (record.type === "single_analysis") {
      setAppMode("audit");
      setResult(record.resultPayload);
      setPrimaryDocType(record.docType || "other");
    } else if (record.type === "compare_quotes") {
      setAppMode("compare");
      setMultiQuoteResult(record.resultPayload);
    } else if (record.type === "dealer_response") {
      setAppMode("dealer_response");
      setCachedDealerResult(record.resultPayload);
    }
  };

  const handleRunOnDeviceQueuedItem = async (fileBlob: Blob, filename: string) => {
    handleReset();
    setIsOnDeviceRunning(true);
    setAppMode("audit");
    try {
      const file = new File([fileBlob], filename, { type: fileBlob.type || "application/octet-stream" });
      setPrimaryFile(file);
      if (file.type.startsWith("image/")) {
        setImagePreviewUrl(URL.createObjectURL(file));
      }
      const offlineRes = await runOnDeviceOfflineAnalysis(file, (pct, statusText) => {
        setStreamEvent({
          stage: "spatial_ocr",
          status: "processing",
          progress: pct,
          message: statusText,
        });
      });
      setOnDeviceResult(offlineRes);
    } catch (err: any) {
      console.error("Could not run on-device analysis:", err);
      setAnalysisError({
        title: "On-Device Analysis Failed",
        message: err?.message || "Could not complete local document analysis.",
        onRetry: () => handleRunOnDeviceQueuedItem(fileBlob, filename),
      });
    } finally {
      setIsOnDeviceRunning(false);
      setStreamEvent(null);
    }
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

  const handleInspectFieldId = (fieldId: string, label?: string) => {
    const comp = result?.document?.cost_breakdown?.find(
      (c) => c.amount?.field_id === fieldId || c.component_id === fieldId
    );
    if (comp?.amount?.provenance?.bounding_box) {
      handleSelectComponent(comp);
      return;
    }
    const item = result?.document?.line_items?.find(
      (li) => li.total_price?.field_id === fieldId || li.unit_price?.field_id === fieldId
    );
    const box = item?.total_price?.provenance?.bounding_box || item?.unit_price?.provenance?.bounding_box;
    if (box) {
      setSelectedFlag({
        flag_id: fieldId,
        claim_type: "requires_verification",
        label: item?.description?.normalized_value ? String(item.description.normalized_value) : label || fieldId,
        message: `${label || fieldId}`,
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
      return;
    }
    const flag = result?.flags?.find(
      (f) => f.field_ids?.includes(fieldId) || f.label.toLowerCase() === label?.toLowerCase()
    );
    if (flag) {
      setSelectedFlag(flag);
      setTimeout(() => {
        const viewer = document.getElementById("document-evidence-viewer");
        if (viewer) {
          viewer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 50);
    }
  };

  const handleSelectLineItem = (item: any) => {
    const fieldId = item.total_price?.field_id || item.unit_price?.field_id;
    const box = item.total_price?.provenance?.bounding_box || item.unit_price?.provenance?.bounding_box;
    const desc = item.description?.normalized_value ? String(item.description.normalized_value) : "Line Item";
    if (box) {
      setSelectedFlag({
        flag_id: fieldId || generateUUID(),
        claim_type: "requires_verification",
        label: desc,
        message: `${desc}: ${item.total_price?.normalized_value ?? ""}`,
        severity: "INFO",
        field_ids: fieldId ? [fieldId] : [],
        bounding_boxes: [box],
      });
      setTimeout(() => {
        const viewer = document.getElementById("document-evidence-viewer");
        if (viewer) {
          viewer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 50);
    }
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
    <div className="relative min-h-screen bg-[#070b14] text-slate-100 flex flex-col pb-24 md:pb-16 selection:bg-brand-500/30 overflow-x-hidden">
      {/* 3D Dynamic Spatial Canvas Background */}
      <Spatial3DCanvas mode={spatialMode} />

      {/* 3D Special Animated Cursor with Particle Wake */}
      <SpatialCursor3D />

      {/* 1. Mobile Header & Application Identity */}
      <Navbar
        userId={userId}
        onUpdateUserId={handleUpdateUserId}
        onNewSession={handleNewSession}
        ragCount={ragRecords.length}
        onOpenRag={() => setIsRagOpen(true)}
        onOpenOkf={() => setIsOkfOpen(true)}
        isBackendHealthy={isBackendHealthy}
        onTriggerScan={() => {
          handleReset();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        onLoadCachedAnalysis={handleLoadCachedAnalysis}
        onRunOnDeviceAnalysis={handleRunOnDeviceQueuedItem}
        offlineRefreshTrigger={offlineRefreshTrigger}
      />

      <main className="relative z-10 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Real Failure State Banner & Recovery Actions */}
        {analysisError && (
          <MobileFailureRecovery
            error={analysisError}
            onDismiss={() => setAnalysisError(null)}
          />
        )}

        {/* On-Device Offline Verification HUD Card */}
        {onDeviceResult && (
          <OnDeviceAnalysisCard
            result={onDeviceResult}
            onQueueForCloud={() => {
              if (primaryFile) {
                handleFileSelect(primaryFile, primaryDocType);
              }
            }}
          />
        )}

        {/* Multi-Quote Comparison Result Matrix */}
        {multiQuoteResult ? (
          <div className="space-y-6 animate-in fade-in duration-300">
            <MultiQuoteComparisonCard
              comparison={multiQuoteResult}
              onClose={() => setMultiQuoteResult(null)}
            />
          </div>
        ) : !result ? (
          /* Pre-Analysis Responsive Cockpit: 2-Column on Desktop (>=1024px), Mobile-First Stack on Phones */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column (lg:col-span-7): Headline, Mode Navigation & Primary Capture Area */}
            <div className="lg:col-span-7 space-y-6">
              <div className="space-y-3">
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-lg shadow-cyan-500/10">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  <span>3D Spatial Geometry • Deterministic Arithmetic Verification</span>
                </div>
                <h1 className="text-2xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-tight">
                  Inspect Every Number Before You Pay
                </h1>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-xl">
                  Scan vehicle quotations, medical bills, or contracts. Explore hidden markups in exploded 3D layers, verify mathematical integrity, and protect your finances with zero fake data.
                </p>
              </div>

              {/* Mode Selector Tabs (3D Spatial Navigation) */}
              <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
                <button
                  type="button"
                  onClick={() => {
                    setAppMode("audit");
                    setCachedDealerResult(null);
                  }}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                    appMode === "audit"
                      ? "bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/50 shadow-md shadow-cyan-500/20"
                      : "bg-slate-900/80 text-slate-400 border border-white/5 hover:text-white hover:border-white/20 hover:bg-slate-800/80"
                  }`}
                >
                  <FileSearch className="w-4 h-4 text-cyan-400" />
                  <span>Document Scan & Math Audit</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAppMode("compare");
                    setCachedDealerResult(null);
                  }}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                    appMode === "compare"
                      ? "bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/50 shadow-md shadow-cyan-500/20"
                      : "bg-slate-900/80 text-slate-400 border border-white/5 hover:text-white hover:border-white/20 hover:bg-slate-800/80"
                  }`}
                >
                  <Scale className="w-4 h-4 text-blue-400" />
                  <span>Compare 2–5 Quotations</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAppMode("dealer_response");
                  }}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                    appMode === "dealer_response"
                      ? "bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-300 border border-purple-500/50 shadow-md shadow-purple-500/20"
                      : "bg-slate-900/80 text-slate-400 border border-white/5 hover:text-white hover:border-white/20 hover:bg-slate-800/80"
                  }`}
                >
                  <MessageSquareQuote className="w-4 h-4 text-purple-400" />
                  <span>Dealer Counter-Offer Parser</span>
                </button>
              </div>

              {/* Mode Specific Upload or Parser */}
              {appMode === "dealer_response" ? (
                <DealerResponseParserCard
                  userId={userId}
                  currency="INR"
                  initialResult={cachedDealerResult}
                  onParsed={async (parsed) => {
                    try {
                      await saveAnalysisToCache({
                        id: generateUUID(),
                        type: "dealer_response",
                        title: `Dealer Response Analysis`,
                        filename: "Dealer Response",
                        timestamp: new Date().toISOString(),
                        currency: parsed.currency || "INR",
                        totalAmount: parsed.calculated_new_total ?? parsed.stated_counter_total,
                        statusVerdict: parsed.math_reconciliation_status,
                        discrepancyCount: parsed.extracted_actions?.length || 0,
                        resultPayload: parsed,
                      });
                      setOfflineRefreshTrigger((prev) => prev + 1);
                    } catch (err) {
                      console.warn("Could not cache dealer response:", err);
                    }
                  }}
                />
              ) : appMode === "compare" ? (
                <MultiQuoteUploadDropzone
                  userId={userId}
                  onComparisonComplete={async (comp) => {
                    setMultiQuoteResult(comp);
                    try {
                      await saveAnalysisToCache({
                        id: generateUUID(),
                        type: "compare_quotes",
                        title: `Comparison Matrix (${comp.quotes.length} Quotes)`,
                        filename: comp.quotes.map((q) => q.filename || q.vendor_name || q.document_id).join(", "),
                        timestamp: new Date().toISOString(),
                        currency: comp.primary_currency,
                        totalAmount: comp.min_total,
                        statusVerdict: comp.currency_mismatch ? "CURRENCY_MISMATCH" : "COMPARED",
                        discrepancyCount: comp.aligned_components?.length || 0,
                        resultPayload: comp,
                      });
                      setOfflineRefreshTrigger((prev) => prev + 1);
                    } catch (err) {
                      console.warn("Could not cache multi-quote result:", err);
                    }
                  }}
                />
              ) : (
                <div id="upload-dropzone-section" className="scroll-mt-24 space-y-4">
                  <Dropzone
                    onFileSelect={handleFileSelect}
                    isProcessing={isProcessing}
                    selectedPrimaryFile={primaryFile}
                    onClearPrimaryFile={handleReset}
                  />
                  <PipelineProgress isProcessing={isProcessing} currentEvent={streamEvent} />
                </div>
              )}
            </div>

            {/* Right Column (lg:col-span-5): Sticky 3D Spatial Holographic Chamber */}
            <div className="lg:col-span-5 lg:sticky lg:top-24 space-y-4">
              {showHologram && (
                <div id="hologram-3d-stage" className="animate-in fade-in duration-300">
                  <Holographic3DScanner
                    result={null}
                    imagePreviewUrl={null}
                    okfRules={okfRules}
                    onTriggerUpload={() => {
                      const el = document.getElementById("upload-dropzone-section");
                      if (el) el.scrollIntoView({ behavior: "smooth" });
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        ) : (


          <div className="space-y-6 animate-in fade-in duration-300">
            {isProcessing && (
              <PipelineProgress isProcessing={isProcessing} currentEvent={streamEvent} />
            )}

            {/* 3D Holographic Evidence Stage (100% Real Audited Document) */}
            {showHologram && (
              <div className="animate-in fade-in duration-300">
                <Holographic3DScanner
                  result={result}
                  imagePreviewUrl={imagePreviewUrl}
                  okfRules={okfRules}
                  onSelectFlag={setSelectedFlag}
                  onSelectComponent={handleSelectComponent}
                  onTriggerUpload={handleReset}
                />
              </div>
            )}

            {/* Decision Support Experience */}
            {result.before_you_pay_summary ? (
              <BeforeYouPayFinalSummaryView
                summary={result.before_you_pay_summary}
                result={result}
                evidenceResult={result.evidence_first_result}
                imagePreviewUrl={imagePreviewUrl}
                documentText={documentText}
                onReset={handleReset}
                onAddSupportingDocument={handleAddSupportingDocument}
                onSelectComponent={handleSelectComponent}
                onSelectLineItem={handleSelectLineItem}
                onInspectFieldId={handleInspectFieldId}
              />
            ) : (
              <>
                {/* Fallback for documents without before_you_pay_summary */}
                <VerdictBanner
                  result={result}
                  onReset={handleReset}
                  onSelectComponent={handleSelectComponent}
                  onSelectLineItem={handleSelectLineItem}
                  onAddSupportingDocument={handleAddSupportingDocument}
                />

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  <div className="lg:col-span-7 space-y-6">
                    {result.document?.cost_breakdown && result.document.cost_breakdown.length > 0 ? (
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
                      />
                    ) : extractedItems.length > 0 ? (
                      <LineItemsTable items={extractedItems} currency={result?.document?.currency} />
                    ) : null}

                    <WaysToReviewCostCard
                      components={result.document?.cost_breakdown || []}
                      lineItems={result.document?.line_items}
                      extraCostAnalysis={result.extra_cost_analysis}
                      costReductionSummary={result.cost_reduction_summary}
                      smartQuestions={result.smart_questions}
                      validationChecks={result.validation_checks}
                      currency={result.document?.currency}
                      onInspectEvidence={handleInspectFieldId}
                    />

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
                      onSelectFieldId={handleInspectFieldId}
                    />
                  </div>

                  <div className="lg:col-span-5 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
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
              </>
            )}
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

      {/* 3D Interactive Spatial HUD Controller */}
      <SpatialHUD3D
        currentMode={spatialMode}
        onChangeMode={setSpatialMode}
        showHologram={showHologram}
        onToggleHologram={() => setShowHologram((prev) => !prev)}
      />

      {/* Non-committal Legal Disclaimer */}
      <footer className="mt-12 pt-6 pb-24 md:pb-12 border-t border-white/10 text-center text-[11px] text-slate-500 max-w-lg mx-auto px-4 leading-relaxed">
        <strong>Automated Decision Support:</strong> Uses spatial OCR geometry and deterministic Python arithmetic. Does not constitute formal legal or tax counsel. Final payment authorization rests with you.
      </footer>
    </div>
  );
}
