# Before You Pay

A phone-first AI decision-support platform designed to analyze financial documents (quotations, bills, contracts, subscriptions, warranties, invoices) before a user commits to payment.

---

## 1. Architectural Philosophy

Before You Pay acts as an objective, evidence-backed decision-support system. It protects users from hidden charges, unexpected renewals, and contract discrepancies with strict data provenance.

### Non-Committal Guardrails
The system **never** makes unsupported legal or accusatory conclusions:
- **Prohibited:** `"This is a scam"`, `"This is fraud"`, `"This charge is illegal"`, `"You should definitely buy/not buy"`
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
$$\text{document\_id} \longrightarrow \text{page\_id} \longrightarrow \text{ocr\_line\_id} \longrightarrow \text{field\_id} \longrightarrow \text{claim\_id} \longrightarrow \text{validation\_id}$$

---

## 4. Key Architectural Improvements & De-Bloating

1. **Purged Bloatware Dependencies**:
   - Replaced ChromaDB (which required 57 heavy transitive packages including `kubernetes`, `onnxruntime`, `grpcio`) with a clean, zero-dependency SQLite RAG service.
   - Replaced PyYAML with Python standard library `json`.
   - Total environment dependencies reduced by **~62%**.
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
n
### Backend Setup & Tests
```bash
# Sync Python dependencies
uv sync

# Run backend unit & integration tests (36 tests)
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
