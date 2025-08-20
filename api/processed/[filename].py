from http.server import BaseHTTPRequestHandler
import os
import mimetypes

# Directory for processed images
PROCESSED_DIR = "/tmp/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Extract filename from path
        path_parts = self.path.split('/')
        if len(path_parts) < 4:
            self.send_response(404)
            self.end_headers()
            return
        
        filename = path_parts[3]  # /api/processed/[filename]
        file_path = os.path.join(PROCESSED_DIR, filename)
        
        if not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'File not found')
            return
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Send the file
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-length', str(len(file_data)))
            self.end_headers()
            
            self.wfile.write(file_data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f'Error serving file: {str(e)}'.encode())