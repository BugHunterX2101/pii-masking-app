"""
Integration tests for the PII Masking API.

Run locally while the backend is running:
    # Option A — FastAPI (port 8000):
    cd backend && python run.py &
    python test_vercel_deployment.py --base-url http://localhost:8000

    # Option B — Vercel dev (port 3000):
    vercel dev &
    python test_vercel_deployment.py --base-url http://localhost:3000

    # Option C — Deployed to Vercel:
    python test_vercel_deployment.py --base-url https://your-app.vercel.app
"""
import sys
import os
import json
import argparse
import io

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def make_test_image() -> bytes:
    """Create a small synthetic image with PII-like text for testing."""
    if not HAS_PIL:
        # Return a minimal valid JPEG (1x1 white pixel)
        import base64
        TINY_JPEG = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
            b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
            b'\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1edL\t\xe0\x00\x01\x01'
            b'\x00\x00\x01\x00\x01\x00\x00\xff\xd9'
        )
        return TINY_JPEG

    img = Image.new('RGB', (400, 200), color='white')
    draw = ImageDraw.Draw(img)
    lines = [
        "Name: John Doe",
        "Aadhaar: 1234 5678 9012",
        "Phone: 9876543210",
        "Email: john.doe@example.com",
        "DOB: 01/01/1990",
    ]
    y = 20
    for line in lines:
        draw.text((20, y), line, fill='black')
        y += 30

    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


def test_health(base_url: str) -> bool:
    """GET /api — health check."""
    try:
        r = requests.get(f"{base_url}/api", timeout=15)
        ok = r.status_code == 200
        data = r.json()
        print(f"  ✓ Health check: {r.status_code} — {data.get('message', '')[:60]}")
        return ok
    except Exception as exc:
        print(f"  ✗ Health check failed: {exc}")
        return False


def test_mask_text(base_url: str) -> bool:
    """POST /api/mask-text — text PII masking."""
    payload = {
        "text": "My Aadhaar is 1234 5678 9012 and my email is test@example.com."
    }
    try:
        r = requests.post(
            f"{base_url}/api/mask-text",
            json=payload,
            timeout=15,
        )
        ok = r.status_code == 200
        data = r.json()
        print(f"  ✓ mask-text: {r.status_code} — pii_found={data.get('pii_found')} types={data.get('pii_types')}")
        if data.get('pii_found') and 'MASKED' in data.get('masked', ''):
            print("    Masking confirmed ✓")
        else:
            print(f"    WARNING: masking may not have applied — masked='{data.get('masked', '')[:60]}'")
            ok = False
        return ok
    except Exception as exc:
        print(f"  ✗ mask-text failed: {exc}")
        return False


def test_upload_image(base_url: str) -> bool:
    """POST /api/upload — image PII masking."""
    image_bytes = make_test_image()
    try:
        r = requests.post(
            f"{base_url}/api/upload",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            timeout=120,  # OCR can be slow on first request
        )
        ok = r.status_code == 200
        content_type = r.headers.get('Content-Type', '')
        is_image = content_type.startswith('image/')
        pii_count = r.headers.get('X-PII-Count', 'N/A')
        pii_report_raw = r.headers.get('X-PII-Report', '')

        print(f"  ✓ upload: {r.status_code} — content-type={content_type} size={len(r.content)} bytes")
        print(f"    X-PII-Count: {pii_count}")

        if pii_report_raw:
            try:
                report = json.loads(pii_report_raw)
                print(f"    X-PII-Report: {len(report)} item(s) detected")
                for item in report[:3]:
                    print(f"      - '{item.get('text', '')}' → {item.get('pii_types', [])}")
            except json.JSONDecodeError:
                print(f"    WARNING: X-PII-Report header could not be parsed as JSON")

        if not is_image:
            print(f"    WARNING: expected image response, got '{content_type}'")
            ok = False

        return ok
    except Exception as exc:
        print(f"  ✗ upload failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description='PII Masking API integration tests')
    parser.add_argument('--base-url', default='http://localhost:8000',
                        help='Base URL of the API (default: http://localhost:8000)')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    print(f"\nRunning integration tests against: {base}\n")
    print("=" * 50)

    results = {
        "health":     test_health(base),
        "mask-text":  test_mask_text(base),
        "upload":     test_upload_image(base),
    }

    print("\n" + "=" * 50)
    passed = sum(results.values())
    total = len(results)
    print(f"Results: {passed}/{total} passed\n")

    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
