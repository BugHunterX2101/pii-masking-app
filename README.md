# PII Masking Application

This application automatically detects and masks Personally Identifiable Information (PII) from images such as Aadhaar cards or similar ID documents. It uses OCR to extract text from images and then applies masking to sensitive information.

## Deployment on Vercel

This application is configured for easy deployment on Vercel. Follow these steps to deploy:

1. Push your code to a GitHub repository
2. Connect your repository to Vercel
3. Vercel will automatically detect the configuration and deploy both the frontend and backend

The application uses Vercel's serverless functions for the backend API and static site hosting for the React frontend.

## Features

- Upload images containing PII
- Automatic detection of sensitive information such as:
  - Full Name
  - Address
  - Date of Birth
  - Aadhaar Number
  - Phone Number
  - Email Address
- Masking of detected PII in the image
- User-friendly interface for uploading and viewing results

## Technology Stack

### Backend
- Python with FastAPI
- EasyOCR for text extraction
- OpenCV for image processing
- Regular expressions for PII detection

### Frontend
- React.js
- Axios for API communication

## Project Structure

```
project/
├── backend/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   └── run.py
└── frontend/
    ├── public/
    │   └── index.html
    ├── src/
    │   ├── App.js
    │   ├── App.css
    │   ├── index.js
    │   └── index.css
    └── package.json
```

## Setup and Running

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the FastAPI server:
   ```
   python run.py
   ```
   The server will start at http://localhost:8000

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install the required dependencies:
   ```
   npm install
   ```

3. Start the React development server:
   ```
   npm start
   ```
   The application will be available at http://localhost:3000

## Usage

1. Open the application in your browser at http://localhost:3000
2. Click on "Choose Image" to select an image containing PII
3. Click on "Process Image" to upload and process the image
4. View the original and processed images side by side

## Implementation Details

### PII Detection

The application uses a combination of techniques to detect PII:

1. Regular expressions for structured data like Aadhaar numbers, phone numbers, and email addresses
2. Keyword-based detection for names, addresses, and dates of birth
3. OCR to extract text from images

### Image Masking

When PII is detected, the application masks it by drawing black rectangles over the sensitive information in the image.