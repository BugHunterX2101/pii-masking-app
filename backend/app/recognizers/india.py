from presidio_analyzer import PatternRecognizer, Pattern  # type: ignore
from backend.app.checksums import is_valid_aadhaar, is_valid_pan
from backend.app.recognizers import ValidatedPatternRecognizer

# Aadhaar (12 digits, often with spaces) — Verhoeff check digit verified.
aadhaar_pattern = Pattern(name="aadhaar_pattern", regex=r'\b\d{4}\s\d{4}\s\d{4}\b', score=0.85)
aadhaar_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_aadhaar,
    supported_entity="AADHAAR",
    patterns=[aadhaar_pattern],
)

# PAN (5 letters, 4 digits, 1 letter). The government has never published the
# PAN checksum, so we keep TWO recognizers:
#   - a plain regex recognizer (recall — anything that looks like a PAN is
#     flagged, a DLP tool must err toward flagging);
#   - a checksum-validated recognizer (precision — a PAN whose mod-36 checksum
#     verifies is promoted to full confidence).
pan_pattern = Pattern(name="pan_pattern", regex=r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', score=0.85)
pan_recognizer = PatternRecognizer(supported_entity="PAN_CARD", patterns=[pan_pattern])
pan_checksum_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_pan,
    supported_entity="PAN_CARD",
    patterns=[pan_pattern],
)

# Vehicle Registration (e.g. MH 12 AB 1234)
vehicle_pattern = Pattern(name="vehicle_pattern", regex=r'\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,2}\s?\d{4}\b', score=0.85)
vehicle_recognizer = PatternRecognizer(supported_entity="VEHICLE_REG", patterns=[vehicle_pattern])

RECOGNIZERS = [aadhaar_recognizer, pan_recognizer, pan_checksum_recognizer, vehicle_recognizer]
