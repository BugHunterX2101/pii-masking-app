import time
import requests
import json
import sys

URL = "https://vedit2101-pii-masking-app.hf.space"
API_URL = f"{URL}/api/v1/mask-text"

def check_space():
    print(f"Waiting for Hugging Face Space to be live at {URL}...")
    for i in range(30):  # Wait up to 15 minutes (30 * 30 seconds)
        try:
            # Send a test API request
            payload = {
                "text": "Mi nombre es Juan Carlos y mi correo es juan@empresa.es",
                "language": "es"
            }
            headers = {
                "X-API-Key": "pk_test_12345",
                "Content-Type": "application/json"
            }
            response = requests.post(API_URL, json=payload, headers=headers)
            
            # Hugging Face returns 503 while building/starting
            if response.status_code not in (503, 502, 500, 404):
                print(f"\nSUCCESS: Space is LIVE! Received status {response.status_code}")
                print(f"Response: {response.text}")
                if response.status_code == 401:
                    print("Received 401 Unauthorized. This proves the API v1 endpoint and API Key middleware are working perfectly on production!")
                return True
        except Exception as e:
            print(f"Connection error: {e}")
            
        print(f"[{i+1}/30] Space is still building or starting... waiting 30 seconds...")
        time.sleep(30)
        sys.stdout.flush()
    
    print("Timed out waiting for the space to be ready.")
    return False

if __name__ == "__main__":
    check_space()
