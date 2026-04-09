# PII Masking App

Automatically detect and redact **Personally Identifiable Information** from document images and free-form text using OCR and pattern matching — no external AI APIs required.

---

## What it does

| Mode | Input | Output |
|---|---|---|
| **Image** | JPEG / PNG / WebP / BMP document photo | Masked image with PII regions blacked out + detection report |
| **Text** | Any free-form text | Redacted text with `[TYPE_MASKED]` tokens replacing PII |

### Detected PII types

| Type | Pattern / Method | Example |
|---|---|---|
| Aadhaar Number | `\d{4} \d{4} \d{4}` | `1234 5678 9012` |
| PAN Card | `[A-Z]{5}[0-9]{4}[A-Z]` | `ABCDE1234F` |
| Passport | `[A-Z][0-9]{7}` | `A1234567` |
| Indian Phone | Anchored `[6-9]\d{9}` | `9876543210` |
| Email Address | RFC-style regex | `user@example.com` |
| Date of Birth | `DD/MM/YYYY` variants | `01/01/1990` |
| Credit/Debit Card | 13–16 digit sequences | `4111 1111 1111 1111` |
| PIN Code | 6-digit Indian postal | `400001` |
| Vehicle Registration | `MH 12 AB 1234` | `MH 12 AB 1234` |
| Name / Address / DOB / Gender | Keyword whole-word match | `Name:`, `DOB:`, `Address:` |

---

## Architecture

```mermaid
flowchart TD
    Browser["🌐 Browser / React Frontend"]

    Browser -->|"POST /api/upload\nmultipart/form-data"| Upload["api/upload.py\nVercel Serverless"]
    Browser -->|"POST /api/mask-text\napplication/json"| Upload
    Browser -->|"GET /api"| Index["api/index.py\nHealth Check"]

    Upload --> OCR["EasyOCR\nreadtext()"]
    Upload --> Detect["detect_pii()\nRegex + Keywords"]

    OCR --> Detect
    Detect -->|"PII found"| Mask["cv2.rectangle()\nBlack fill over bbox"]
    Detect -->|"Text route"| Redact["Token replacement\n[TYPE_MASKED]"]

    Mask --> Response["JPEG binary\n+ X-PII-Report header"]
    Redact --> JSONResp["JSON response\nmasked text + types"]

    Response --> Browser
    JSONResp --> Browser

    style Browser fill:#E8DDD0,stroke:#C4714A,color:#2C2416
    style Upload fill:#F5E0D4,stroke:#C4714A,color:#2C2416
    style OCR fill:#DDE8DD,stroke:#6B8C6B,color:#2C2416
    style Detect fill:#DDE8DD,stroke:#6B8C6B,color:#2C2416
    style Mask fill:#FBF0DA,stroke:#D4891A,color:#2C2416
    style Redact fill:#FBF0DA,stroke:#D4891A,color:#2C2416
    style Response fill:#E8DDD0,stroke:#6B8C6B,color:#2C2416
    style JSONResp fill:#E8DDD0,stroke:#6B8C6B,color:#2C2416
    style Index fill:#F0E9DF,stroke:#6B5D4A,color:#2C2416
```

### Request flow — image masking

```mermaid
sequenceDiagram
    participant B as Browser
    participant V as Vercel (upload.py)
    participant OCR as EasyOCR Engine
    participant CV as OpenCV

    B->>V: POST /api/upload (multipart/form-data)
    V->>V: cgi.FieldStorage.parse()
    V->>CV: cv2.imdecode(image_bytes)
    CV-->>V: numpy array (H×W×3)

    V->>OCR: easyocr.readtext(rgb_array)
    OCR-->>V: [(bbox, text, confidence), ...]

    loop For each detected text region
        V->>V: detect_pii(text)
        alt PII detected
            V->>CV: cv2.rectangle(black fill)
            V->>V: Append to report[]
        end
    end

    V->>CV: cv2.imencode('.jpg', masked_img)
    CV-->>V: JPEG bytes

    V-->>B: 200 image/jpeg (masked image)
    Note over B,V: X-PII-Report: [{text, pii_types, confidence}]
    Note over B,V: X-PII-Count: N
    Note over B,V: Access-Control-Expose-Headers: X-PII-Report, X-PII-Count
```

### Request flow — text masking

```mermaid
sequenceDiagram
    participant B as Browser
    participant V as Vercel (upload.py)

    B->>V: POST /api/mask-text
    Note over B,V: {"text": "My Aadhaar is 1234 5678 9012"}

    V->>V: detect_pii(text)
    Note over V: Check 9 regex patterns
    Note over V: Check 4 keyword groups

    V->>V: Replace matches with [TYPE_MASKED] tokens

    V-->>B: 200 application/json
    Note over B,V: {original, masked, pii_found, pii_types, count}
```

### PII detection engine

