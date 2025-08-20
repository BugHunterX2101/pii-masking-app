import requests
import os
import json

def test_api_health():
    """Test the API health endpoint"""
    try:
        # For local testing
        response = requests.get("http://localhost:3000/api")
        print(f"Local API health check: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Local API health check failed: {str(e)}")

def test_upload_endpoint():
    """Test the upload endpoint with a sample image"""
    # Path to a sample image for testing
    sample_image_path = os.path.join(os.path.dirname(__file__), "sample_image.jpg")
    
    # Check if sample image exists
    if not os.path.exists(sample_image_path):
        print(f"Sample image not found at {sample_image_path}")
        print("Please create a sample image for testing")
        return
    
    try:
        # For local testing
        with open(sample_image_path, "rb") as img_file:
            files = {"file": ("sample_image.jpg", img_file, "image/jpeg")}
            response = requests.post("http://localhost:3000/api/upload", files=files)
        
        print(f"Local upload endpoint test: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Local upload endpoint test failed: {str(e)}")

if __name__ == "__main__":
    print("Testing Vercel deployment configuration locally...")
    test_api_health()
    test_upload_endpoint()
    print("\nNote: These tests are for local verification only.")
    print("After deploying to Vercel, update the URLs to test the deployed application.")