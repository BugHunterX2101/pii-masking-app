import requests
import json
import uuid

# Configuration - Change this to your local or deployed URL
BASE_URL = "http://localhost:7860"

def test_api():
    print("=== Phase 1 API Verification ===")
    
    # 1. Create a dummy API key (assuming you've manually added it to the DB, or we can use a known hash)
    # For a real test, you'd need an API key that exists in your database.
    # We will simulate this by demonstrating the exact payload required.
    
    api_key = "pk_test_12345"
    
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    # Test 1: Spanish PII Detection
    payload_es = {
        "text": "Mi nombre es Juan Carlos y mi correo es juan@empresa.es",
        "language": "es"
    }
    
    print(f"\n[Test 1] Testing Spanish NLP Detection (requires valid API key)...")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/mask-text", json=payload_es, headers=headers)
        if response.status_code == 401:
            print("Received 401 Unauthorized - This is EXPECTED if the test API key is not in your database!")
            print("To fully test, connect to your Postgres DB and insert an API key:")
            print("INSERT INTO api_keys (id, org_id, key_hash, is_active) VALUES ('pk_1', 1, '<sha256_of_your_key>', true);")
        else:
            print(f"Response ({response.status_code}):", json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error connecting to server: {e}. Ensure Docker container is running on port 7860.")

if __name__ == "__main__":
    test_api()
