from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import re
import cv2
from typing import Optional
from pydantic import BaseModel

app = FastAPI(title="PII Masking API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# -------------------------------------------------------------------
# PII patterns — fixed false positives, added new document types
# -------------------------------------------------------------------
PII_PATTERNS = {
    "aadhaar":       re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'),
    "pan_card":      re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
    "passport":      re.compile(r'\b[A-Z][0-9]{7}\b'),
    "phone":         re.compile(r'(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)'),
    "email":         re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'),
    "date_of_birth": re.compile(r'\b\d{2}[/\-\.]\d{2}[/\-\.]\d{4}\b'),
    "credit_card":   re.compile(r'\b(?:\d[ \-]?){13,16}\b'),
    "pincode":       re.compile(r'\b[1-9]\d{5}\b'),
    "vehicle_reg":   re.compile(r'\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,2}\s?\d{4}\b'),
}

KEYWORD_GROUPS = {
    "name_field":    re.compile(r'\b(name|naam|full name)\b', re.I),
    "address_field": re.compile(r'\b(address|addr|residence|pata|locality)\b', re.I),
    "dob_field":     re.compile(r'\b(date of birth|dob|born|janm|d\.o\.b)\b', re.I),
    "gender_field":  re.compile(r'\b(male|female|gender|sex)\b', re.I),
}

# Lazy OCR reader — loaded on first image request, not at import time
_ocr_reader = None

def get_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader


def detect_pii(text: str) -> dict:
    found_types = []
    redacted = text
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            found_types.append(name)
            redacted = pattern.sub(f"[{name.upper()}_MASKED]", redacted)
    for name, pattern in KEYWORD_GROUPS.items():
        if pattern.search(text) and name not in found_types:
            found_types.append(name)
    return {"found": bool(found_types), "types": found_types, "redacted": redacted}


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "message": "PII Masking API v2.0 is running",
        "endpoints": {
            "POST /upload/": "Upload image for PII masking",
            "POST /mask-text/": "Mask PII in plain text",
            "GET /processed/{filename}": "Download processed image",
        }
    }


@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG, PNG, etc.)")

    ext = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        masked_path, report = mask_pii(file_path)
        return JSONResponse({
            "filename": os.path.basename(masked_path),
            "pii_detected": len(report),
            "report": report,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(exc)}")


class TextMaskRequest(BaseModel):
    text: str
    highlight: Optional[bool] = False


@app.post("/mask-text/")
async def mask_text(req: TextMaskRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' field is required.")
    result = detect_pii(req.text)
    return {
        "original": req.text,
        "masked": result["redacted"],
        "pii_found": result["found"],
        "pii_types": result["types"],
        "count": len(result["types"]),
    }


@app.get("/processed/{filename}")
async def get_processed_image(filename: str):
    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    file_path = os.path.join(PROCESSED_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Processed image not found")
    return FileResponse(file_path, media_type="image/jpeg",
                        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})


def mask_pii(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not decode image")

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    reader = get_reader()
    results = reader.readtext(rgb)

    masked = img.copy()
    report = []

    for (bbox, text, conf) in results:
        detection = detect_pii(text)
        if detection["found"]:
            tl = tuple(map(int, bbox[0]))
            br = tuple(map(int, bbox[2]))
            cv2.rectangle(masked, tl, br, (0, 0, 0), -1)
            report.append({
                "text": text,
                "pii_types": detection["types"],
                "confidence": round(float(conf), 3),
            })

    out_name = f"masked_{os.path.basename(image_path)}"
    out_path = os.path.join(PROCESSED_DIR, out_name)
    cv2.imwrite(out_path, masked)
    return out_path, report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
