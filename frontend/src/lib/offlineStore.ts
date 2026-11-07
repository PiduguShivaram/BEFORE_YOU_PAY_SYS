// Zero-dependency IndexedDB Offline Store for Before You Pay
import { DocumentClassification, FinalDecisionSupportResult, MultiQuoteComparisonResult, DealerResponseAnalysisResult } from "./types";
import { analyzeDocument, compareQuotes, parseDealerResponse } from "./api";

const DB_NAME = "before_you_pay_offline_db";
const DB_VERSION = 1;

export interface CachedAnalysisRecord {
  id: string;
  type: "single_analysis" | "compare_quotes" | "dealer_response";
  title: string;
  filename: string;
  docType?: DocumentClassification;
  timestamp: string;
  currency?: string;
  totalAmount?: number | null;
  statusVerdict?: string;
  discrepancyCount: number;
  resultPayload: FinalDecisionSupportResult | MultiQuoteComparisonResult | DealerResponseAnalysisResult | any;
}

export interface StoredFileData {
  name: string;
  type: string;
  blob: Blob;
}

export interface OfflineQueueItem {
  id: string;
  type: "single_analysis" | "compare_quotes" | "dealer_response";
  filename: string;
  files: StoredFileData[];
  params: {
    userId: string;
    docType?: DocumentClassification;
    originalTotal?: number | null;
    dealerText?: string;
    currency?: string;
  };
  createdAt: string;
  status: "pending" | "syncing" | "completed" | "failed";
  errorMessage?: string | null;
  retryCount: number;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !("indexedDB" in window)) {
      return reject(new Error("IndexedDB is not supported in this environment"));
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db = (event.target as IDBOpenDBRequest).result;

      if (!db.objectStoreNames.contains("cached_analyses")) {
        const analysisStore = db.createObjectStore("cached_analyses", { keyPath: "id" });
        analysisStore.createIndex("timestamp", "timestamp", { unique: false });
        analysisStore.createIndex("type", "type", { unique: false });
      }

      if (!db.objectStoreNames.contains("offline_queue")) {
        const queueStore = db.createObjectStore("offline_queue", { keyPath: "id" });
        queueStore.createIndex("createdAt", "createdAt", { unique: false });
        queueStore.createIndex("status", "status", { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// -------------------------------------------------------------
// Cached Analysis Helpers
// -------------------------------------------------------------

export async function saveAnalysisToCache(record: CachedAnalysisRecord): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cached_analyses", "readwrite");
    const store = tx.objectStore("cached_analyses");
    const req = store.put(record);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getAllCachedAnalyses(): Promise<CachedAnalysisRecord[]> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cached_analyses", "readonly");
    const store = tx.objectStore("cached_analyses");
    const req = store.getAll();
    req.onsuccess = () => {
      const records = (req.result || []) as CachedAnalysisRecord[];
      // Sort newest first
      records.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      resolve(records);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function getCachedAnalysisById(id: string): Promise<CachedAnalysisRecord | null> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cached_analyses", "readonly");
    const store = tx.objectStore("cached_analyses");
    const req = store.get(id);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

export async function deleteCachedAnalysis(id: string): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cached_analyses", "readwrite");
    const store = tx.objectStore("cached_analyses");
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function clearAllCachedAnalyses(): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cached_analyses", "readwrite");
    const store = tx.objectStore("cached_analyses");
    const req = store.clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// -------------------------------------------------------------
// Offline Queue Helpers
// -------------------------------------------------------------

export async function enqueueOfflineAudit(item: OfflineQueueItem): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("offline_queue", "readwrite");
    const store = tx.objectStore("offline_queue");
    const req = store.put(item);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getAllOfflineQueueItems(): Promise<OfflineQueueItem[]> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("offline_queue", "readonly");
    const store = tx.objectStore("offline_queue");
    const req = store.getAll();
    req.onsuccess = () => {
      const items = (req.result || []) as OfflineQueueItem[];
      items.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
      resolve(items);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function removeOfflineQueueItem(id: string): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("offline_queue", "readwrite");
    const store = tx.objectStore("offline_queue");
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function updateOfflineQueueStatus(
  id: string,
  status: OfflineQueueItem["status"],
  errorMessage?: string | null
): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("offline_queue", "readwrite");
    const store = tx.objectStore("offline_queue");
    const getReq = store.get(id);

    getReq.onsuccess = () => {
      const item = getReq.result as OfflineQueueItem;
      if (!item) return resolve();
      item.status = status;
      if (errorMessage !== undefined) item.errorMessage = errorMessage;
      if (status === "syncing") item.retryCount += 1;
      const putReq = store.put(item);
      putReq.onsuccess = () => resolve();
      putReq.onerror = () => reject(putReq.error);
    };
    getReq.onerror = () => reject(getReq.error);
  });
}

// -------------------------------------------------------------
// Queue Sync Processor
// -------------------------------------------------------------

export async function processOfflineQueue(
  onItemProgress?: (item: OfflineQueueItem, status: string, result?: any) => void
): Promise<{ processed: number; failed: number }> {
  const items = await getAllOfflineQueueItems();
  const pending = items.filter((i) => i.status === "pending" || i.status === "failed");

  let processed = 0;
  let failed = 0;

  for (const item of pending) {
    try {
      await updateOfflineQueueStatus(item.id, "syncing");
      if (onItemProgress) onItemProgress(item, "syncing");

      if (item.type === "single_analysis") {
        const primaryFile = new File([item.files[0].blob], item.files[0].name, {
          type: item.files[0].type,
        });
        const supportingFile =
          item.files.length > 1
            ? new File([item.files[1].blob], item.files[1].name, { type: item.files[1].type })
            : null;

        const res = await analyzeDocument(
          primaryFile,
          item.params.userId,
          item.params.docType || "other",
          supportingFile
        );

        // Cache the newly analyzed result
        await saveAnalysisToCache({
          id: item.id,
          type: "single_analysis",
          title: `Audit: ${primaryFile.name}`,
          filename: primaryFile.name,
          docType: item.params.docType || "other",
          timestamp: new Date().toISOString(),
          currency: res.document?.currency || res.semantic_financial_structure?.currency || "INR",
          totalAmount: Number(res.document?.total_amount?.normalized_value || res.semantic_financial_structure?.stated_total || 0),
          statusVerdict: res.flags?.[0]?.severity || "COMPLETED",
          discrepancyCount: res.flags?.length || 0,
          resultPayload: res,
        });

        await removeOfflineQueueItem(item.id);
        processed++;
        if (onItemProgress) onItemProgress(item, "completed", res);
      } else if (item.type === "compare_quotes") {
        const files = item.files.map((f) => new File([f.blob], f.name, { type: f.type }));
        const res = await compareQuotes(files, item.params.userId);

        await saveAnalysisToCache({
          id: item.id,
          type: "compare_quotes",
          title: `Comparison: ${files.map((f) => f.name).join(" vs ")}`,
          filename: res.quotes.map((q) => q.filename || q.vendor_name || q.document_id).join(", "),
          timestamp: new Date().toISOString(),
          currency: res.primary_currency,
          totalAmount: res.min_total,
          statusVerdict: res.currency_mismatch ? "CURRENCY_MISMATCH" : "COMPARED",
          discrepancyCount: res.aligned_components?.length || 0,
          resultPayload: res,
        });

        await removeOfflineQueueItem(item.id);
        processed++;
        if (onItemProgress) onItemProgress(item, "completed", res);
      } else if (item.type === "dealer_response") {
        const quoteFile =
          item.files.length > 0
            ? new File([item.files[0].blob], item.files[0].name, { type: item.files[0].type })
            : null;

        const res = await parseDealerResponse(
          item.params.dealerText || "",
          item.params.userId,
          item.params.originalTotal,
          item.params.currency || "INR",
          quoteFile
        );

        await saveAnalysisToCache({
          id: item.id,
          type: "dealer_response",
          title: `Dealer Response Analysis`,
          filename: item.filename,
          timestamp: new Date().toISOString(),
          currency: res.currency || item.params.currency || "INR",
          totalAmount: res.calculated_new_total ?? res.stated_counter_total,
          statusVerdict: res.math_reconciliation_status,
          discrepancyCount: res.extracted_actions?.length || 0,
          resultPayload: res,
        });

        await removeOfflineQueueItem(item.id);
        processed++;
        if (onItemProgress) onItemProgress(item, "completed", res);
      }
    } catch (err: any) {
      console.error(`Offline sync failed for item ${item.id}:`, err);
      await updateOfflineQueueStatus(item.id, "failed", err?.message || "Sync network error");
      failed++;
      if (onItemProgress) onItemProgress(item, "failed");
    }
  }

  return { processed, failed };
}
