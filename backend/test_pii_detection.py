import os
import sys
import cv2
import numpy as np
from app.main import is_pii, reader

def test_pii_detection():
    # Test cases for PII detection
    test_cases = [
        # Aadhaar number format
        ("1234 5678 9012", True),
        # Phone number
        ("+91 9876543210", True),
        # Email address
        ("user@example.com", True),
        # Date format
        ("01/01/1990", True),
        # Name indicator
        ("Name: John Doe", True),
        # Address indicator
        ("Address: 123 Main St", True),
        # DOB indicator
        ("Date of Birth: 01/01/1990", True),
        # Non-PII text
        ("This is a regular text", False),
        ("Hello world", False),
        ("12345", False),  # Just a number, not in Aadhaar format
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    print("\nTesting PII detection function...\n")
    print("-" * 50)
    print(f"{'Text':<30} | {'Expected':<10} | {'Result':<10} | {'Status':<10}")
    print("-" * 50)
    
    for text, expected in test_cases:
        result = is_pii(text)
        status = "PASS" if result == expected else "FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            
        print(f"{text[:30]:<30} | {str(expected):<10} | {str(result):<10} | {status:<10}")
    
    print("-" * 50)
    print(f"Tests passed: {passed}/{len(test_cases)} ({passed/len(test_cases)*100:.1f}%)")
    print(f"Tests failed: {failed}/{len(test_cases)} ({failed/len(test_cases)*100:.1f}%)")
    print("-" * 50)
    
    return passed == len(test_cases)

if __name__ == "__main__":
    # Create directories if they don't exist
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("processed", exist_ok=True)
    
    # Run the tests
    success = test_pii_detection()
    
    if success:
        print("\nAll PII detection tests passed!")
        sys.exit(0)
    else:
        print("\nSome PII detection tests failed.")
        sys.exit(1)