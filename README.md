# TriNetra

**Explainable Multilingual Criminal Intelligence Graph for Evidence-Backed Investigation**

TriNetra is an SIH-style full-stack prototype for authorized investigators. It uses entirely synthetic records and presents reviewable, evidence-linked analytical leads. It does not determine guilt, prove identity, or recommend arrest, punishment, or surveillance.

> **DEMO DATA — SYNTHETIC INVESTIGATION ENVIRONMENT.** Human verification is required before acting on any lead.

## Quick Start

### Local Development (Zero-Setup SQLite Mode)

Backend (FastAPI):
```bash
cd backend
.venv\Scripts\activate   # on Windows (or source .venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (Vite + React):
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) (development) or [http://localhost:8000](http://localhost:8000) (when frontend is built). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs) and health check is at [http://localhost:8000/api/health](http://localhost:8000/api/health).

### Deploy Backend to Railway and Frontend to Vercel

The repository includes [railway.toml](railway.toml), [frontend/vercel.json](frontend/vercel.json), and [frontend/.env.example](frontend/.env.example) for this deployment shape.

1. In Railway, create a new project from this GitHub repository. Railway will use [railway.toml](railway.toml) to install `backend/requirements.txt`, start FastAPI, and health-check `/api/health`.
2. Set Railway variables `JWT_SECRET` to a long random value, `DEMO_PASSWORD` to a non-default password, `DATABASE_MODE=sqlite`, `GRAPH_MODE=local`, and `CORS_ORIGINS=http://localhost:5173` while testing.
3. Copy the deployed Railway URL, for example `https://trinetra-production.up.railway.app`, and set the Vercel environment variable `VITE_API_URL` to `https://trinetra-production.up.railway.app/api`.
4. In Vercel, import this repository, set the root directory to `frontend`, keep build command `npm run build`, and set output directory to `dist`. Redeploy.
5. Replace Railway `CORS_ORIGINS` with the final Vercel URL, for example `https://trinetra.vercel.app`, then redeploy the backend.

The default Railway deployment uses SQLite and local uploads for a demo. Railway service storage should not be treated as durable application storage, so use PostgreSQL and persistent object storage before relying on this deployment for data that must survive restarts.

### Docker Runtime (Optional)

