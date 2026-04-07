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

```
┌────────────────────────────────────────────────────────────────┐
│                         Browser / Client                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     React Frontend                       │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │   │
│  │  │ Image Upload │  │  Text Input  │  │ Detection Report│  │   │
│  │  │  Drag & Drop │  │   Textarea   │  │  Type Badges   │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────────────┘  │   │
│  └─────────┼────────────────┼──────────────────────────────┘   │
└────────────┼────────────────┼────────────────────────────────────┘
             │ POST /api/upload│ POST /api/mask-text
             │ multipart/form  │ application/json
             ▼                 ▼
┌────────────────────────────────────────────────────────────────┐
│              Vercel Serverless Functions (Python)               │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────────────────────┐  │
│  │   api/upload.py  │    │         api/index.py              │  │
│  │                  │    │    (health check + API docs)       │  │
│  │  1. cgi.FieldStorage│  └──────────────────────────────────┘  │
│  │     multipart parse│                                          │
│  │  2. Lazy EasyOCR  │  ┌──────────────────────────────────┐  │
│  │     (cached/proc) │  │   api/processed/[filename].py    │  │
│  │  3. detect_pii()  │  │   (serve masked images, CORS)    │  │
│  │  4. cv2.rectangle │  └──────────────────────────────────┘  │
│  │  5. Return JPEG + │                                          │
│  │     X-PII-Report  │                                          │
│  └──────────────────┘                                          │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│                     PII Detection Engine                         │
│                                                                  │
│   Image path:                      Text path:                   │
│   Image bytes                      Raw string                   │
│       │                                │                        │
│       ▼                                ▼                        │
│   EasyOCR.readtext()           detect_pii(text)                 │
│   (OCR bounding boxes)                 │                        │
│       │                                ▼                        │
│       ▼                        Regex patterns ──────────────┐   │
│   For each (bbox, text, conf): │ aadhaar / pan / passport   │   │
│   → detect_pii(text)           │ phone / email / dob         │   │
│   → if PII: cv2.rectangle()    │ credit_card / pincode       │   │
│       │                        │ vehicle_reg                 │   │
│       ▼                        └─────────────────────────────┘   │
│   Masked JPEG + report                 │                        │
│                                        ▼                        │
│                                Keyword patterns                  │
│                                (whole-word \b boundary)          │
│                                name / address / dob / gender     │
└────────────────────────────────────────────────────────────────┘
```

### Request flow — image masking

```
Browser                     Vercel Function (upload.py)           OCR Engine
  │                                 │                                  │
  │── POST /api/upload ────────────>│                                  │
  │   (multipart/form-data)         │                                  │
  │                                 │── cgi.FieldStorage.parse ──>│   │
  │                                 │<── image bytes ─────────────│   │
  │                                 │                                  │
  │                                 │── cv2.imdecode() ────────────────│
  │                                 │── easyocr.readtext() ──────────>│
  │                                 │<── [(bbox, text, conf), ...] ───│
  │                                 │                                  │
  │                                 │── detect_pii(text) for each ─────│
  │                                 │   cv2.rectangle() on matches     │
  │                                 │── cv2.imencode() ────────────────│
  │                                 │                                  │
  │<── 200 JPEG binary ─────────────│                                  │
  │    X-PII-Report: [{...}]        │                                  │
  │    X-PII-Count: N               │                                  │
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
│                                   Endpoints: GET / · POST /upload/ · POST /mask-text/
│                                              GET /processed/{filename}
│
├── frontend/                       React 18 SPA
│   ├── package.json                Dependencies: react, react-dom, react-scripts
│   ├── .env.production             REACT_APP_API_URL=/api (relative, works on Vercel)
│   ├── .env.local.example          Template for local development
│   ├── public/
│   │   └── index.html              HTML shell with meta tags
│   └── src/
│       ├── index.js                ReactDOM.createRoot entry point
│       ├── index.css               Minimal reset (design tokens in App.css)
│       ├── App.js                  Main component — image upload + text masking
│       └── App.css                 Full design system (warm earthy palette,
│                                   Playfair Display + Source Sans 3, animations)
│
├── vercel.json                     Deployment routing: static build + serverless
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
# API running at http://localhost:8000

# 3. Frontend (new terminal)
cd ../frontend
cp .env.local.example .env.local
# Edit .env.local: REACT_APP_API_URL=http://localhost:8000
npm install
npm start
# App at http://localhost:3000
```

### Option B — Vercel dev (serverless locally)

```bash
npm install -g vercel
cd pii-masking-app
vercel dev
# Serves frontend + serverless functions together at http://localhost:3000
```

### Option C — Deploy to Vercel

```bash
vercel --prod
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full walkthrough.

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

**Error responses:**

| Code | Reason |
|---|---|
| 400 | No file field / empty file / not an image |
| 500 | OCR or image processing error |

---

### `POST /api/mask-text`

Mask PII in plain text; returns JSON.

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

Health check.

```json
{
  "message": "PII Masking API v2.0 is running",
  "version": "2.0.0",
  "endpoints": { ... }
}
```

---

## Running tests

```bash
cd backend
python test_pii_detection.py
```

Tests cover: Aadhaar, PAN, passport, phone, email, date, pincode, vehicle registration, keyword fields, and false-positive guards (`filename.jpg` must not trigger the `name` keyword).

---

## Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18, CSS3 | SPA with drag-and-drop, two-tab interface |
| Fonts | Playfair Display, Source Sans 3 | Warm serif + clean body pairing |
| API (serverless) | Python `http.server.BaseHTTPRequestHandler` | Vercel-compatible handlers |
| API (local) | FastAPI + Uvicorn | Full-featured local dev server |
| OCR | EasyOCR 1.7.2 | Text extraction from images |
| Image processing | OpenCV headless 4.8 | Decode, rectangle masking, re-encode |
| Pattern matching | Python `re` | Compiled regex for all PII types |
| Deployment | Vercel (static + serverless) | Frontend CDN + Python functions |

---

## Known limitations

- **Serverless ephemeral storage** — `/tmp` files are not shared between Vercel invocations. The `/api/processed` endpoint is for local use; in production the masked image is returned directly in the upload response body.
- **OCR accuracy** — EasyOCR performs well on printed text but may miss handwritten or heavily stylised fonts.
- **Large files** — Images over ~5 MB may hit Vercel's 10 MB request body limit. Compress before uploading.
- **Cold starts** — The first request after idle may take 10–30 seconds while EasyOCR loads its model weights (~50 MB).
