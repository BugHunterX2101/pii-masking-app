from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self._cors()
        self.end_headers()
        response = json.dumps({
            "message": "PII Masking API is running",
            "version": "2.0.0",
            "endpoints": {
                "POST /api/upload": "Upload an image for PII masking",
                "POST /api/mask-text": "Mask PII in plain text",
                "GET /api/processed/{filename}": "Retrieve a processed image"
            }
        })
        self.wfile.write(response.encode())
