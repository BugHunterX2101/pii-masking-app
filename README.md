---
title: Enterprise Privacy Suite
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

<div align="center">

# Enterprise Privacy Suite
### *Automated Data Loss Prevention (DLP) & PII Redaction at Cloud Scale*

[![React](https://img.shields.io/badge/Frontend-React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Workers-Celery-37814A?style=for-the-badge)](https://docs.celeryq.dev/)
[![Auth0](https://img.shields.io/badge/Auth-Auth0_SSO-eb5424?style=for-the-badge&logo=auth0)](https://auth0.com/)
[![AWS S3](https://img.shields.io/badge/Storage-AWS_S3-ff9900?style=for-the-badge&logo=amazonaws)](https://aws.amazon.com/s3/)
[![GCP Vision](https://img.shields.io/badge/OCR-GCP_Vision-4285F4?style=for-the-badge&logo=googlecloud)](https://cloud.google.com/vision)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)

<br/>

> **Every document your company handles is a potential data breach waiting to happen.** 
> The Enterprise Privacy Suite is an automated, cloud-native DLP pipeline that detects and permanently redacts sensitive PII from documents — *before* they ever reach your database, your support agents, or your AI models.

<br/>

**[Live Demo](https://huggingface.co/spaces/vedit2101/pii-masking-app)** &nbsp;|·&nbsp; **[Report a Bug](https://github.com/BugHunterX2101/pii-masking-app/issues)** &nbsp;|·&nbsp; **[Request a Feature](https://github.com/BugHunterX2101/pii-masking-app/issues)**

</div>

---

## Table of Contents
1. [The Problem We Solve](#the-problem-we-solve)
2. [Key Capabilities](#key-capabilities)
3. [Full System Architecture](#full-system-architecture)
4. [PII Processing Deep Dive](#pii-processing-deep-dive)
5. [Authentication & RBAC Flow](#authentication--rbac-flow)
6. [Database Schema](#database-schema)
7. [Technology Stack](#technology-stack)
8. [Supported PII Entity Types](#supported-pii-entity-types)
9. [Local Development Setup](#local-development-setup)
10. [API Reference](#api-reference)
11. [Compliance Coverage](#compliance-coverage)
12. [Project Structure](#project-structure)

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

### Admin Dashboard & Live Policy Engine
- **RBAC**: First registered user becomes `admin`. All subsequent users are `standard users`.
- **DLP Policy Toggles**: Admins can enable/disable specific PII entity types (e.g., turn off `PERSON` detection for a specific data processing workflow) in real-time from the UI.
- **Immutable Audit Log**: Every masking operation is logged to PostgreSQL: Auth0 User ID, IP address, filename, timestamp, and detected entity types.

---

##  Full System Architecture

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
Redis["Redis 7\nMessage Broker\n+ Result Backend"]
Worker["Celery Worker\nProcess Pool"]
end

subgraph AI [" AI / ML Layer"]
GCPVision["Google Cloud Vision API\nOCR Engine"]
Presidio["Microsoft Presidio\nNER Engine"]
Spacy["SpaCy en_core_web_lg\nNLP Model"]
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

The document goes through a specific pipeline based on its file type. Here is the complete decision tree:

```mermaid
flowchart TD
Start([" File Received by Celery Worker"]) --> TypeCheck{{"File Extension?"}}

TypeCheck -->|".pdf"| PDF["PyMuPDF\nExtract pages as images"]
TypeCheck -->|".docx"| DOCX["python-docx\nExtract paragraph runs"]
TypeCheck -->|".jpg/.png/.webp"| IMG["Raw Image Bytes"]

PDF --> GCP1[" GCP Vision API\nper-page OCR"]
IMG --> GCP2[" GCP Vision API\nfull image OCR"]
DOCX --> Direct["Direct Text Extraction\n(no OCR needed)"]

GCP1 --> TextBlocks["Text Annotations\n+ Bounding Boxes"]
GCP2 --> TextBlocks

TextBlocks --> Presidio[" Microsoft Presidio\nNER Detection"]
Direct --> Presidio

Presidio --> Entities{{"PII Found?"}}

Entities -->|"Yes"| Redact["Apply Redaction\nBlack Box / Token Replace"]
Entities -->|"No"| PassThrough["Pass-through unchanged"]

Redact --> Report[" Build Detection Report\n{text, pii_types, location}"]
PassThrough --> Report

Report --> S3Upload[" Upload Masked Output to S3"]
S3Upload --> PreSignedURL[" Generate 1-Hour Pre-signed URL"]
PreSignedURL --> ResultBackend[" Publish SUCCESS to Redis\n{download_url, report}"]
```

---

## Authentication & RBAC Flow

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
FastAPI->>FastAPI: Validates JWT signature & expiry

alt User exists in DB
FastAPI->>DB: SELECT * FROM users WHERE username = sub
DB-->>FastAPI: Existing user record + role
else First-ever login
FastAPI->>DB: INSERT user (role='admin')
DB-->>FastAPI: New user record
else Subsequent login
FastAPI->>DB: INSERT user (role='user')
DB-->>FastAPI: New user record
end

FastAPI-->>User: { status: "synced", role: "admin|user" }

Note over User,FastAPI: All subsequent API calls carry Bearer JWT
Note over FastAPI,DB: Admin-only endpoints check role before responding
```

---

##  Database Schema

```mermaid
erDiagram
USERS {
int id PK
string username "Auth0 sub claim"
string hashed_password "SSO for Auth0 users"
string role "admin or user"
datetime created_at
}

AUDIT_LOGS {
int id PK
int user_id FK
string action "LOGIN, FILE_MASK_TASK_STARTED, TEXT_MASK"
string ip_address
json details "filename, task_id, detected_entities"
datetime timestamp
}

DLP_POLICIES {
int id PK
string pii_type "PERSON, EMAIL_ADDRESS, CREDIT_CARD, etc."
bool is_active
datetime updated_at
}

USERS ||--o{ AUDIT_LOGS : "generates"
```

---

## Technology Stack

| Layer | Technology | Version | Why This Choice |
|-------|------------|---------|-----------------|
| **Frontend** | React | 18 | Component-driven SPA, Auth0 SDK |
| **UI Library** | Lucide React + Vanilla CSS | Latest | Zero dependency, dark-mode glassmorphism |
| **Backend** | FastAPI | 0.110+ | Async-native Python, OpenAPI auto-docs |
| **Auth** | Auth0 (RS256 JWT) | — | Enterprise SSO; no password management |
| **ORM** | SQLAlchemy + Alembic | 2.0 | Type-safe DB sessions, migration support |
| **Database** | PostgreSQL (NeonDB) | 16 | Serverless Postgres; scales to zero |
| **Task Queue** | Celery | 5.3.6 | Distributed async workers; Redis backend |
| **Broker** | Redis | 7 | In-memory pub/sub; sub-millisecond latency |
| **Storage** | AWS S3 + Boto3 | Latest | Durable object storage; pre-signed URL support |
| **OCR** | Google Cloud Vision API | v1 | Best-in-class accuracy on low-quality scans |
| **NLP / NER** | Microsoft Presidio + SpaCy | 2.2 / 3.7 | Context-aware PII detection beyond regex |
| **PDF** | PyMuPDF (fitz) | 1.24 | Fast, accurate PDF page rendering |
| **Word** | python-docx | 1.1 | Native `.docx` manipulation |
| **Image Processing** | OpenCV | 4.9 | Bounding box redaction on images |
| **Container** | Docker + Supervisord | Latest | Multi-process single-container orchestration |

---

## Supported PII Entity Types

The Presidio NLP engine detects **18+ entity types** out of the box, with custom recognizers added for Indian documents:

| Category | Entities Detected |
|---|---|
| **Identity** | `PERSON`, `AADHAAR`, `PAN_CARD`, `PASSPORT` |
| **Financial** | `CREDIT_CARD`, `BANK_ACCOUNT`, `IBAN_CODE` |
| **Contact** | `EMAIL_ADDRESS`, `PHONE_NUMBER`, `URL` |
| **Location** | `LOCATION`, `ADDRESS` |
| **Temporal** | `DATE_TIME`, `DATE_OF_BIRTH` |
| **Digital** | `IP_ADDRESS`, `NRP` |

All entity types can be **dynamically toggled on/off** by admins via the policy dashboard without redeploying.

---

##  Local Development Setup

### Prerequisites
```
Python 3.12+
Node.js 18+
PostgreSQL 15+ (or NeonDB connection string)
Redis 7+ (or Docker)
AWS Account (S3 Bucket created)
Google Cloud Project (Vision API enabled)
Auth0 Tenant (Single Page Application + API configured)
```

### 1. Clone & Configure
```bash
git clone https://github.com/BugHunterX2101/pii-masking-app.git
cd pii-masking-app

# Copy and fill in your credentials
cp .env.example .env
```

### 2. Environment Variables
```env
# — Database -----------------------------------------------
DATABASE_URL=postgresql://user:password@localhost:5432/pii_masking

# — AWS S3 -------------------------------------------------
AWS_REGION=us-east-2
S3_BUCKET_NAME=pii-mask-ocr-files
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# — Redis (Celery Broker & Backend) ------------------------
REDIS_URL=redis://localhost:6379/0

# — Auth0 SSO & Roles ----------------------------------------
AUTH0_DOMAIN=your-tenant.us.auth0.com
ADMIN_EMAILS=ceo@company.com,security@company.com

# — GCP Vision (path to service account JSON) --------------
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-gcp-key.json
```

### 3. Backend Services
```bash
# Start Redis via Docker (fastest way)
docker run -d -p 6379:6379 --name redis redis:7

# Python environment
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

# Set backend URL for development
echo "REACT_APP_API_URL=http://localhost:8000" > .env.local

npm start
# → App available at http://localhost:3000
```

### 5. Run via Docker (Single Command)
```bash
docker build -t enterprise-privacy-suite .
docker run -p 7860:7860 --env-file .env enterprise-privacy-suite
# Supervisord automatically boots Redis, FastAPI, and Celery
```

---

## API Reference

### Authentication
All endpoints (except `/api/auth/sync`) require a valid Auth0 JWT in the Authorization header:
```
Authorization: Bearer <your-auth0-jwt>
```

### Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/sync` | JWT | Sync Auth0 user to DB; returns role |
| `POST` | `/api/upload` | JWT | Upload document; returns `task_id` (202) |
| `GET` | `/api/tasks/{task_id}` | JWT | Poll async task status |
| `POST` | `/api/mask-text` | JWT | Mask PII in raw text (synchronous) |
| `GET` | `/api/admin/logs` | Admin JWT | Fetch last 100 audit log entries |
| `GET` | `/api/admin/policies` | Admin JWT | List all DLP policies |
| `POST` | `/api/admin/policies` | Admin JWT | Toggle a DLP policy on/off |

### Example: Upload & Poll
```bash
# 1. Upload a document
curl -X POST https://your-app/api/upload \
-H "Authorization: Bearer $TOKEN" \
-F "file=@sensitive_doc.pdf"

# → Response: {"status": "accepted", "task_id": "abc-123", "message": "..."}

# 2. Poll for result (repeat until status == "SUCCESS")
curl https://your-app/api/tasks/abc-123 \
-H "Authorization: Bearer $TOKEN"

# → Response: {"task_id": "abc-123", "status": "SUCCESS",
# "result": {"download_url": "https://s3.amazonaws.com/...", "report": [...]}}
```


---

## Compliance Coverage

| Standard | How This Suite Helps |
|---|---|
| **GDPR (EU)** | Right to erasure via masking; audit logs proving lawful processing |
| **HIPAA (USA)** | PHI de-identification from medical uploads |
| **DPDP Act (India)** | Aadhaar, PAN, and Passport masking; consent-based access controls |
| **SOC 2 Type II** | Complete audit trail; Auth0 access control; ephemeral data storage |
| **PCI-DSS** | Credit card numbers are never stored; masked tokens replace raw PANs |

---

## Project Structure

```
pii-masking-app/
├── backend/
| ├── app/
| ├── main.py # FastAPI app: routes, middleware, S3 helpers
| ├── worker.py # Celery task: full async document processing pipeline
| ├── auth.py # Auth0 JWT validation (RS256)
| ├── models.py # SQLAlchemy ORM: User, AuditLog, DLPPolicy
| ├── database.py # DB engine & session factory
| ├── pii_engine.py # Microsoft Presidio NLP detection + masking
| ├── file_handlers.py # PDF (PyMuPDF) & Word (python-docx) processors
├── frontend/
| ├── src/
│   ├── App.js          # Main React app: Auth0, polling, UI state
| ├── App.css # Dark-mode glassmorphism design system
│   ├── index.js        # Auth0Provider, app bootstrap
├── Dockerfile # Multi-stage build (Node → Python)
├── supervisord.conf    # Process orchestration: Redis + FastAPI + Celery
├── requirements.txt # Python dependencies
├── README.md # You are here
```

---

<div align="center">

## Key Technical Achievements

| | |
|---|---|
| **Fully Async Pipeline** | HTTP request returns in <100ms while 50-page PDFs are processed in the background |
| **Zero Plaintext Storage** | Raw files are staged temporarily; only masked outputs are persisted |
| **Multi-Cloud** | Auth0 (Identity) + GCP (OCR) + AWS (Storage) + NeonDB (Database) |
| **Horizontally Scalable** | Add more Celery workers to any node; Redis broker coordinates automatically |
| **Enterprise-Ready** | RBAC, Audit Logs, Policy Management, SSO — all production-grade |

<br/>

---

<br/>

**Built with care — combining Cloud, AI, and Security into a single production-grade application.**


</div>