```mermaid
flowchart LR
    Input["Input text"] --> Regex["Regex patterns"]
    Input --> Keywords["Keyword groups"]

    Regex --> A["Aadhaar\n\\d{4} \\d{4} \\d{4}"]
    Regex --> B["PAN Card\n[A-Z]{5}[0-9]{4}[A-Z]"]
    Regex --> C["Passport\n[A-Z][0-9]{7}"]
    Regex --> D["Phone\n[6-9]\\d{9}"]
    Regex --> E["Email\nRFC regex"]
    Regex --> F["Date of Birth\nDD/MM/YYYY"]
    Regex --> G["Credit Card\n13–16 digits"]
    Regex --> H["PIN Code\n6-digit postal"]
    Regex --> I["Vehicle Reg\nMH 12 AB 1234"]

    Keywords --> J["name / naam\n\\b boundary"]
    Keywords --> K["address / addr\n\\b boundary"]
    Keywords --> L["dob / born\n\\b boundary"]
    Keywords --> M["male / female\n\\b boundary"]

    A & B & C & D & E & F & G & H & I --> Out["detected types[ ]"]
    J & K & L & M --> Out
    Out --> Mask["Redact / mask"]

    style Input fill:#E8DDD0,stroke:#C4714A,color:#2C2416
    style Regex fill:#F5E0D4,stroke:#C4714A,color:#2C2416
    style Keywords fill:#DDE8DD,stroke:#6B8C6B,color:#2C2416
    style Out fill:#FBF0DA,stroke:#D4891A,color:#2C2416
    style Mask fill:#DDE8DD,stroke:#6B8C6B,color:#2C2416
```

---

## File structure

```
pii-masking-app/
│
├── api/                            Vercel serverless functions
│   ├── index.py                    GET /api — health check + endpoint list
│   ├── upload.py                   POST /api/upload + POST /api/mask-text
│   ├── requirements.txt            Python deps for Vercel (headless, minimal)
│   └── processed/
│       └── [filename].py           GET /api/processed/:file — serve masked images
│
├── backend/                        Local development FastAPI server
│   ├── run.py                      Entry point: uvicorn app.main:app
│   ├── requirements.txt            Full deps including uvicorn
│   ├── test_pii_detection.py       Unit tests for PII detection patterns
│   └── app/
│       └── main.py                 FastAPI app — mirrors api/upload.py logic
│
├── frontend/                       React 18 SPA
│   ├── package.json                Dependencies: react, react-dom, react-scripts
│   ├── .env.production             REACT_APP_API_URL= (empty — same-origin /api/*)
│   ├── .env.local.example          Template: point to localhost:8000 for local dev
│   ├── public/
│   │   └── index.html              HTML shell
│   └── src/
│       ├── index.js                ReactDOM.createRoot entry
│       ├── index.css               Minimal reset
│       ├── App.js                  Two-tab UI: image upload + text masking
│       └── App.css                 Design system (warm earthy palette)
│
├── vercel.json                     Routing: static build + serverless functions
├── test_vercel_deployment.py       Integration tests (health, mask-text, upload)
├── README.md                       This file
└── DEPLOYMENT.md                   Vercel deployment walkthrough
```

---

## Quick start

### Option A — Local backend (FastAPI)

```bash
# 1. Clone
git clone https://github.com/BugHunterX2101/pii-masking-app.git
cd pii-masking-app

# 2. Backend
cd backend
pip install -r requirements.txt
python run.py
# API at http://localhost:8000

# 3. Frontend (new terminal)
cd ../frontend
cp .env.local.example .env.local
# .env.local already has REACT_APP_API_URL=http://localhost:8000
npm install
npm start
# App at http://localhost:3000
```

### Option B — Vercel dev (serverless locally)

```bash
npm install -g vercel
vercel dev
# Frontend + serverless functions at http://localhost:3000
```

### Option C — Deploy to Vercel

```bash
vercel --prod
```

---

## API reference

### `POST /api/upload`

Upload an image; returns the masked image as JPEG binary.

**Request:** `multipart/form-data`, field name `file`

**Response:**
- Body: JPEG image bytes (masked)
- `Content-Type: image/jpeg`
- `X-PII-Report: [{"text": "...", "pii_types": [...], "confidence": 0.95}, ...]`
- `X-PII-Count: N`
- `Access-Control-Expose-Headers: X-PII-Report, X-PII-Count`

| Code | Reason |
|---|---|
| 400 | No file field / empty file / not an image |
| 500 | OCR or image processing error |

---

### `POST /api/mask-text`

**Request body:**
```json
{ "text": "My Aadhaar is 1234 5678 9012 and email is me@example.com" }
```

**Response:**
```json
{
  "original":  "My Aadhaar is 1234 5678 9012 and email is me@example.com",
  "masked":    "My Aadhaar is [AADHAAR_MASKED] and email is [EMAIL_MASKED]",
  "pii_found": true,
  "pii_types": ["aadhaar", "email"],
  "count":     2
}
```

---

### `GET /api`

Health check — returns version and available endpoints.

---

## Running tests

```bash
# Unit tests (PII pattern logic, no OCR required)
cd backend
python test_pii_detection.py

# Integration tests (requires running server)
python test_vercel_deployment.py --base-url http://localhost:8000
```

---

## Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18 | SPA with drag-and-drop, two-tab interface |
| Fonts | Playfair Display, Source Sans 3 | Warm serif + clean body pairing |
| API (serverless) | Python `BaseHTTPRequestHandler` | Vercel-compatible handlers |
| API (local dev) | FastAPI + Uvicorn | Full-featured local server |
| OCR | EasyOCR 1.7.2 | Text extraction from images |
| Image processing | OpenCV headless 4.8 | Decode, rectangle masking, re-encode |
| Pattern matching | Python `re` | Compiled regex for all PII types |
| Deployment | Vercel | Static CDN + Python serverless functions |

---

## Known limitations

- **Ephemeral `/tmp`** — Vercel invocations don't share `/tmp`. The `/api/processed` endpoint works locally; in production the masked image is returned directly in the upload response body.
- **OCR accuracy** — EasyOCR performs well on printed text but may miss handwritten or heavily stylised fonts.
- **Cold starts** — First request after idle may take 10–30 s while EasyOCR loads model weights (~50 MB).
- **File size** — Images over ~5 MB may hit Vercel's 10 MB request body limit. Compress before uploading.
