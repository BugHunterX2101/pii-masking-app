from presidio_analyzer import PatternRecognizer, Pattern  # type: ignore
from backend.app.checksums import is_valid_routing_number
from backend.app.recognizers import ValidatedPatternRecognizer

# Routing Number (9 digits) — official ABA mod-10 (3-7-1 weights) check digit.
routing_pattern = Pattern(name="routing_pattern", regex=r'\b\d{9}\b', score=0.5)
routing_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_routing_number,
    supported_entity="US_ROUTING_NUMBER",
    patterns=[routing_pattern],
)

RECOGNIZERS = [routing_recognizer]
