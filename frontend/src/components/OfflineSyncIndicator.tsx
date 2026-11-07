"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Wifi,
  WifiOff,
  RefreshCw,
  Clock,
  Trash2,
  FileText,
  AlertTriangle,
  CheckCircle2,
  HardDrive,
  Database,
  ArrowRight,
  X,
  Layers,
} from "lucide-react";
import {
  CachedAnalysisRecord,
  OfflineQueueItem,
  getAllCachedAnalyses,
  getAllOfflineQueueItems,
  removeOfflineQueueItem,
  deleteCachedAnalysis,
  clearAllCachedAnalyses,
  processOfflineQueue,
} from "../lib/offlineStore";
import { formatCurrency } from "../lib/utils";

interface OfflineSyncIndicatorProps {
  onLoadCachedAnalysis?: (record: CachedAnalysisRecord) => void;
  refreshTrigger?: number;
}

export function OfflineSyncIndicator({
  onLoadCachedAnalysis,
  refreshTrigger = 0,
}: OfflineSyncIndicatorProps) {
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [queueItems, setQueueItems] = useState<OfflineQueueItem[]>([]);
  const [cachedAudits, setCachedAudits] = useState<CachedAnalysisRecord[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"queue" | "cached">("queue");
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncStatusMsg, setSyncStatusMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [queue, cached] = await Promise.all([
        getAllOfflineQueueItems(),
        getAllCachedAnalyses(),
      ]);
      setQueueItems(queue);
      setCachedAudits(cached);
    } catch (err) {
      console.warn("Could not read from IndexedDB:", err);
    }
  }, []);

  const handleSyncAll = useCallback(async () => {
    if (!navigator.onLine || isSyncing) return;
    setIsSyncing(true);
    setSyncStatusMsg("Processing offline queue...");

    try {
      const { processed, failed } = await processOfflineQueue(
        (item, status, result) => {
          if (status === "completed" && result && onLoadCachedAnalysis) {
            // Optionally notify
          }
        }
      );
      await loadData();
      if (failed > 0) {
        setSyncStatusMsg(`Sync completed: ${processed} synced, ${failed} failed.`);
      } else if (processed > 0) {
        setSyncStatusMsg(`Successfully synced ${processed} item(s)!`);
      } else {
        setSyncStatusMsg("Queue is up to date.");
      }
    } catch (e: any) {
      setSyncStatusMsg(`Sync error: ${e?.message || "Network error"}`);
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncStatusMsg(null), 4000);
    }
  }, [isSyncing, loadData, onLoadCachedAnalysis]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsOnline(navigator.onLine);

      const handleOnline = async () => {
        setIsOnline(true);
        // Automatic sync when connection returns
        const queue = await getAllOfflineQueueItems();
        const pending = queue.filter((q) => q.status === "pending" || q.status === "failed");
        if (pending.length > 0) {
          handleSyncAll();
        }
      };

      const handleOffline = () => {
        setIsOnline(false);
      };

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      loadData();

      const interval = setInterval(loadData, 5000);

      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
        clearInterval(interval);
      };
    }
  }, [loadData, handleSyncAll]);

  useEffect(() => {
    loadData();
  }, [refreshTrigger, loadData]);

  const handleRemoveQueueItem = async (id: string) => {
    await removeOfflineQueueItem(id);
    await loadData();
  };

  const handleDeleteCachedAudit = async (id: string) => {
    await deleteCachedAnalysis(id);
    await loadData();
  };

  const handleClearAllCached = async () => {
    if (confirm("Are you sure you want to clear all offline cached audits?")) {
      await clearAllCachedAnalyses();
      await loadData();
    }
  };

  const pendingCount = queueItems.filter(
    (q) => q.status === "pending" || q.status === "failed" || q.status === "syncing"
  ).length;

  return (
    <>
      {/* Floating Network & Offline Status Pill */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => {
            if (pendingCount > 0) {
              setActiveTab("queue");
            } else {
              setActiveTab("cached");
            }
            setIsDrawerOpen(true);
          }}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all backdrop-blur-md border shadow-lg ${
            !isOnline
              ? "bg-amber-950/80 border-amber-500/40 text-amber-300 hover:bg-amber-900/80 animate-pulse"
              : pendingCount > 0
              ? "bg-blue-950/80 border-blue-500/40 text-blue-300 hover:bg-blue-900/80"
              : "bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
          }`}
          title="Click to view offline queue & cached audits"
        >
          {isOnline ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-amber-400" />
          )}

          <span>{isOnline ? "Online" : "Offline Mode"}</span>

          {pendingCount > 0 && (
            <span className="flex items-center justify-center px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold border border-amber-500/40">
              {pendingCount} queued
            </span>
          )}

          {cachedAudits.length > 0 && pendingCount === 0 && (
            <span className="flex items-center gap-1 text-[11px] text-slate-400">
              <Database className="w-3 h-3 text-slate-400" />
              {cachedAudits.length}
            </span>
          )}
        </button>
      </div>

      {/* Offline Management Drawer / Modal */}
      {isDrawerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 px-6 border-b border-slate-800 bg-slate-950/50">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                  <HardDrive className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    Offline Sync & Local Cache
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        isOnline
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {isOnline ? "Connected" : "Offline"}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    IndexedDB zero-egress local store for field audits & dealership reviews
                  </p>
                </div>
              </div>

              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-2 p-2 px-6 border-b border-slate-800 bg-slate-900/50">
              <button
                onClick={() => setActiveTab("queue")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === "queue"
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                Offline Queue
                {pendingCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-bold">
                    {pendingCount}
                  </span>
                )}
              </button>

              <button
                onClick={() => setActiveTab("cached")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === "cached"
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                Cached Audits
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px]">
                  {cachedAudits.length}
                </span>
              </button>

              <div className="ml-auto flex items-center gap-2">
                {activeTab === "queue" && (
                  <button
                    onClick={handleSyncAll}
                    disabled={!isOnline || isSyncing || pendingCount === 0}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                      isOnline && pendingCount > 0
                        ? "bg-blue-600 hover:bg-blue-500 text-white shadow"
                        : "bg-slate-800 text-slate-500 cursor-not-allowed"
                    }`}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
                    {isSyncing ? "Syncing..." : "Sync All Now"}
                  </button>
                )}
                {activeTab === "cached" && cachedAudits.length > 0 && (
                  <button
                    onClick={handleClearAllCached}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-rose-400 hover:bg-rose-950/30 border border-rose-900/30 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Clear Cache
                  </button>
                )}
              </div>
            </div>

            {/* Sync Status Banner */}
            {syncStatusMsg && (
              <div className="p-3 px-6 bg-blue-950/40 border-b border-blue-900/30 text-xs text-blue-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0" />
                <span>{syncStatusMsg}</span>
              </div>
            )}

            {/* Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-3">
              {activeTab === "queue" ? (
                queueItems.length === 0 ? (
                  <div className="text-center py-12 text-slate-500">
                    <CheckCircle2 className="w-10 h-10 text-slate-600 mx-auto mb-2 opacity-50" />
                    <p className="text-sm font-medium text-slate-400">Queue is empty</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Scans taken without internet will automatically queue here and sync when reconnected.
                    </p>
                  </div>
                ) : (
                  queueItems.map((item) => (
                    <div
                      key={item.id}
                      className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0 mt-0.5">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-slate-200">
                              {item.filename || "Uploaded Quotation"}
                            </span>
                            <span
                              className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                                item.status === "syncing"
                                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                  : item.status === "failed"
                                  ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                                  : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                              }`}
                            >
                              {item.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                            <span>Type: {item.type.replace("_", " ")}</span>
                            <span>•</span>
                            <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                            {item.retryCount > 0 && <span>• Retries: {item.retryCount}</span>}
                          </div>
                          {item.errorMessage && (
                            <p className="text-xs text-rose-400 mt-1 flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              {item.errorMessage}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        <button
                          onClick={() => handleRemoveQueueItem(item.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-900 rounded-lg transition"
                          title="Remove from queue"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))
                )
              ) : cachedAudits.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <Database className="w-10 h-10 text-slate-600 mx-auto mb-2 opacity-50" />
                  <p className="text-sm font-medium text-slate-400">No cached audits yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Every analyzed document is saved to local IndexedDB for instant offline review.
                  </p>
                </div>
              ) : (
                cachedAudits.map((record) => (
                  <div
                    key={record.id}
                    className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-200">
                            {record.title}
                          </span>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase tracking-wider">
                            {record.type.replace("_", " ")}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                          {record.totalAmount != null && (
                            <span className="font-semibold text-emerald-400">
                              {formatCurrency(record.totalAmount, record.currency || "INR")}
                            </span>
                          )}
                          <span>•</span>
                          <span>
                            {new Date(record.timestamp).toLocaleDateString()}{" "}
                            {new Date(record.timestamp).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                          {record.discrepancyCount > 0 && (
                            <>
                              <span>•</span>
                              <span className="text-amber-400 font-medium">
                                {record.discrepancyCount} findings
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      {onLoadCachedAnalysis && (
                        <button
                          onClick={() => {
                            onLoadCachedAnalysis(record);
                            setIsDrawerOpen(false);
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
                        >
                          <span>Open Report</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDeleteCachedAudit(record.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-slate-900 rounded-lg transition"
                        title="Delete cached report"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="p-3 px-6 border-t border-slate-800 bg-slate-950/70 flex items-center justify-between text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>Zero cloud telemetry when offline</span>
              </div>
              <span>Total Cached: {cachedAudits.length}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Shield({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
