"""
PII Masking API - Image upload and processing endpoint
Fixed issues:
  - Lazy OCR reader initialization (no module-level crash)
  - Returns image binary directly instead of a filename
  - Robust multipart parsing
  - Improved PII patterns (fewer false positives)
  - Detection report included in response headers
  - Added PAN card, passport, credit card patterns
"""
from http.server import BaseHTTPRequestHandler
import os
import uuid
import re
import json
import mimetypes
import cgi
import io

UPLOAD_DIR = "/tmp/pii_uploads"
PROCESSED_DIR = "/tmp/pii_processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# -------------------------------------------------------------------
# PII detection patterns — compiled once
# -------------------------------------------------------------------
PII_PATTERNS = {
    "aadhaar":      re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'),
    "pan_card":     re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
    "passport":     re.compile(r'\b[A-Z][0-9]{7}\b'),
    "phone":        re.compile(r'(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)'),
    "email":        re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'),
    "date_of_birth": re.compile(r'\b\d{2}[/\-\.]\d{2}[/\-\.]\d{4}\b'),
    "credit_card":  re.compile(r'\b(?:\d[ \-]?){13,16}\b'),
    "pincode":      re.compile(r'\b[1-9]\d{5}\b'),
    "vehicle_reg":  re.compile(r'\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,2}\s?\d{4}\b'),
}

# Keyword-based detection (whole-word matching to avoid 'filename' false positives)
KEYWORD_GROUPS = {
    "name_field":    re.compile(r'\b(name|naam|full name)\b', re.I),
    "address_field": re.compile(r'\b(address|addr|residence|pata|locality)\b', re.I),
    "dob_field":     re.compile(r'\b(date of birth|dob|born|janm|d\.o\.b)\b', re.I),
    "gender_field":  re.compile(r'\b(male|female|gender|sex)\b', re.I),
}


def detect_pii(text: str) -> dict:
    """
    Returns dict with keys: found (bool), types (list), redacted (str)
    Redacted text has PII replaced with [TYPE_MASKED] tokens.
    """
    found_types = []
    redacted = text

    for name, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            found_types.append(name)
            redacted = pattern.sub(f"[{name.upper()}_MASKED]", redacted)

    for name, pattern in KEYWORD_GROUPS.items():
        if pattern.search(text):
            if name not in found_types:
                found_types.append(name)

    return {
        "found": len(found_types) > 0,
        "types": found_types,
        "redacted": redacted,
    }


def mask_pii_in_image(image_bytes: bytes):
    """
    OCR → detect PII → draw black rectangles.
    Returns (masked_image_bytes, detection_report).
    Heavy imports are inside the function to avoid Vercel cold-start crashes.
    """
    import cv2
    import numpy as np
    import easyocr

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Ensure the file is a valid image.")

    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Lazy-load OCR (cached at process level for reuse within the same invocation)
    if not hasattr(mask_pii_in_image, "_reader"):
        mask_pii_in_image._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    reader = mask_pii_in_image._reader

    results = reader.readtext(rgb_img)
    masked = img.copy()
    report = []

    for (bbox, text, confidence) in results:
        detection = detect_pii(text)
        if detection["found"]:
            top_left = tuple(map(int, bbox[0]))
            bottom_right = tuple(map(int, bbox[2]))
            # Black fill rectangle
            cv2.rectangle(masked, top_left, bottom_right, (0, 0, 0), -1)
            report.append({
                "original_text": text,
                "pii_types": detection["types"],
                "confidence": round(float(confidence), 3),
                "bbox": [list(map(int, p)) for p in bbox],
            })

    # Encode result back to JPEG
    success, buffer = cv2.imencode('.jpg', masked, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise ValueError("Failed to encode processed image.")

    return buffer.tobytes(), report


def mask_pii_in_text(text: str) -> dict:
    """Mask PII in plain text and return structured result."""
    result = detect_pii(text)
    return {
        "original": text,
        "masked": result["redacted"],
        "pii_found": result["found"],
        "pii_types": result["types"],
        "count": len(result["types"]),
    }


# -------------------------------------------------------------------
# CORS helper
# -------------------------------------------------------------------
def _cors_headers(handler_instance):
    handler_instance.send_header('Access-Control-Allow-Origin', '*')
    handler_instance.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler_instance.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        _cors_headers(self)
        self.end_headers()

    def do_POST(self):
        # Route: /api/mask-text
        if 'mask-text' in self.path or 'mask_text' in self.path:
            self._handle_text_masking()
            return
        # Route: /api/upload (default)
        self._handle_image_upload()

    def _handle_text_masking(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode('utf-8'))
            text = body.get('text', '')

            if not text.strip():
                self._json_error(400, "Field 'text' is required.")
                return

            result = mask_pii_in_text(text)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            _cors_headers(self)
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as exc:
            self._json_error(500, str(exc))

    def _handle_image_upload(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))

            # Use cgi.FieldStorage for robust multipart parsing
            env = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': str(content_length),
            }
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ=env,
            )

            if 'file' not in form:
                self._json_error(400, "No file field in request. Use field name 'file'.")
                return

            file_item = form['file']
            image_bytes = file_item.file.read()

            if not image_bytes:
                self._json_error(400, "Uploaded file is empty.")
                return

            # Process
            masked_bytes, report = mask_pii_in_image(image_bytes)

            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(masked_bytes)))
            self.send_header('X-PII-Report', json.dumps(report))
            self.send_header('X-PII-Count', str(len(report)))
            _cors_headers(self)
            self.end_headers()
            self.wfile.write(masked_bytes)

        except Exception as exc:
            self._json_error(500, f"Processing error: {str(exc)}")

    def _json_error(self, code: int, detail: str):
        body = json.dumps({"error": detail}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Suppress default request logging
