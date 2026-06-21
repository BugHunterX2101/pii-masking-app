from presidio_analyzer import PatternRecognizer, Pattern

# Aadhaar (12 digits, often with spaces)
aadhaar_pattern = Pattern(name="aadhaar_pattern", regex=r'\b\d{4}\s\d{4}\s\d{4}\b', score=0.85)
aadhaar_recognizer = PatternRecognizer(supported_entity="AADHAAR", patterns=[aadhaar_pattern])

# PAN (5 letters, 4 digits, 1 letter)
pan_pattern = Pattern(name="pan_pattern", regex=r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', score=0.85)
pan_recognizer = PatternRecognizer(supported_entity="PAN_CARD", patterns=[pan_pattern])

# Vehicle Registration (e.g. MH 12 AB 1234)
vehicle_pattern = Pattern(name="vehicle_pattern", regex=r'\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,2}\s?\d{4}\b', score=0.85)
vehicle_recognizer = PatternRecognizer(supported_entity="VEHICLE_REG", patterns=[vehicle_pattern])

RECOGNIZERS = [aadhaar_recognizer, pan_recognizer, vehicle_recognizer]
