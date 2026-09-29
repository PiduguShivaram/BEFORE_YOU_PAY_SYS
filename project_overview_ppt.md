# Before You Pay — Project Overview (Verified)

## 1. Architectural Philosophy

Before You Pay is a phone-first AI decision-support platform designed to analyze financial documents (quotations, bills, contracts, subscriptions, warranties, invoices) before a user commits to payment.

### Non-Committal Guardrails
The system **never** makes unsupported legal or accusatory conclusions:
- **Prohibited:** `"This is a scam"`, `"This is fraud"`, `"This charge is illegal"`, `"You should definitely buy/not buy"`, `"Guaranteed savings"`, `"Good deal"`, `"Bad deal"`, `"Safe to buy"`, `"Unsafe to buy"`
- **Approved:** `"Potential issue"`, `"Potential overlap"`, `"Requires verification"`, `"Additional charge detected"`, `"Term requiring attention"`

The product informs the user with strict citations; **the user makes the final decision**.

---

## 2. Lean & Production-Ready Pipeline

```
                     UPLOAD (PDF / Image)
                              │
                              ▼
                      PRECONDITION CHECKER
               (Mime verification, integrity check)
                              │
                              ▼
                      SPATIAL OCR ENGINE
            (Normalized lines, bounding boxes: 0.0 - 1.0)
                              │
                              ▼
                STRUCTURED FINANCIAL EXTRACTION
             (Normalized fields with OCR line pointers)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       USER DOCUMENT RAG                 OKF CATALOG
 (Zero-dependency SQLite RAG)      (Curated JSON rules)
 (Strict multi-tenant isolation)   (Warranties, hidden fees)
               │                             │
               └──────────────┬──────────────┘
                              ▼
                   SEMANTIC REASONING ENGINE
                   (Evidence-grounded claims)
                              │
                              ▼
               DETERMINISTIC VALIDATION ENGINE
               (Pure Python arithmetic, totals)
                              │
                              ▼
                 DECISION-SUPPORT RESULT PAYLOAD
                  (Tap-to-source mobile cards)
```

---

## 3. Strict Architectural Boundaries

### A. Deterministic Code vs. Semantic Reasoning Authority
* **Semantic Engine:** OCR post-correction, fuzzy entity matching, clause categorization, comparison hypothesis generation, user-friendly synthesis.
* **Deterministic Code Domain:** Sole authority for arithmetic (`quantity * unit_price == total`), tax calculations, total consistency, date sequencing, and schema validation.
* **Invariant:** The LLM is **never** the authority for numerical correctness.

### B. User RAG vs. Curated OKF
* **User RAG:** Deterministic SQLite-based token-overlap document retrieval with tenant isolation. The current retrieval system is lexical/token-overlap based and does not use neural semantic/vector embeddings. Strictly scoped to user-provided documents (prior quotes, active contracts, past invoices) with strict multi-tenant isolation (`WHERE user_id = ?`).
* **OKF (Open Knowledge Format):** A versioned, curated knowledge catalog of non-user domain concepts, definitions, and verification rules stored in structured JSON (`data/okf/rules.json`). User documents **must never** be indexed in OKF.

### C. Data Provenance Chain
Every finding displayed on the mobile app traces directly to raw physical evidence:
$$\text{document\_id} \longrightarrow \text{page\_id} \longrightarrow \text{ocr\_line\_id} \longrightarrow \text{field\_id} \longrightarrow \text{financial\_component\_id} \longrightarrow \text{semantic\_component\_id} \longrightarrow \text{validation\_id} \longrightarrow \text{finding\_id} \longrightarrow \text{opportunity\_id} \longrightarrow \text{question\_id}$$

---

## 4. Key Architectural Improvements & De-Bloating

1. **Curated Lean Dependencies**:
   - Zero-dependency SQLite RAG service replacing external vector stores.
   - Standard library `json` for rule definitions.
   - Current verified production dependencies: 8 packages (`fastapi`, `groq`, `pillow`, `pydantic`, `pydantic-settings`, `pypdf`, `python-multipart`, `uvicorn`).
   - **Audit Finding:** Dependency reduction percentage could not be independently verified from the current repository. The original baseline is not available in local commit history.

2. **Single High-Performance Upload Pipeline**:
   - Collapsed 7 micro-endpoints into a single, mobile-optimized endpoint: `POST /api/v1/analyze`.
   - Eliminates high-latency mobile round-trips over cellular networks.

3. **Streamlined Domain Models**:
   - Consolidated 9 fragmented model files into 2 clean domain modules: `models/document.py` (spatial structures) and `models/analysis.py` (decision support).

4. **Concrete Idiomatic Services**:
   - Replaced single-implementation abstract base classes (ABCs) with clean, testable service classes injected via FastAPI dependencies.

---

## 5. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness & readiness probes |
| `POST` | `/api/v1/analyze` | Single-shot multi-part scan analysis (runs full 7-stage pipeline) |
| `POST` | `/api/v1/documents` | Index historical user contracts, warranties, or past quotes |

