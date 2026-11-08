import { DocumentClassification, FinalDecisionSupportResult } from "./types";

const isDev = process.env.NODE_ENV === "development";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  (isDev ? "http://127.0.0.1:8000" : "");

let cachedAuthToken: string | null = null;
let currentTokenUserId: string | null = null;

export async function getAuthToken(userId?: string): Promise<string> {
  if (cachedAuthToken && (!userId || currentTokenUserId === userId)) {
    return cachedAuthToken;
  }
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (cachedAuthToken) {
      headers["Authorization"] = `Bearer ${cachedAuthToken}`;
    }
    // Security Rule: Never claim a user_id without presenting authenticating credentials
    const payload = cachedAuthToken && userId ? { user_id: userId } : {};
    const res = await fetch(`${API_BASE}/api/v1/auth/session`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      cachedAuthToken = data.access_token;
      currentTokenUserId = data.user_id;
      return data.access_token;
    }
  } catch (e) {
    console.warn("Could not retrieve session token from auth service:", e);
  }
  return "";
}

export function clearAuthToken(): void {
  cachedAuthToken = null;
  currentTokenUserId = null;
}

export async function getCurrentUserProfile(token?: string): Promise<{ user_id: string; authenticated: boolean } | null> {
  const activeToken = token || (await getAuthToken());
  if (!activeToken) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${activeToken}`,
      },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("Failed to fetch verified user profile:", err);
  }
  return null;
}

export async function createFreshSession(): Promise<{ user_id: string; access_token: string }> {
  clearAuthToken();
  const res = await fetch(`${API_BASE}/api/v1/auth/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    throw new Error("Failed to create fresh authenticated session");
  }
  const data = await res.json();
  cachedAuthToken = data.access_token;
  currentTokenUserId = data.user_id;
  return { user_id: data.user_id, access_token: data.access_token };
}

export async function analyzeDocument(
  file: File,
  userId: string,
  docType: DocumentClassification = "other",
  supportingFile?: File | null,
  signal?: AbortSignal
): Promise<FinalDecisionSupportResult> {
  const token = await getAuthToken(userId);
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  formData.append("document_classification", docType);
  if (supportingFile) {
    formData.append("supporting_file", supportingFile);
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) {
    let errorDetail = "Failed to analyze document";
    try {
      const err = await res.json();
      errorDetail = err.message || errorDetail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export interface StreamEvent {
  stage: string;
  status: string;
  message: string;
  progress: number;
  data?: any;
  result?: FinalDecisionSupportResult;
}

export async function analyzeDocumentStream(
  file: File,
  userId: string,
  docType: DocumentClassification = "other",
  onEvent?: (event: StreamEvent) => void,
  supportingFile?: File | null,
  signal?: AbortSignal
): Promise<FinalDecisionSupportResult> {
  const token = await getAuthToken(userId);
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  formData.append("document_classification", docType);
  if (supportingFile) {
    formData.append("supporting_file", supportingFile);
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/analyze/stream`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) {
    let errorDetail = "Failed to analyze document";
    try {
      const err = await res.json();
      errorDetail = err.message || errorDetail;
    } catch {}
    throw new Error(errorDetail);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("Readable stream is not supported in this browser.");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: FinalDecisionSupportResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const chunk of lines) {
      const trimmed = chunk.trim();
      if (trimmed.startsWith("data: ")) {
        let event: StreamEvent;
        try {
          event = JSON.parse(trimmed.slice(6));
        } catch (e) {
          console.error("Failed to parse SSE payload", e);
          continue;
        }

        if (onEvent) onEvent(event);
        if (event.stage === "error") {
          throw new Error((event as any).error || event.message || "Document analysis failed");
        }
        if (event.stage === "complete" && event.result) {
          finalResult = event.result;
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error("Stream completed without a final verdict.");
  }

  return finalResult;
}

export async function storeUserDocument(
  userId: string,
  documentId: string,
  docType: DocumentClassification,
  textContent: string,
  pageNumber: number = 1
): Promise<{ status: string; chunks_indexed: number; user_id: string }> {
  const token = await getAuthToken(userId);
  const payload = {
    user_id: userId,
    document_id: documentId,
    document_type: docType,
    page_number: pageNumber,
    text_content: textContent,
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/documents`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let errorDetail = "Failed to index document in RAG store";
    try {
      const err = await res.json();
      errorDetail = err.message || errorDetail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export async function listUserDocuments(
  userId: string
): Promise<Array<{ document_id: string; document_type: string; chunk_count: number; max_page: number }>> {
  const token = await getAuthToken(userId);
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/documents`, {
    method: "GET",
    headers,
  });

  if (!res.ok) {
    throw new Error("Failed to list historical documents");
  }
  return res.json();
}

export async function deleteUserDocument(
  userId: string,
  documentId: string
): Promise<{ status: string; document_id: string; deleted_chunks: number }> {
  const token = await getAuthToken(userId);
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/documents/${documentId}`, {
    method: "DELETE",
    headers,
  });

  if (!res.ok) {
    throw new Error("Failed to delete document");
  }
  return res.json();
}

export async function checkBackendHealth(): Promise<{ status: string; app_name: string; version: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) {
    throw new Error("Backend server is unreachable");
  }
  return res.json();
}

export async function compareQuotes(
  files: File[],
  userId: string,
  signal?: AbortSignal
): Promise<import("./types").MultiQuoteComparisonResult> {
  const token = await getAuthToken(userId);
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }
  formData.append("user_id", userId);

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/compare-quotes`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) {
    let errorDetail = "Failed to compare quotations";
    try {
      const err = await res.json();
      errorDetail = err.message || err.detail || errorDetail;
    } catch {}
    throw new Error(errorDetail);
  }

  return res.json();
}

export async function parseDealerResponse(
  dealerText: string,
  userId: string,
  originalTotal?: number | null,
  currency: string = "INR",
  quoteFile?: File | null,
  signal?: AbortSignal
): Promise<import("./types").DealerResponseAnalysisResult> {
  const token = await getAuthToken(userId);
  const formData = new FormData();
  formData.append("dealer_text", dealerText);
  formData.append("user_id", userId);
  if (originalTotal != null) {
    formData.append("original_total", String(originalTotal));
  }
  formData.append("currency", currency);
  if (quoteFile) {
    formData.append("quote_file", quoteFile);
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/v1/parse-dealer-response`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) {
    let errorDetail = "Failed to parse dealer response";
    try {
      const err = await res.json();
      errorDetail = err.message || err.detail || errorDetail;
    } catch {}
    throw new Error(errorDetail);
  }

  return res.json();
}
