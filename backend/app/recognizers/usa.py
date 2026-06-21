from presidio_analyzer import PatternRecognizer, Pattern

# SSN (Presidio already has this, but adding a specific one if needed. Presidio handles US_SSN natively)
# Routing Number (9 digits)
routing_pattern = Pattern(name="routing_pattern", regex=r'\b\d{9}\b', score=0.5)
routing_recognizer = PatternRecognizer(supported_entity="US_ROUTING_NUMBER", patterns=[routing_pattern])

RECOGNIZERS = [routing_recognizer]
