from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
from PIL import Image, ImageDraw
import easyocr
import cv2
import numpy as np
import re
from http.server import BaseHTTPRequestHandler
from io import BytesIO
import json

# Create directories for storing images
UPLOAD_DIR = "/tmp/uploads"
PROCESSED_DIR = "/tmp/processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Initialize OCR reader
reader = easyocr.Reader(['en'])

# PII detection patterns
PII_PATTERNS = {
    'aadhaar': r'\d{4}\s\d{4}\s\d{4}',  # Aadhaar number pattern (e.g., 1234 5678 9012)
    'phone': r'\+?\d{10,12}',  # Phone number pattern
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email pattern
    'date': r'\d{2}[/.-]\d{2}[/.-]\d{2,4}',  # Date pattern (DD/MM/YYYY or similar)
}

# Keywords that might indicate PII
NAME_KEYWORDS = ['name', 'naam']
ADDRESS_KEYWORDS = ['address', 'addr', 'residence', 'pata']
DOB_KEYWORDS = ['birth', 'dob', 'born', 'janm']

def is_pii(text):
    """Check if the text contains PII based on patterns and keywords"""
    text = text.lower()
    
    # Check for Aadhaar number, phone, email, and date patterns
    for pattern in PII_PATTERNS.values():
        if re.search(pattern, text):
            return True
    
    # Check for name indicators
    for keyword in NAME_KEYWORDS:
        if keyword in text:
            return True
    
    # Check for address indicators
    for keyword in ADDRESS_KEYWORDS:
        if keyword in text:
            return True
    
    # Check for DOB indicators
    for keyword in DOB_KEYWORDS:
        if keyword in text:
            return True
    
    # Additional heuristics can be added here
    
    return False

def mask_pii(image_path):
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        raise Exception("Could not read the image")
    
    # Convert to RGB for EasyOCR
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Perform OCR to extract text and bounding boxes
    results = reader.readtext(rgb_img)
    
    # Create a copy for masking
    masked_img = img.copy()
    
    # Process each detected text region
    for (bbox, text, prob) in results:
        # Check if the text contains PII
        if is_pii(text):
            # Convert bbox to the format required by cv2.rectangle
            # bbox is a list of 4 points (top-left, top-right, bottom-right, bottom-left)
            # We need top-left and bottom-right points for cv2.rectangle
            top_left = tuple(map(int, bbox[0]))
            bottom_right = tuple(map(int, bbox[2]))
            
            # Draw a black rectangle to mask the PII
            cv2.rectangle(masked_img, top_left, bottom_right, (0, 0, 0), -1)
    
    # Save the masked image
    output_filename = f"masked_{os.path.basename(image_path)}"
    output_path = os.path.join(PROCESSED_DIR, output_filename)
    cv2.imwrite(output_path, masked_img)
    
    return output_path, output_filename

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Check if the path is correct
        if self.path != '/api/upload/':
            self.send_response(404)
            self.end_headers()
            return

        # Get content length
        content_length = int(self.headers['Content-Length'])
        
        # Get boundary from Content-Type
        content_type = self.headers['Content-Type']
        boundary = content_type.split('=')[1].encode()
        
        # Read the form data
        form_data = self.rfile.read(content_length)
        
        # Parse the form data to get the file
        file_data = None
        file_name = None
        
        # Simple multipart form parsing
        form_parts = form_data.split(boundary)
        for part in form_parts:
            if b'filename=' in part:
                # Extract filename
                header_end = part.find(b'\r\n\r\n')
                if header_end > 0:
                    header = part[:header_end].decode('utf-8', 'ignore')
                    filename_match = re.search(r'filename="(.+?)"', header)
                    if filename_match:
                        file_name = filename_match.group(1)
                    
                    # Extract file data
                    file_data = part[header_end+4:]
                    # Remove trailing boundary marker if present
                    if file_data.endswith(b'--\r\n'):
                        file_data = file_data[:-4]
                    elif file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
        
        if not file_data or not file_name:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'No file uploaded')
            return
        
        try:
            # Generate unique filename
            file_extension = os.path.splitext(file_name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            # Save uploaded file
            with open(file_path, "wb") as buffer:
                buffer.write(file_data)
            
            # Process the image to mask PII
            masked_image_path, output_filename = mask_pii(file_path)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = json.dumps({"filename": output_filename})
            self.wfile.write(response.encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            error_message = json.dumps({"detail": f"Error processing image: {str(e)}"})
            self.wfile.write(error_message.encode())