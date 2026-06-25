"""
Test suite for PII detection — updated for v2 patterns
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import pii_engine

TEST_CASES = [
    # Aadhaar
    ("1234 5678 9012",           True,  ["aadhaar"]),
    # PAN card
    ("ABCDE1234F",               True,  ["pan_card"]),
    # Passport
    ("A1234567",                 True,  ["passport"]),
    # Indian phone
    ("9876543210",               True,  ["phone"]),
    ("+91 9876543210",           True,  ["phone"]),
    # Email
    ("user@example.com",         True,  ["email"]),
    # Date of birth
    ("01/01/1990",               True,  ["date_of_birth"]),
    ("31-12-2000",               True,  ["date_of_birth"]),
    # Name keyword (whole word)
    ("Name: John Doe",           True,  ["name_field"]),
    # Address keyword
    ("Address: 123 Main St",     True,  ["address_field"]),
    # DOB keyword
    ("Date of Birth: 01/01/1990", True, ["dob_field", "date_of_birth"]),
    # 'name' must NOT match inside 'filename'
    ("filename.jpg",             False, []),
    # Non-PII
    ("This is a regular text",   False, []),
    ("Hello world",              False, []),
    ("12345",                    False, []),  # too short for Aadhaar/phone
    # Pincode
    ("400001",                   True,  ["pincode"]),
    # Vehicle
    ("MH 12 AB 1234",            True,  ["vehicle_reg"]),
]

def run_tests():
    passed = failed = 0
    header = f"\n{'Text':<35} | {'Expected':<8} | {'Got':<8} | {'Status':<6}"
    print(header)
    print("-" * len(header))

    for text, expected_found, expected_types in TEST_CASES:
        results = pii_engine.detect_raw(text, active_entities=expected_types if expected_types else ["email", "phone", "aadhaar", "pan_card", "passport", "date_of_birth", "name_field", "address_field", "dob_field", "pincode", "vehicle_reg"])
        
        got_found = len(results) > 0
        got_types = [res.entity_type for res in results]
        
        ok = (got_found == expected_found)
        if expected_types:
            # We match if any of the expected types are in the detected types
            ok = ok and all(t.upper() in [gt.upper() for gt in got_types] for t in expected_types)

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  !! Expected types: {expected_types}, Got: {got_types}")

        print(f"{text[:35]:<35} | {str(expected_found):<8} | {str(got_found):<8} | {status:<6}")

    print("-" * len(header))
    total = passed + failed
    print(f"\nPassed: {passed}/{total}  |  Failed: {failed}/{total}")
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
