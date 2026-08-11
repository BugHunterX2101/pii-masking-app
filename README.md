---
title: Enterprise Privacy Suite
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Enterprise Privacy Suite
**Intelligent Data Loss Prevention (DLP) and PII Redaction Engine**

*Protect sensitive customer data before it reaches your database, support agents, or AI models.*

<br/>

[![React](https://img.shields.io/badge/Frontend-React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Workers-Celery-37814A?style=for-the-badge)](https://docs.celeryq.dev/)
[![Auth0](https://img.shields.io/badge/Auth-Auth0_SSO-eb5424?style=for-the-badge&logo=auth0)](https://auth0.com/)
[![AWS S3](https://img.shields.io/badge/Storage-AWS_S3-ff9900?style=for-the-badge&logo=amazonaws)](https://aws.amazon.com/s3/)
[![RapidOCR](https://img.shields.io/badge/OCR-RapidOCR-5B21B6?style=for-the-badge)](https://github.com/RapidAI/RapidOCR)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)
[![Hugging Face](https://img.shields.io/badge/Hosted_on-Hugging_Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/vedit2101/pii-masking-app)

<br/>

> **Every document your company handles is a potential data breach waiting to happen.**
> The Enterprise Privacy Suite is an automated, cloud-native DLP pipeline that detects and permanently redacts sensitive PII from documents — *before* they ever reach your database, your support agents, or your AI models.

<br/>

**[Live Demo on Hugging Face](https://huggingface.co/spaces/vedit2101/pii-masking-app)** &nbsp;|&nbsp; **[Report a Bug](https://github.com/BugHunterX2101/pii-masking-app/issues)** &nbsp;|&nbsp; **[Request a Feature](https://github.com/BugHunterX2101/pii-masking-app/issues)**

---

## Table of Contents
1. [The Problem We Solve](#the-problem-we-solve)
2. [Key Capabilities](#key-capabilities)
3. [Full System Architecture](#full-system-architecture)
4. [PII Processing Deep Dive](#pii-processing-deep-dive)
5. [Authentication and RBAC Flow](#authentication-and-rbac-flow)
6. [Database Schema](#database-schema)
7. [Technology Stack](#technology-stack)
8. [Supported PII Entity Types](#supported-pii-entity-types)
9. [Local Development Setup](#local-development-setup)
10. [Deployment on Hugging Face](#deployment-on-hugging-face)
11. [API Reference](#api-reference)
12. [Compliance Coverage](#compliance-coverage)
13. [Project Structure](#project-structure)

---

## The Problem We Solve

Every day, organizations deal with a ticking compliance time bomb: **unstructured documents** containing raw PII. Whether it is a customer uploading their Aadhaar card for KYC, an HR team storing resumes with home addresses, or engineers feeding production SQL dumps into an AI model — **sensitive data is everywhere, and most of it is completely unprotected**.

| Without This Tool | With Enterprise Privacy Suite |
|---|---|
| Raw Aadhaar/PAN numbers stored in S3 | Only `[AADHAAR_MASKED]` tokens are persisted |
| Support agents seeing real credit card numbers | Documents are sanitized before human review |
| LLM training data containing customer emails | Clean, anonymized datasets for safe AI ingestion |
| No audit trail for compliance auditors | Immutable PostgreSQL logs of every masked operation |
| One authentication system to breach = full data access | Auth0 SSO + RBAC: zero-trust identity model |

---

## Key Capabilities

### AI-Powered Dual Detection Engine
Unlike rule-based tools that only catch "known patterns," this system uses a **two-layer detection pipeline**:
1. **RapidOCR (local ONNX)** — Extracts every character from scanned images, IDs, and screenshots with state-of-the-art accuracy via a bundled ONNX model — fully local, no cloud API, no credentials, no per-image network round-trip.
2. **Microsoft Presidio (NLP)** — Runs named-entity recognition (NER) on the extracted text using a lazy-loaded SpaCy model to catch contextual PII (like names in a sentence) that regex alone would miss.

### Multi-Language Support
The detection engine supports **24 languages**. Each language uses a small spaCy `_sm` model (~10-15 MB) loaded **lazily on first use per language** by a custom `LazySpacyNlpEngine` — so cold start is near-instant and memory only grows for languages actually requested:

| Region | Languages |
|---|---|
| Western Europe | English, Spanish, French, German, Italian, Portuguese, Dutch, Catalan |
| Nordic | Danish, Norwegian Bokmål, Swedish, Finnish |
| Eastern Europe | Polish, Russian, Ukrainian, Czech→*, Slovak→*, Bulgarian→*, Croatian, Slovenian, Macedonian, Lithuanian, Latvian→*, Estonian→*, Hungarian→*, Romanian |
| Asia | Japanese, Chinese, Korean |

> *Languages marked → are detected by `langdetect` but have no dedicated spaCy 3.7 model, so their text is analyzed with the English NER model (the pipeline never errors on an unsupported code — it clamps to English). Regex-backed PII detection (email, phone, Aadhaar, PAN, cards, ...) works in every language regardless, because the regional recognizers are pure regex registered for all 24 languages.*

This replaces the previous setup of eight ~500 MB `_lg` models loaded eagerly at startup (≈4 GB of downloads and RAM before the first request) with a ~90% smaller footprint, instant startup, and triple the language coverage. Languages are auto-detected with `langdetect` when not specified.

### Event-Driven Asynchronous Architecture
Large files (multi-page PDFs, high-res images) can take several seconds to process. In a synchronous system, this would cause HTTP timeouts, thread starvation, and a terrible user experience. This suite uses a **full event-driven pipeline**:
- The FastAPI server **immediately** responds with `HTTP 202 Accepted` + a `task_id`.
- The Celery worker processes the document entirely in the background.
- The React frontend **polls** `/api/tasks/{task_id}` every 2 seconds, rendering a live progress state.
- On completion, the UI delivers the masked file to the user via a **secure S3 pre-signed URL** (expires in 1 hour).

### Exact-Redaction Document Masking
Redaction is **span-exact**: only the precise words Presidio flagged are removed — never the whole line, and never unrelated occurrences. Each file type uses a purpose-built strategy so the output is safe and looks professional:

| File type | Strategy | What it guarantees |
|---|---|---|
| **PDF** (native text) | Word-level redaction from the page's extracted word boxes | PII split across lines is fully blacked out; a flagged word never damages words that merely *contain* it (flagging `John` leaves `Johnston` untouched) |
| **DOCX** | Run-level replacement | Formatting (bold, italic, fonts) survives; headers and footers are scanned (they never were before); tables are covered |
| **Images / scans** | Local OCR + per-word box redaction | Runs fully offline (no cloud API, no credentials); only OCR boxes intersecting a flagged span are blacked out — an email's `com` never blacks out a legitimate `example.com` elsewhere in the image |
| **CSV / JSONL** | Row-by-row synthesis | Training data is sanitized with realistic Faker substitutes per language |

Every handler reports what it actually redacted — if a detection ever maps to no box, it is reported as missed rather than silently claimed as masked. One language detection per document (not per paragraph) keeps large-file latency low.

### Zero-Trust Security Model
- **Auth0 SSO**: Users authenticate via corporate identity providers (Microsoft Entra ID, Google Workspace, Okta). No passwords are stored in the application database.
- **JWT Validation (RS256)**: Every API call validates the Auth0 JWT against the JWKS endpoint with **issuer verification** (tokens minted by other tenants are rejected) and a **time-based JWKS cache** so key rotations are picked up automatically. Unauthenticated requests receive `HTTP 401`.
- **Verified-Email-Provider Gate**: `POST /api/auth/sync` rejects any email that is not verified by Auth0, is on the disposable/temporary-mail blocklist (Mailinator, 10MinuteMail, GuerrillaMail, Yopmail, ...), or belongs to a domain with no real MX record. Both lists are environment-configurable.
- **Per-IP Rate Limiting**: The auth sync endpoint is throttled per client IP (20 req/min) in addition to the per-key limit on the programmatic API.
- **Ephemeral Storage**: Raw (unmasked) files are temporarily staged in a private S3 prefix and are never returned to the client. Only the masked output is accessible via a time-limited pre-signed URL.
- **Per-Key Rate Limiting**: Programmatic API keys carry a per-minute limit (default 1000 req/min) enforced with Redis fixed-window counters — exceeding it returns `HTTP 429`.

### Admin Dashboard and Live Policy Engine
- **RBAC**: Roles are assigned on every login based on the `ADMIN_EMAILS` environment variable whitelist. Users whose email matches the whitelist receive the `admin` role; all others receive the `user` role. This is enforced server-side on every login — the database is never the source of truth.
- **DLP Policy Toggles**: Admins can enable/disable specific PII entity types (e.g., turn off `PERSON` detection for a specific data processing workflow) in real-time from the UI.
- **Custom Regex Policies**: Admins can define and deploy custom regex patterns from the dashboard without redeploying the application.
- **Immutable Audit Log**: Every masking operation is logged to PostgreSQL: Auth0 User ID, IP address, filename, timestamp, and detected entity types. Exportable as CSV.

### Live PII Heatmap
The text input tab features a real-time inline detection overlay that highlights PII in the textarea as you type, color-coded by severity:
- Red — Critical (Aadhaar, SSN, credit cards)
- Amber — High (email addresses, phone numbers)
- Blue — Medium (IP addresses)
- Green — Low (dates)

---

## Full System Architecture

The system is built on a distributed, event-driven architecture with complete separation between the API layer and the processing layer.

```mermaid
flowchart TD
subgraph CLIENT [" Client Layer"]
Browser["React SPA\nDark Mode UI"]
end

subgraph AUTH [" Identity Layer"]
Auth0["Auth0 SSO\nRS256 JWT Provider"]
end

subgraph API [" API Layer (FastAPI)"]
Uvicorn["Uvicorn ASGI Server\nPort 7860"]
CORS["CORS Middleware"]
AuthMiddleware["JWT Validation\nMiddleware"]
Endpoints["REST Endpoints\n/upload /mask-text /tasks"]
end

subgraph ASYNC [" Async Processing Layer"]
Redis["Redis 8\nMessage Broker\n+ Result Backend"]
Worker["Celery Worker\nBackground Workers"]
end

subgraph AI [" AI / ML Layer"]
RapidOCR["RapidOCR (local ONNX)\nOCR Engine"]
Presidio["Microsoft Presidio\nNER Engine"]
Spacy["SpaCy (24 lazy-loaded sm models)\nNLP Models"]
end

subgraph STORAGE [" Cloud Storage"]
S3["AWS S3\npii-mask-ocr-files"]
RawPrefix["s3://...raw_*\nTemporary Raw Files"]
MaskedPrefix["s3://...masked_*\nRedacted Output Files"]
end

subgraph DB [" Persistence Layer"]
Postgres["PostgreSQL (NeonDB)\nUsers, Audit Logs, Policies"]
end

Browser -- "1. Login Redirect" --> Auth0
Auth0 -- "2. RS256 JWT Token" --> Browser
Browser -- "3. POST /upload + Bearer JWT" --> Uvicorn
Uvicorn --> CORS --> AuthMiddleware
AuthMiddleware -- "4. Verify JWT @ JWKS URI" --> Auth0
AuthMiddleware -- "5. Lookup User" --> Postgres
Uvicorn --> Endpoints
Endpoints -- "6. Stage Raw File" --> RawPrefix
Endpoints -- "7. Enqueue Task" --> Redis
Endpoints -- "8. HTTP 202 + task_id" --> Browser
Redis -- "9. Dequeue Task" --> Worker
Worker -- "10. Fetch Raw File" --> RawPrefix
Worker -- "11. Local OCR" --> RapidOCR
RapidOCR -- "12. Text Annotations" --> Worker
Worker -- "13. NER Detection" --> Presidio
Presidio --> Spacy
Spacy -- "14. Detected Entities" --> Worker
Worker -- "15. Upload Masked File" --> MaskedPrefix
Worker -- "16. Task SUCCESS + URL" --> Redis
Browser -- "17. Poll GET /tasks/:id" --> Uvicorn
Uvicorn -- "18. Fetch Result" --> Redis
Uvicorn -- "19. Return Pre-signed URL" --> Browser
Endpoints -- "Log Audit Event" --> Postgres
```

---

## PII Processing Deep Dive

The document goes through a specific pipeline based on its file type:

```mermaid
flowchart TD
Start([" File Received by Celery Worker"]) --> TypeCheck{{"File Extension?"}}

TypeCheck -->|".pdf"| PDF["PyMuPDF\nWord-level text extraction"]
TypeCheck -->|".docx"| DOCX["python-docx\nExtract paragraph runs"]
TypeCheck -->|".jpg/.png/.webp"| IMG["Raw Image Bytes"]
TypeCheck -->|".csv/.jsonl"| DS["Dataset Parser\nRow-by-row processing"]

PDF --> Direct["Word-level text extraction\n(no OCR needed — native text)"]
IMG --> OCR[" RapidOCR (local ONNX)\nfull image OCR"]
DOCX --> Runs["python-docx\nRun-level extraction"]
DS --> Direct

OCR --> TextBlocks["Text Annotations\n+ Bounding Boxes"]
Direct --> Presidio
Runs --> Presidio
TextBlocks --> Presidio

Presidio --> Entities{{"PII Found?"}}

Entities -->|"Yes"| Redact["Apply Redaction\nBlack Box / Token Replace / Asterisk"]
Entities -->|"No"| PassThrough["Pass-through unchanged"]

Redact --> Report[" Build Detection Report\n{text, pii_types, location}"]
PassThrough --> Report

Report --> S3Upload[" Upload Masked Output to S3"]
S3Upload --> PreSignedURL[" Generate 1-Hour Pre-signed URL"]
PreSignedURL --> ResultBackend[" Publish SUCCESS to Redis\n{download_url, report}"]
```

---

## Authentication and RBAC Flow

```mermaid
sequenceDiagram
actor User as User (Browser)
participant Auth0 as Auth0
participant FastAPI as  FastAPI
participant DB as  PostgreSQL

User->>Auth0: Clicks "Login with Auth0"
Auth0-->>User: Redirects to Universal Login Page
User->>Auth0: Enters corporate credentials (SSO)
Auth0-->>User: RS256 Signed JWT (ID Token)

User->>FastAPI: POST /api/auth/sync (Bearer JWT)
FastAPI->>Auth0: Fetches JWKS public keys
Auth0-->>FastAPI: JWK Set (RS256 Public Key)
FastAPI->>FastAPI: Validates JWT signature and expiry

FastAPI->>FastAPI: Check email against ADMIN_EMAILS env var
Note over FastAPI: admin if email is whitelisted, user otherwise

alt New user
FastAPI->>DB: INSERT user with assigned role
DB-->>FastAPI: New user record
else Returning user
FastAPI->>DB: UPDATE user.role (re-sync on every login)
DB-->>FastAPI: Updated user record
end

FastAPI-->>User: { status: "synced", role: "admin|user" }

Note over User,FastAPI: All subsequent API calls carry Bearer JWT
Note over FastAPI,DB: Admin-only endpoints enforce role via require_admin() dependency
```

### Role Enforcement

| Role | Assigned When | Access |
|---|---|---|
| `admin` | Email is in the `ADMIN_EMAILS` env var | All tabs including Admin Dashboard, all `/api/admin/*` endpoints |
| `user` | Any other authenticated user | Document masking, text scanner, cloud scan tabs only |

The role is **re-evaluated on every login** from the environment variable — changing `ADMIN_EMAILS` takes effect on the user's next login without any database migration.

---

## Database Schema

```mermaid
erDiagram
ORGANIZATIONS {
    int id PK
    string name
    string slug
    string plan "free or enterprise"
    datetime created_at
}

USERS {
    int id PK
    string username "Auth0 sub claim"
    string hashed_password "SSO for Auth0 users"
    string role "admin or user"
    bool is_active
    int org_id FK
}

AUDIT_LOGS {
    int id PK
    int user_id FK
    int org_id FK
    string api_key_id FK
    string action "LOGIN, FILE_MASK_TASK_STARTED, TEXT_MASK, CLOUD_SCAN_STARTED"
    string ip_address
    json details "filename, task_id, detected_entities"
    datetime timestamp
}

DLP_POLICIES {
    int id PK
    int org_id FK
    string pii_type "PERSON, EMAIL_ADDRESS, CREDIT_CARD, etc."
    bool is_active
}

CUSTOM_REGEX_POLICIES {
    int id PK
    int org_id FK
    string name
    string pattern
    bool is_active
}

SYSTEM_SETTINGS {
    int id PK
    int org_id FK
    string masking_style "LABEL, BLACKOUT, or ASTERISK"
}

API_KEYS {
    string id PK
    int org_id FK
    string name
    string key_hash
    int rate_limit
    bool is_active
    datetime created_at
}

ORGANIZATIONS ||--o{ USERS : "has"
ORGANIZATIONS ||--o{ AUDIT_LOGS : "generates"
ORGANIZATIONS ||--o{ DLP_POLICIES : "owns"
ORGANIZATIONS ||--o{ CUSTOM_REGEX_POLICIES : "owns"
ORGANIZATIONS ||--o{ SYSTEM_SETTINGS : "configures"
ORGANIZATIONS ||--o{ API_KEYS : "issues"
USERS ||--o{ AUDIT_LOGS : "generates"
```

---

## Technology Stack

| Layer | Technology | Version | Why This Choice |
|-------|------------|---------|-----------------|
| **Frontend** | React | 18 | Component-driven SPA, Auth0 SDK |
| **UI** | Lucide React + Vanilla CSS | Latest | Zero dependency, glassmorphism dark mode |
| **Fonts** | Plus Jakarta Sans | Latest | Premium typographic hierarchy |
| **Backend** | FastAPI | 0.110+ | Async-native Python, OpenAPI auto-docs |
| **ASGI Server** | Uvicorn | Latest | Production-grade ASGI with hot-reload |
| **Auth** | Auth0 (RS256 JWT) | — | Enterprise SSO; no password management |
| **ORM** | SQLAlchemy | 2.0 | Type-safe DB sessions |
| **Database** | PostgreSQL (NeonDB) | 16 | Serverless Postgres; scales to zero (SQLite fallback for no-config boot) |
| **Task Queue** | Celery | 5.3.6 | Distributed async workers; Redis backend |
| **Broker** | Redis | 8 | In-memory pub/sub; sub-millisecond latency |
| **Storage** | AWS S3 + Boto3 | Latest | Durable object storage; pre-signed URL support |
| **OCR** | RapidOCR (ONNX) | 1.3 | Local OCR — offline, no credentials, no per-image network latency |
| **NLP / NER** | Microsoft Presidio + SpaCy | 2.2 / 3.7 | Context-aware PII detection beyond regex |
| **PDF** | PyMuPDF (fitz) | 1.24 | Word-exact text extraction + redaction |
| **Word** | python-docx | 1.1 | Run-level redaction that preserves formatting |
| **Image** | RapidOCR + OpenCV | 1.3 / 4.x | Local OCR + span-exact box redaction |
| **Container** | Docker + Supervisord | Latest | Multi-process single-container orchestration |
| **CI/CD** | GitHub Actions | — | Automated deploy to Hugging Face on every push to `main` |

---

## Supported PII Entity Types

Detection combines Presidio's built-in recognizers with **16 custom regional entity classes** shipped with the app (all active by default, all toggleable from the admin dashboard):

| Category | Entities Detected |
|---|---|
| **Indian Identity** | `AADHAAR`, `PAN_CARD`, `VEHICLE_REG` (custom recognizers) |
| **European Identity** | `EU_IBAN`, `EU_VAT` (custom recognizers) |
| **US Identity** | `US_SSN` (built-in), `US_ROUTING_NUMBER` (custom) |
| **Brazilian Identity** | `BR_CPF`, `BR_CNPJ` (custom recognizers) |
| **Healthcare / PHI** | `PROVIDER_NPI`, `MEDICAL_RECORD_NUMBER`, `ICD10_CODE`, `HEALTH_PLAN_ID` (custom) |
| **Universal Identity** | `PERSON`, `DATE_OF_BIRTH`, `LOCATION`, `ADDRESS` (built-in NER) |
| **Financial** | `CREDIT_CARD`, `BANK_ACCOUNT`, `IBAN` (built-in) |
| **Contact** | `EMAIL_ADDRESS`, `PHONE_NUMBER`, `URL` |
| **Temporal** | `DATE_TIME` |
| **Digital** | `IP_ADDRESS` |

### Accuracy: check-digit verification
Regex matches alone produce false positives — random strings that merely *look* like a national identifier. Every regional recognizer therefore validates the identifier's official checksum before reporting it:

| Entity | Verification |
|---|---|
| `AADHAAR` | Verhoeff check digit (official UIDAI algorithm) |
| `EU_IBAN` | ISO 13616 mod-97 check (reference number `GB29 NWBK 6016 1331 9268 19`) |
| `EU_VAT` | Per-country official checksums (mod-11 weighted, mod-97, CIF, ISO 7064) covering every EU member state plus UK — including the letter-body formats `ATU…` (Austria), CIF (Spain), `IE…F` (Ireland) and `NL…B..` (Netherlands); CZ/SK are format-validated (no checksum exists by law) |
| `BR_CPF` / `BR_CNPJ` | Two mod-11 check digits |
| `PROVIDER_NPI` | CMS algorithm (80840 prefix + Luhn) |
| `US_ROUTING_NUMBER` | ABA mod-10 with 3-7-1 weights |
| `PAN_CARD` | Mod-36 checksum used as a **confidence boost** (the checksum is not officially published, so plain matches are still flagged — a DLP tool must err toward flagging) |

Validated matches are promoted to full confidence (1.0); identifiers that fail their checksum are dropped from the regional entity (they may still be caught by a generic class such as `PHONE_NUMBER`). Overlapping detections are resolved score-aware, keeping the strongest match per span.

Regional recognizers live in `backend/app/recognizers/` and load automatically at startup; all 16 shipped entities are active by default so no PII class is silently missed, and every entity can be **dynamically toggled on/off** by admins via the policy dashboard without redeploying. Custom regex patterns can also be added at runtime.

---

## Local Development Setup

### Prerequisites
```
Python 3.12+
Node.js 18+
Redis 7+ (or Docker) — required for async document processing
Optional: PostgreSQL (or NeonDB string), AWS S3, Auth0 tenant
```

> **No-config boot:** the app starts with a local SQLite database when `DATABASE_URL` is unset, so you can bring up the API and text-masking features immediately. Point `DATABASE_URL` at PostgreSQL for production/multi-instance deployments.

### 1. Clone and Configure
```bash
git clone https://github.com/BugHunterX2101/pii-masking-app.git
cd pii-masking-app
```

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in the services you are using. Only `REDIS_URL` is needed for the full async pipeline:
```env
# Redis (Celery Broker and Backend) — required for file uploads
REDIS_URL=redis://localhost:6379/0

# Database (optional — SQLite fallback when unset)
DATABASE_URL=postgresql://user:password@localhost:5432/pii_masking

# AWS S3 (required only for file upload/batch processing)
AWS_REGION=us-east-2
S3_BUCKET_NAME=pii-mask-ocr-files
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Auth0 SSO
AUTH0_DOMAIN=your-tenant.us.auth0.com
# AUTH0_AUDIENCE=your-api-audience   # set to enforce audience verification
# JWKS_TTL_SECONDS=21600             # how often the signing keys cache refreshes

# Admin Role Assignment (comma-separated emails — exact match required)
ADMIN_EMAILS=veditagrawal21@gmail.com,ceo@company.com

# Verified-email-provider policy (comma-separated; override the defaults)
# VERIFIED_EMAIL_PROVIDERS=gmail.com,outlook.com,yahoo.com
# DISPOSABLE_EMAIL_DOMAINS=mailinator.com,yopmail.com,10minutemail.com

# CORS allowed origins (comma-separated; "*" allows all)
# ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000

# OCR runs locally via RapidOCR (ONNX) — no credentials required
```

### 3. Backend Services
```bash
# Start Redis via Docker
docker run -d -p 6379:6379 --name redis redis:7

# Install Python dependencies (includes 24 small spaCy language models via wheel URLs)
pip install -r requirements.txt

# Start FastAPI server
uvicorn backend.app.main:app --reload --port 8000

# Start Celery Worker (separate terminal)
celery -A backend.app.worker.celery_app worker --loglevel=info --concurrency=4
```

### 4. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local   # sets REACT_APP_API_URL=http://localhost:8000
npm start
# App available at http://localhost:3000
```

### 5. Running the Test Suite
```bash
# Unit tests: check-digit validators, email policy, multilingual registry,
# and the document-handler exact-redaction guarantees (35 tests)
python -m pytest backend/tests -q

# Frontend production build check
cd frontend && npm run build
```
The CI pipeline (`.github/workflows/main.yml`) runs the same backend tests and a frontend build on every push and pull request — and only deploys to Hugging Face after both pass.

### 6. Run via Docker (Single Command)
```bash
docker build -t enterprise-privacy-suite .
docker run -p 7860:7860 --env-file .env enterprise-privacy-suite
# Supervisord automatically boots Redis, FastAPI, and Celery inside the container
```

---

## Deployment on Hugging Face

This application is hosted as a **Docker Space on Hugging Face** at:
**https://huggingface.co/spaces/vedit2101/pii-masking-app**

### How CI/CD Works

Every push to the `main` branch on GitHub automatically triggers the deployment pipeline:

```
git push origin main
  └── GitHub Actions (.github/workflows/main.yml)
        └── Upload entire repository to Hugging Face Space
              └── Hugging Face builds the Docker image
                    └── Supervisord starts Redis + FastAPI + Celery
```

The GitHub Actions workflow uses the `HF_TOKEN` secret stored in GitHub repository settings to authenticate with the Hugging Face API.

### Hugging Face Secrets Required

Set the following secrets in your Hugging Face Space settings under **Settings > Variables and secrets**:

| Secret Name | Description |
|---|---|
| `DATABASE_URL` | NeonDB or any PostgreSQL connection string (**optional** — app falls back to SQLite) |
| `AWS_REGION` | AWS region where your S3 bucket is located |
| `S3_BUCKET_NAME` | Name of your S3 bucket |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `REDIS_URL` | Defaults to `redis://localhost:6379/0` (local Redis inside the container) |
| `AUTH0_DOMAIN` | Your Auth0 tenant domain |
| `ADMIN_EMAILS` | Comma-separated emails to grant admin role |
| `VERIFIED_EMAIL_PROVIDERS` | Comma-separated allowlist of email providers (defaults to the well-known set) |
| `DISPOSABLE_EMAIL_DOMAINS` | Comma-separated blocklist of disposable/temporary mail domains |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (defaults to `*`) |
| `JWKS_TTL_SECONDS` | How long the Auth0 signing-key cache lives before refresh (default 21600) |

### Container Architecture on Hugging Face

The single Docker container runs three processes managed by Supervisord:

```
Container (Port 7860)
├── Redis 8          — in-process message broker and result backend
├── Uvicorn (FastAPI) — API server + serves React static build
└── Celery Worker    — async document processing (concurrency defaults to CPU count)
```

The React frontend is built during the Docker image build phase (`npm run build`) and served directly by FastAPI as static files. There is no separate frontend server.

---

## API Reference

### Authentication
All endpoints except `/api/auth/sync` require a valid Auth0 JWT in the Authorization header:
```
Authorization: Bearer <your-auth0-jwt>
```

### Core Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health` | None | Liveness probe: API + database status (used by the UI status bar) |
| `POST` | `/api/auth/sync` | JWT | Sync Auth0 user to DB (enforces verified-provider email policy); returns assigned role |
| `POST` | `/api/upload` | JWT | Upload document; returns `task_id` (HTTP 202) |
| `GET` | `/api/tasks/{task_id}` | JWT | Poll async task status and result |
| `POST` | `/api/mask-text` | JWT | Mask PII in raw text (synchronous, <200ms) |
| `POST` | `/api/cloud-scan` | JWT | Scan an S3 or Azure Blob bucket for PII |

### Admin-Only Endpoints (require `admin` role)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/users` | List all registered users and their roles |
| `GET` | `/api/admin/logs` | Fetch last 100 audit log entries |
| `GET` | `/api/admin/logs/export` | Export full audit log as CSV |
| `GET` | `/api/admin/policies` | List all DLP policies |
| `POST` | `/api/admin/policies` | Toggle a DLP policy on/off |
| `GET` | `/api/admin/settings` | Get global masking style setting |
| `PUT` | `/api/admin/settings` | Update masking style (LABEL / BLACKOUT / ASTERISK) |
| `GET` | `/api/admin/custom-regex` | List custom regex policies |
| `POST` | `/api/admin/custom-regex` | Add a new custom regex policy |
| `DELETE` | `/api/admin/custom-regex/{id}` | Delete a custom regex policy |
| `GET` | `/api/admin/analytics` | PII entity detection frequency analytics |
| `GET` | `/api/admin/api-keys` | List API keys for programmatic access |
| `POST` | `/api/admin/api-keys` | Create an API key (plaintext returned once) |
| `DELETE` | `/api/admin/api-keys/{id}` | Revoke an API key |

### Programmatic API (API Key Authentication)

Create an API key from the **Admin dashboard → API Keys** card (or `POST /api/admin/api-keys`). Keys authenticate via the `X-API-Key` header and are rate-limited per minute (`rate_limit` on the key, default 1000 req/min — enforced via Redis, returns `429` when exceeded).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/mask-text` | Mask text via API key (for integrations) |
| `POST` | `/api/v1/sanitize/dataset` | Sanitize a CSV/JSONL training dataset |
| `POST` | `/api/v1/scan/realtime` | Ultra-fast DLP scan for Slack/Teams webhooks (<100ms) |

```bash
curl -X POST https://vedit2101-pii-masking-app.hf.space/api/v1/mask-text \
  -H "X-API-Key: pk_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"text": "My Aadhaar is 2345 6789 0123", "language": "en"}'
# => {"original": "...", "masked": "My Aadhaar is [AADHAAR_MASKED]",
#     "pii_found": true, "pii_types": ["AADHAAR"], "count": 1}
```

> `count` is the number of PII matches found; `pii_types` lists the distinct entity types detected.

### Example: Upload and Poll
```bash
# 1. Upload a document
curl -X POST https://vedit2101-pii-masking-app.hf.space/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sensitive_doc.pdf"

# Response: {"status": "accepted", "task_id": "abc-123", "message": "..."}

# 2. Poll for result (repeat until status == "SUCCESS")
curl https://vedit2101-pii-masking-app.hf.space/api/tasks/abc-123 \
  -H "Authorization: Bearer $TOKEN"

# Response: {"task_id": "abc-123", "status": "SUCCESS",
#            "result": {"download_url": "https://s3.amazonaws.com/...", "report": [...]}}
```

---

## Compliance Coverage

| Standard | How This Suite Helps |
|---|---|
| **GDPR (EU)** | Right to erasure via masking; audit logs proving lawful processing |
| **HIPAA (USA)** | PHI de-identification from medical uploads; HIPAA compliance certificate generation |
| **DPDP Act (India)** | Aadhaar, PAN, and Passport masking; consent-based access controls |
| **SOC 2 Type II** | Complete audit trail; Auth0 access control; ephemeral data storage |
| **PCI-DSS** | Credit card numbers are never stored; masked tokens replace raw PANs |

---

## Project Structure

```
pii-masking-app/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app: all routes, middleware, S3 helpers
│       ├── worker.py            # Celery tasks: document, batch, dataset, cloud scan
│       ├── auth.py              # Auth0 JWT validation (RS256 + issuer check + TTL JWKS cache)
│       ├── models.py            # SQLAlchemy ORM: all database models
│       ├── database.py          # DB engine and session factory
│       ├── pii_engine.py        # Microsoft Presidio NLP detection and masking
│       ├── nlp_engine.py        # Lazy-loading multilingual spaCy engine (24 languages)
│       ├── checksums.py         # Check-digit validators (Verhoeff, Luhn, mod-97, mod-11, ...)
│       ├── email_verification.py# Verified-provider / disposable-domain / MX policy
│       ├── file_handlers.py     # PDF word-level, DOCX run-level, image RapidOCR processors
│       ├── compliance_cert.py   # HIPAA compliance certificate generator
│       ├── tests/               # Pytest suite (runs in CI without model downloads)
│       └── recognizers/         # Custom regional PII recognizers
│           ├── india.py         # Aadhaar, PAN, vehicle registration
│           ├── europe.py        # IBAN, EU VAT
│           ├── usa.py           # US routing numbers
│           ├── brazil.py        # CPF, CNPJ
│           └── healthcare.py    # NPI, MRN, ICD-10, health plan IDs
├── frontend/
│   └── src/
│       ├── App.js               # Main React app: all tabs, state, API calls
│       ├── App.css              # Complete design system: dark mode, glassmorphism
│       ├── index.js             # Auth0Provider, app bootstrap
│       └── .env.example         # Frontend env template (REACT_APP_API_URL, Auth0)
├── .github/
│   └── workflows/
│       └── main.yml             # CI/CD: backend tests + frontend build + HF deploy
├── Dockerfile                   # Multi-stage build: Node (frontend) then Python (backend)
├── supervisord.conf             # Process orchestration: Redis + FastAPI + Celery
├── requirements.txt             # Python dependencies (incl. spaCy model wheels)
├── .env.example                 # All supported environment variables
└── README.md                    # This file
```

---

<div align="center">

## Key Technical Achievements

| Achievement | Details |
|---|---|
| **Fully Async Pipeline** | HTTP request returns in <100ms while 50-page PDFs are processed in the background |
| **Zero Plaintext Storage** | Raw files are staged temporarily in S3; only masked outputs are persisted |
| **Hybrid Cloud** | Auth0 (Identity) + AWS (Storage) + NeonDB (Database); OCR runs locally on the worker (no cloud dependency) |
| **Multi-Language NLP** | 24 languages, lazy-loaded small SpaCy models (~10-15 MB each) |
| **Horizontally Scalable** | Add more Celery workers to any node; Redis broker coordinates automatically |
| **Enterprise-Ready** | RBAC, Audit Logs, Policy Management, Custom Regex, SSO — all production-grade |
| **Zero-Trust RBAC** | Role re-evaluated from env var on every login; database never the source of truth |
| **Live UI** | Real-time PII heatmap, command palette (Ctrl+K), toast notifications, animated canvas |
| **Exact Redaction** | Word-level PDF, run-level DOCX (formatting preserved), span-exact image masking — no over- or under-redaction |
| **Verified Accuracy** | 35 automated tests: check-digit validation, email policy, multilingual routing, and masked-document guarantees |

<br/>

---

<br/>

**Built with care — combining Cloud, AI, and Security into a single production-grade application.**

</div>
