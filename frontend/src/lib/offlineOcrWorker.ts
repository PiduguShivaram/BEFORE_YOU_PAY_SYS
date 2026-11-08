/**
 * On-Demand Client-Side Web Worker for Offline OCR and Analysis.
 * 
 * Uses dynamic import of tesseract.js to avoid bundle bloat.
 * Runs in background thread to prevent UI freezing during OCR.
 */

import { analyzeOfflineText, OfflineAnalysisResult } from "./offlineAnalysisEngine";

export type OcrProgressCallback = (progress: number, statusText: string) => void;

export async function runOnDeviceOfflineAnalysis(
  imageSource: Blob | File | string,
  onProgress?: OcrProgressCallback
): Promise<OfflineAnalysisResult> {
  onProgress?.(10, "Initializing on-device OCR engine...");

  try {
    // Dynamic import ensures zero bundle impact until explicitly invoked
    const { createWorker } = await import("tesseract.js");

    onProgress?.(25, "Loading local OCR WebWorker and WASM assets...");
    const isBrowser = typeof window !== "undefined";
    const worker = await createWorker("eng", 1, {
      workerPath: isBrowser ? "/tesseract/worker.min.js" : undefined,
      corePath: isBrowser ? "/tesseract/tesseract-core-simd-lstm.wasm.js" : undefined,
      logger: (m) => {
        if (m.status === "recognizing text" && typeof m.progress === "number") {
          const pct = Math.round(25 + m.progress * 65);
          onProgress?.(pct, `Extracting text on-device (${Math.round(m.progress * 100)}%)...`);
        }
      },
    });

    onProgress?.(60, "Scanning image geometry & characters...");
    const ret = await worker.recognize(imageSource);
    const extractedText = ret.data.text || "";

    onProgress?.(92, "Running local deterministic financial verification...");
    await worker.terminate();

    const analysis = analyzeOfflineText(extractedText);
    onProgress?.(100, "On-device analysis complete.");

    return analysis;
  } catch (error: any) {
    console.error("On-device OCR error:", error);
    return {
      id: `err-${Date.now()}`,
      timestamp: new Date().toISOString(),
      status: "ANALYSIS_UNAVAILABLE",
      status_label: "Analysis unavailable",
      ocr_text: "",
      detected_total: null,
      detected_subtotal: null,
      detected_tax: null,
      detected_discount: null,
      components: [],
      math_status: "INCONCLUSIVE",
      discrepancy: null,
      currency: "INR",
      summary: `On-device analysis unavailable: ${error?.message || "Local OCR engine initialization failed"}.`,
      is_on_device: true,
    };
  }
}

