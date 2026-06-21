from presidio_analyzer import PatternRecognizer, Pattern

# IBAN (General European Bank Account)
iban_pattern = Pattern(name="iban_pattern", regex=r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b', score=0.85)
iban_recognizer = PatternRecognizer(supported_entity="EU_IBAN", patterns=[iban_pattern])

# EU VAT Number (Basic regex for general format)
vat_pattern = Pattern(name="vat_pattern", regex=r'\b[A-Z]{2}[A-Z0-9]{2,12}\b', score=0.5)
vat_recognizer = PatternRecognizer(supported_entity="EU_VAT", patterns=[vat_pattern])

RECOGNIZERS = [iban_recognizer, vat_recognizer]
