import os
import requests
import json

# Configuration — override with environment variables
BASE_URL = os.getenv("PII_APP_URL", "https://vedit2101-pii-masking-app.hf.space")
API_KEY = os.getenv("PII_APP_API_KEY", "pk_test_12345")


def test_api():
    print(f"=== Phase 1 API Verification against {BASE_URL} ===")

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    # Test 1: Spanish PII Detection
    payload_es = {
        "text": "Mi nombre es Juan Carlos y mi correo es juan@empresa.es",
        "language": "es"
    }

    print("\n[Test 1] Testing Spanish NLP Detection...")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/mask-text", json=payload_es, headers=headers)
        if response.status_code == 401:
            print("Received 401 Unauthorized — expected if the test API key is not in the database.")
            print("Create a key via the Admin dashboard (API Keys card), then re-run with:")
            print("  PII_APP_API_KEY=<your-key> python test_phase1_api.py")
        else:
            print(f"Response ({response.status_code}):", json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error connecting to server: {e}. Ensure the app is running.")


if __name__ == "__main__":
    test_api()
