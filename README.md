# PII Masking Application

This application automatically detects and masks Personally Identifiable Information (PII) from images such as Aadhaar cards or similar ID documents. It uses OCR to extract text from images and then applies masking to sensitive information.

## Deployment on Vercel

This application is configured for easy deployment on Vercel. Follow these steps to deploy:

1.  Push your code to a GitHub repository.
2.  Connect your repository to Vercel.
3.  Vercel will automatically detect the configuration and deploy both the frontend and backend.

The application uses Vercel's serverless functions for the backend API and static site hosting for the React frontend.

## Features

-   Upload images containing PII
-   Automatic detection of sensitive information such as:
    -   Full Name
    -   Address
    -   Date of Birth
    -   Aadhaar Number
    -   Phone Number
    -   Email Address
-   Masking of detected PII in the image
-   User-friendly interface for uploading and viewing results

## Technology Stack

### Backend

-   Python with FastAPI
-   EasyOCR for text extraction
-   OpenCV for image processing
-   Regular expressions for PII detection

### Frontend

-   React.js
-   Axios for API communication

## Project Structure (Vercel-Compliant)
