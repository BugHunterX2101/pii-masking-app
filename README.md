---
title: Enterprise Privacy Suite
emoji: 🛡️
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
[![GCP Vision](https://img.shields.io/badge/OCR-GCP_Vision-4285F4?style=for-the-badge&logo=googlecloud)](https://cloud.google.com/vision)
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
1. **Google Cloud Vision API** — Performs server-side OCR, extracting every character from scanned images, IDs, and screenshots with state-of-the-art accuracy, even on low-quality images.
2. **Microsoft Presidio (NLP)** — Runs named-entity recognition (NER) on the extracted text using SpaCy's `en_core_web_lg` model to catch contextual PII (like names in a sentence) that regex alone would miss.

### Multi-Language Support
The detection engine supports **8 languages** with dedicated SpaCy models:

| Language | SpaCy Model |
|---|---|
| English | `en_core_web_lg` |
| Spanish | `es_core_news_lg` |
| French | `fr_core_news_lg` |
| German | `de_core_news_lg` |
| Italian | `it_core_news_lg` |
| Portuguese | `pt_core_news_lg` |
| Japanese | `ja_core_news_lg` |
| Chinese | `zh_core_web_lg` |

### Event-Driven Asynchronous Architecture
Large files (multi-page PDFs, high-res images) can take several seconds to process. In a synchronous system, this would cause HTTP timeouts, thread starvation, and a terrible user experience. This suite uses a **full event-driven pipeline**:
- The FastAPI server **immediately** responds with `HTTP 202 Accepted` + a `task_id`.
- The Celery worker processes the document entirely in the background.
- The React frontend **polls** `/api/tasks/{task_id}` every 2 seconds, rendering a live progress state.
- On completion, the UI delivers the masked file to the user via a **secure S3 pre-signed URL** (expires in 1 hour).

### Zero-Trust Security Model
- **Auth0 SSO**: Users authenticate via corporate identity providers (Microsoft Entra ID, Google Workspace, Okta). No passwords are stored in the application database.
- **JWT Validation (RS256)**: Every single API call validates the Auth0 JWT against the JWKS endpoint. Unauthenticated requests receive `HTTP 401`.
- **Ephemeral Storage**: Raw (unmasked) files are temporarily staged in a private S3 prefix and are never returned to the client. Only the masked output is accessible via a time-limited pre-signed URL.

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
Worker["Celery Worker\nProcess Pool (16 concurrent)"]
end

subgraph AI [" AI / ML Layer"]
GCPVision["Google Cloud Vision API\nOCR Engine"]
Presidio["Microsoft Presidio\nNER Engine"]
Spacy["SpaCy (8 language models)\nNLP Models"]
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
Worker -- "11. OCR Request" --> GCPVision
GCPVision -- "12. Text Annotations" --> Worker
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

TypeCheck -->|".pdf"| PDF["PyMuPDF\nExtract pages as images"]
TypeCheck -->|".docx"| DOCX["python-docx\nExtract paragraph runs"]
TypeCheck -->|".jpg/.png/.webp"| IMG["Raw Image Bytes"]
TypeCheck -->|".csv/.jsonl"| DS["Dataset Parser\nRow-by-row processing"]

PDF --> GCP1[" GCP Vision API\nper-page OCR"]
IMG --> GCP2[" GCP Vision API\nfull image OCR"]
DOCX --> Direct["Direct Text Extraction\n(no OCR needed)"]
DS --> Direct

GCP1 --> TextBlocks["Text Annotations\n+ Bounding Boxes"]
GCP2 --> TextBlocks

TextBlocks --> Presidio[" Microsoft Presidio\nNER Detection"]
Direct --> Presidio

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
| **Fonts** | Outfit + Inter (Google Fonts) | Latest | Premium typographic hierarchy |
| **Backend** | FastAPI | 0.110+ | Async-native Python, OpenAPI auto-docs |
| **ASGI Server** | Uvicorn | Latest | Production-grade ASGI with hot-reload |
| **Auth** | Auth0 (RS256 JWT) | — | Enterprise SSO; no password management |
| **ORM** | SQLAlchemy | 2.0 | Type-safe DB sessions |
| **Database** | PostgreSQL (NeonDB) | 16 | Serverless Postgres; scales to zero |
| **Task Queue** | Celery | 5.3.6 | Distributed async workers; Redis backend |
| **Broker** | Redis | 8 | In-memory pub/sub; sub-millisecond latency |
| **Storage** | AWS S3 + Boto3 | Latest | Durable object storage; pre-signed URL support |
| **OCR** | Google Cloud Vision API | v1 | Best-in-class accuracy on low-quality scans |
| **NLP / NER** | Microsoft Presidio + SpaCy | 2.2 / 3.7 | Context-aware PII detection beyond regex |
| **PDF** | PyMuPDF (fitz) | 1.24 | Fast, accurate PDF page rendering |
| **Word** | python-docx | 1.1 | Native `.docx` manipulation |
| **Image** | OpenCV | 4.9 | Bounding box redaction on images |
| **Container** | Docker + Supervisord | Latest | Multi-process single-container orchestration |
| **CI/CD** | GitHub Actions | — | Automated deploy to Hugging Face on every push to `main` |

---

## Supported PII Entity Types

The Presidio NLP engine detects **20+ entity types** out of the box, with custom recognizers built for regional documents:

| Category | Entities Detected |
|---|---|
| **Indian Identity** | `AADHAAR`, `PAN_CARD`, `PASSPORT`, `INDIA_IFSC` |
| **European Identity** | `IBAN_CODE`, `NHS_NUMBER`, `NRP` |
| **US Identity** | `US_SSN`, `US_EIN`, `US_PASSPORT` |
| **Brazilian Identity** | `BRAZIL_CPF` |
| **Universal Identity** | `PERSON`, `DATE_OF_BIRTH` |
| **Financial** | `CREDIT_CARD`, `BANK_ACCOUNT` |
| **Contact** | `EMAIL_ADDRESS`, `PHONE_NUMBER`, `URL` |
| **Location** | `LOCATION`, `ADDRESS` |
| **Temporal** | `DATE_TIME` |
| **Digital** | `IP_ADDRESS` |

All entity types can be **dynamically toggled on/off** by admins via the policy dashboard without redeploying. Custom regex patterns can also be added at runtime.

---

## Local Development Setup

### Prerequisites
```
Python 3.12+
Node.js 18+
PostgreSQL 15+ (or NeonDB connection string)
Redis 7+ (or Docker)
AWS Account (S3 bucket created)
Google Cloud Project (Vision API enabled + service account JSON)
Auth0 Tenant (Single Page Application configured)
```

### 1. Clone and Configure
```bash
git clone https://github.com/BugHunterX2101/pii-masking-app.git
cd pii-masking-app
```

### 2. Environment Variables
Create a `.env` file at the project root:
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pii_masking

# AWS S3
AWS_REGION=us-east-2
S3_BUCKET_NAME=pii-mask-ocr-files
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Redis (Celery Broker and Backend)
REDIS_URL=redis://localhost:6379/0

# Auth0 SSO
AUTH0_DOMAIN=your-tenant.us.auth0.com

# Admin Role Assignment (comma-separated emails)
ADMIN_EMAILS=veditagrawal21@gmail.com,ceo@company.com

# GCP Vision (path to service account JSON)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-gcp-key.json
```

### 3. Backend Services
```bash
# Start Redis via Docker
docker run -d -p 6379:6379 --name redis redis:7

# Install Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# Start FastAPI server
uvicorn backend.app.main:app --reload --port 8000

# Start Celery Worker (separate terminal)
celery -A backend.app.worker.celery_app worker --loglevel=info --concurrency=4
```

### 4. Frontend
```bash
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:8000" > .env.local
npm start
# App available at http://localhost:3000
```

### 5. Run via Docker (Single Command)
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
| `DATABASE_URL` | NeonDB or any PostgreSQL connection string |
| `AWS_REGION` | AWS region where your S3 bucket is located |
| `S3_BUCKET_NAME` | Name of your S3 bucket |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `REDIS_URL` | Defaults to `redis://localhost:6379/0` (local Redis inside the container) |
| `AUTH0_DOMAIN` | Your Auth0 tenant domain |
| `ADMIN_EMAILS` | Comma-separated emails to grant admin role |
| `GCP_CREDENTIALS_JSON` | Full contents of your GCP service account JSON file |

### Container Architecture on Hugging Face

The single Docker container runs three processes managed by Supervisord:

```
Container (Port 7860)
├── Redis 8          — in-process message broker and result backend
├── Uvicorn (FastAPI) — API server + serves React static build
└── Celery Worker    — async document processing with 16 concurrent workers
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
| `POST` | `/api/auth/sync` | JWT | Sync Auth0 user to DB; returns assigned role |
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

### Programmatic API (API Key Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/mask-text` | Mask text via API key (for integrations) |
| `POST` | `/api/v1/sanitize/dataset` | Sanitize a CSV/JSONL training dataset |
| `POST` | `/api/v1/scan/realtime` | Ultra-fast DLP scan for Slack/Teams webhooks (<100ms) |

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
│       ├── auth.py              # Auth0 JWT validation (RS256 + JWKS)
│       ├── models.py            # SQLAlchemy ORM: all database models
│       ├── database.py          # DB engine and session factory
│       ├── pii_engine.py        # Microsoft Presidio NLP detection and masking
│       ├── file_handlers.py     # PDF (PyMuPDF) and Word (python-docx) processors
│       ├── compliance_cert.py   # HIPAA compliance certificate generator
│       └── recognizers/         # Custom regional PII recognizers
│           ├── india.py         # Aadhaar, PAN, IFSC
│           ├── europe.py        # IBAN, NHS
│           ├── usa.py           # SSN, EIN
│           └── brazil.py        # CPF
├── frontend/
│   └── src/
│       ├── App.js               # Main React app: all tabs, state, API calls
│       ├── App.css              # Complete design system: dark mode, glassmorphism
│       └── index.js             # Auth0Provider, app bootstrap
├── .github/
│   └── workflows/
│       └── main.yml             # CI/CD: GitHub Actions to Hugging Face
├── Dockerfile                   # Multi-stage build: Node (frontend) then Python (backend)
├── supervisord.conf             # Process orchestration: Redis + FastAPI + Celery
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

<div align="center">

## Key Technical Achievements

| Achievement | Details |
|---|---|
| **Fully Async Pipeline** | HTTP request returns in <100ms while 50-page PDFs are processed in the background |
| **Zero Plaintext Storage** | Raw files are staged temporarily in S3; only masked outputs are persisted |
| **Multi-Cloud** | Auth0 (Identity) + GCP (OCR) + AWS (Storage) + NeonDB (Database) |
| **Multi-Language NLP** | 8 SpaCy language models for global PII detection |
| **Horizontally Scalable** | Add more Celery workers to any node; Redis broker coordinates automatically |
| **Enterprise-Ready** | RBAC, Audit Logs, Policy Management, Custom Regex, SSO — all production-grade |
| **Zero-Trust RBAC** | Role re-evaluated from env var on every login; database never the source of truth |
| **Live UI** | Real-time PII heatmap, command palette (Ctrl+K), toast notifications, animated canvas |

<br/>

---

<br/>

**Built with care — combining Cloud, AI, and Security into a single production-grade application.**

</div>