With Docker Desktop running:
```bash
docker compose up --build
```
Open [http://localhost:8080](http://localhost:8080).

---

## Demo Accounts

All accounts use `TriNetraDemo!2026` by default (configurable via `DEMO_PASSWORD` in `.env`):

| Role | Email | Capabilities |
|---|---|---|
| **ADMIN** | `admin@example.com` | Full system access, audit logs, user management, case archiving |
| **SUPERVISOR** | `supervisor@example.com` | Case creation, editing, entity match decisions, reports |
| **INVESTIGATOR** | `investigator@example.com` | Case creation, document upload, extraction, copilot |
| **ANALYST** | `analyst@example.com` | Analytics run, report generation, read access |
| **VIEWER** | `viewer@example.com` | Read-only inspection of assigned cases |

The UI includes one-click demo credential pills on the sign-in screen and a quick role switcher in the top bar to easily demonstrate role-based access control.

---

## Core Capabilities & Architecture

1. **Case Workspace & Evidence-First Inspector**:
   - Case summary with active priority and status badges.
   - Interactive Cytoscape network graph (blue=Person, purple=Phone, orange=Vehicle, green=BankAccount, cyan=Location, pink=Organization, red=CrimeEvent).
   - Relationship origin distinction: solid lines for **OBSERVED** facts, dashed amber lines for **INFERRED** leads.
   - Detail panel exposes source entity, target entity, relationship type, confidence, verification status, evidence type, source document reference, observed timestamp, frequency, amount, explanation, and caveats.

2. **Graph Explorer & Multi-Hop Path Finder**:
   - Filter by entity search query, entity type, and minimum confidence threshold.
   - Zoom in, zoom out, fit to screen controls.
   - Multi-Hop Path Finder: select source and target entities to trace connecting analytical relationship paths across the case scope.

3. **Entity Explorer**:
   - Comprehensive registry of entities with search and type filters.
   - Direct navigation from entity table into Case Workspace inspector.

4. **Human-in-the-Loop Entity Resolution (Identity Matches)**:
   - Evaluates potential duplicate records across the case (e.g. shared phone association, name token overlap).
   - Match categories: `CONFIRMED`, `PROBABLE`, `POSSIBLE`, `UNRESOLVED`.
   - Explicitly separates matching fields, conflicting fields, missing fields, and supporting evidence.
   - Actionable review: **Confirm**, **Reject**, **Mark Uncertain**, and **Undo** decisions are audited and reversible. Entities are never automatically merged.

5. **Chronological Investigation Timeline**:
   - Time-sequenced stream of synthetic calls, money transfers, location visits, vehicle usages, and FIR crime events.
   - Filter by event type and search query.

6. **Explainable Analytics & Investigation Priority Score**:
   - Real temporal activity bar chart aggregated from timestamped records.
   - Explainable composite **Investigation Priority Score** (0-100):
     - Network Position (30%)
     - Cross-Community Bridge Connections (25%)
     - Temporal Interaction Frequency (20%)
     - Evidence Quality (15%)
     - Data Completeness (10%)
   - Methodology breakdown and Responsible AI guardrails.

7. **Actionable Pattern Alerts & Data-Gap Finder**:
   - Alerts with severity, confidence, rationales, linked evidence references, limitations, and recommended verification actions.
   - Investigation data-gap finder highlighting missing subscriber verifications or unconfirmed identifiers.

8. **Grounded Investigator Copilot**:
   - Evidence-grounded deterministic analysis engine (no external paid LLM required).
   - Multi-hop traversal (e.g., 2-hop search from vehicles or phones).
   - Entity priority decomposition (explains why an individual lead is flagged).
   - Multilingual support (summarizes in Hindi / Hinglish).
   - Financial flow summaries and data-gap audits.
   - Every answer cites evidence sources, confidence, and explicit data limitations.

9. **Document Center & File Ingestion**:
   - Drag-and-drop file ingestion for TXT, CSV, JSON, PDF, DOCX, and images (<10 MB).
   - Safe sanitized filenames, MIME type verification, and SHA-256 idempotency.
   - Deterministic entity extraction trigger with extracted entity counts.
   - Extraction provenance inspector with source snippet, language, method, and green/amber/red confidence badge for every persisted entity.

10. **Printable Analytical Dossiers & Reports**:
    - Generates complete analytical intelligence dossier with case scope, priority entities table, pattern alerts, data gaps, evidence sample, document inventory with checksums, and investigator sign-off block.
    - Print-optimized CSS (`@media print`) allows instant "Print to PDF" from the browser.

11. **System Audit Trail**:
    - Admin-restricted audit log recording all user actions (logins, logouts, case accesses, match decisions, report downloads, file uploads, copilot queries).

---

## Security & Privacy Controls

- **Password Hashing**: Argon2id primary hash with PBKDF2 backward compatibility.
- **JWT Expiration**: 8-hour expiration tokens with HS256 signature verification.
- **Role-Based Access Control**: Strict endpoint decorators (`require("ADMIN", ...)`) and UI-level disabled states.
- **Case Isolation**: `CaseAccess` mapping prevents unauthorized investigators from viewing private cases.
- **File Validation**: MIME verification, extension whitelist, 10MB size limits, path normalization, and SHA-256 deduplication.
- **SQL & Query Safety**: All queries parameterized via SQLAlchemy ORM; no arbitrary SQL or Cypher from user inputs.

---

## Testing & Verification

Run backend test suite (14 tests covering auth, RBAC, isolation, graph, timeline, copilot, analytics, reports):
```bash
cd backend
.venv\Scripts\python -m pytest -v
```

Run end-to-end verification script:
```bash
cd backend
.venv\Scripts\python verify_runtime.py
```

Run frontend unit tests:
```bash
cd frontend
npm run test
```

Build production frontend:
```bash
cd frontend
npm run build
```

---

## Unstructured NLP Pipeline

The zero-setup extraction pipeline processes FIRs/police narratives, CDR CSVs, bank-transfer CSVs, surveillance notes, and social-media JSON. It uses deterministic regex and context rules (with optional OCR) rather than a hosted model.

- **Entities:** Person, Location, Phone, Vehicle, Date/Time, Amount, Organization, Bank Account, and FIR crime event.
- **Relationships:** ASSOCIATED_WITH, LOCATED_AT, MET, CALLED, TRANSFERRED_MONEY_TO, VISITED, FOLLOWS, and evidence-linked phone/vehicle associations.
- **Languages:** English, Hindi (Devanagari), and Hinglish. The detected document language and each extracted entity's language are retained.
- **Reviewability:** Each extracted entity retains confidence, method, source snippet and character offsets, and a verification flag. Entity resolution only proposes merge candidates—nothing is auto-merged.

Sample data is in [`seed/`](seed): `sample_fir.txt`, `sample_fir_hindi.txt`, `sample_cdr.csv`, `sample_transactions.csv`, `sample_surveillance.txt`, and `test_unseen_fir.txt`. The latter is a different Case Diary layout used to check basic generalization.

### OCR

Text, CSV, and JSON files work without additional dependencies. Image OCR is optional: install Tesseract plus its Hindi language data, then install `pytesseract` and Pillow in the backend environment. When unavailable, the service returns a clear review notice instead of failing ingestion. PDF text extraction is attempted when `pypdf` is installed; scanned PDFs also need OCR support.

### Known NLP Limits

The demo is intentionally deterministic and conservative. It does not resolve ambiguous names, infer identity from a phone number, or reliably extract every free-form address, nickname, or table layout. OCR quality depends on scan quality and installed Hindi assets. All outputs are investigative leads requiring human verification.

---

## Responsible AI Limitations

- A relationship does not establish criminal involvement.
- Similar names do not prove identity; the demo never automatically merges candidates.
- Confidence reflects source corroboration, not legal certainty.
- All records in this demo environment are synthetic.
- Authorized human review is required before acting on any lead.