---

## 6. Full-Stack Development & Verification

The project is structured into two clean layers:
1. **Backend (FastAPI)**: Running on `http://127.0.0.1:8000`
2. **Frontend (Next.js 14 App Router)**: Running on `http://localhost:3000`

### Backend Setup & Tests
```bash
# Sync Python dependencies
uv sync

# Run backend unit & integration tests (655 tests across 30 test files)
uv run pytest

# Run linter and formatter
uv run ruff check .
uv run ruff format --check .

# Start FastAPI server
uv run uvicorn before_you_pay.main:app --host 127.0.0.1 --port 8000
```

### Frontend Setup & Dev Server (Next.js)
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies with pnpm
pnpm install

# Start Next.js development server
pnpm dev
```
Open **`http://localhost:3000`** in your browser to view the interactive Next.js application. All `/api` and `/health` requests are seamlessly proxied to the FastAPI backend.

---

## 7. Verified Claims Summary

| Claim | Status | Evidence |
| :--- | :--- | :--- |
| 655 tests | **VERIFIED** | `pytest` output: 655 passed, 1 warning (deprecation warning about httpx with starlette TestClient) |
| 30 test files | **VERIFIED** | Exactly 30 test files (`test_*.py`) in `tests/` directory |
| SQLite RAG | **VERIFIED** | Deterministic SQLite-based token-overlap document retrieval with tenant isolation. The current retrieval system is lexical/token-overlap based and does not use neural semantic/vector embeddings. (`SqliteRagService` in `services/rag.py`). |
| Non-committal by design | **VERIFIED** | Pydantic model validators in `models/analysis.py`, `models/decision_summary.py`, `models/evidence.py` |
| Prohibited phrases enforced at model-validator level | **VERIFIED** | Runtime validators raise `ValueError` on prohibited recommendation language ("buy this", "guaranteed savings", "scam", "fraud", "safe to buy", etc.) across `ReasoningClaim`, `DecisionFlag`, `ResultSummary`, `SmartCostReductionQuestion`, `EvidenceItem`, `FindingExplanation`, `BeforeYouPayFinalDecisionSummary` |
| LLM interprets. Python verifies. | **VERIFIED** | Clear separation in `pipeline.py` and `validation.py`; deterministic validation engine is sole authority for arithmetic and totals |
| Phone-first | **PARTIALLY VERIFIED** | Responsive mobile UI, touch targets, mobile document viewer, low-roundtrip API; no on-device NPU/offline execution |
| One upload, full analysis | **PARTIALLY VERIFIED** | Primary document is single-upload; optional second upload for supporting document comparison |
| No multi-step round trips | **VERIFIED** | Single `POST /api/v1/analyze` multipart endpoint |
| 62% dependency reduction | **NOT VERIFIED** | Dependency reduction percentage could not be independently verified from the current repository. The original baseline is not available in local commit history. |

---

## 8. Phase 7 — Evidence-First Explainability

Phase 7 adds comprehensive evidence traceability to every finding:

### Evidence Chain
```
DOCUMENT → OCR EVIDENCE → EXTRACTED FIELD → FINANCIAL COMPONENT → SEMANTIC INTERPRETATION → DETERMINISTIC VALIDATION → FINDING → EXPLANATION → QUESTION → ACTION
```

### Evidence Types
- `DOCUMENT_TEXT` — Raw text from the uploaded document
- `OCR_TEXT` — Text recognized by OCR engine
- `EXTRACTED_VALUE` — Normalized financial value
- `SEMANTIC_CLASSIFICATION` — AI/LLM interpretation
- `DETERMINISTIC_CALCULATION` — Python arithmetic
- `SUPPORTING_DOCUMENT` — Evidence from supporting documents
- `CROSS_DOCUMENT_COMPARISON` — Comparison results
- `AUTHORITATIVE_KNOWLEDGE` — OKF rules and curated knowledge

### Fact vs Interpretation
Every explanation distinguishes:
- **FACT** — What the document literally states
- **INTERPRETATION** — What the system inferred
- **CALCULATION** — Deterministic arithmetic
- **UNCERTAINTY** — What remains unknown
- **ACTION** — What the user can do

### Amount States
Preserved states: `PRESENT`, `MISSING`, `UNKNOWN`, `UNREADABLE`, `ZERO`, `NOT_APPLICABLE`

**Invariant:** `MISSING` → `₹0`, `UNKNOWN` → `₹0`, `UNREADABLE` → `₹0` is **never** performed.

---

## 9. Security & Isolation

### Tenant Isolation
- All RAG queries scoped to `user_id` via SQL `WHERE` clause
- Evidence retrieval never crosses user boundaries

### Prompt Injection Protection
- Document text is treated as **DATA**, not system instructions
- Existing prompt-injection protections preserved

### Non-Committal Language
- Model validators enforce neutral language at runtime
- Frontend displays only approved terminology
