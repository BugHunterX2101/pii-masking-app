"""
Serve processed (PII-masked) images.
Adds CORS headers and path traversal protection.
Note: In production (Vercel), /tmp files are ephemeral per invocation.
      This endpoint is mainly useful for local development.
      The primary flow returns the image directly from /api/upload.
"""
from http.server import BaseHTTPRequestHandler
import os
import mimetypes

PROCESSED_DIR = "/tmp/pii_processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)


def _cors(h):
    h.send_header('Access-Control-Allow-Origin', '*')
    h.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        _cors(self)
        self.end_headers()

    def do_GET(self):
        # Extract filename safely — prevent path traversal
        raw = self.path.split('?')[0]          # strip query string
        parts = [p for p in raw.split('/') if p]
        if len(parts) < 3:
            self._404()
            return

        # parts[-1] is the filename in /api/processed/<filename>
        filename = os.path.basename(parts[-1])  # path traversal guard
        if not filename:
            self._404()
            return

        file_path = os.path.join(PROCESSED_DIR, filename)

        if not os.path.isfile(file_path):
            self._404()
            return

        content_type, _ = mimetypes.guess_type(file_path)
        content_type = content_type or 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Disposition',
                             f'attachment; filename="{filename}"')
            _cors(self)
            self.end_headers()
            self.wfile.write(data)

        except OSError as exc:
            self._500(str(exc))

    def _404(self):
        self.send_response(404)
        _cors(self)
        self.end_headers()
        self.wfile.write(b'Not found')

    def _500(self, msg):
        self.send_response(500)
        _cors(self)
        self.end_headers()
        self.wfile.write(f'Error: {msg}'.encode())

    def log_message(self, fmt, *args):
        pass
