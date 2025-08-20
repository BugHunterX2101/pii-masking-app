from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
from PIL import Image, ImageDraw
import easyocr
import cv2
import numpy as np
import re

app = FastAPI(title="PII Masking API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories for storing images
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
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

@app.get("/")
def read_root():
    return {"message": "PII Masking API is running"}

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    # Validate file is an image
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Process the image to mask PII
    try:
        masked_image_path = mask_pii(file_path)
        return {"filename": os.path.basename(masked_image_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.get("/processed/{filename}")
async def get_processed_image(filename: str):
    file_path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Processed image not found")
    return FileResponse(file_path)

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
    
    return output_path

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)