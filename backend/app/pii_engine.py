import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

# Lazy-loaded Presidio engines
_analyzer = None
_anonymizer = None

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
        
        # Add Custom Indian PII Recognizers
        aadhaar_pattern = Pattern(name="aadhaar_pattern", regex=r'\b\d{4}\s\d{4}\s\d{4}\b', score=0.85)
        aadhaar_recognizer = PatternRecognizer(supported_entity="AADHAAR", patterns=[aadhaar_pattern])
        _analyzer.registry.add_recognizer(aadhaar_recognizer)

        pan_pattern = Pattern(name="pan_pattern", regex=r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', score=0.85)
        pan_recognizer = PatternRecognizer(supported_entity="PAN_CARD", patterns=[pan_pattern])
        _analyzer.registry.add_recognizer(pan_recognizer)

        vehicle_pattern = Pattern(name="vehicle_pattern", regex=r'\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,2}\s?\d{4}\b', score=0.85)
        vehicle_recognizer = PatternRecognizer(supported_entity="VEHICLE_REG", patterns=[vehicle_pattern])
        _analyzer.registry.add_recognizer(vehicle_recognizer)
    return _analyzer

def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer

def detect_and_mask_text(text: str, active_entities: list[str]) -> dict:
    """
    Use Presidio to analyze and mask text based on active policies.
    active_entities is a list of entity strings allowed to be masked.
    e.g., ["PERSON", "EMAIL_ADDRESS", "AADHAAR"]
    """
    if not text.strip():
        return {"found": False, "types": [], "redacted": text}

    # If no entities are active, don't mask anything
    if not active_entities:
        return {"found": False, "types": [], "redacted": text}

    # Analyze
    results = _get_analyzer().analyze(text=text, entities=active_entities, language='en')
    
    if not results:
        return {"found": False, "types": [], "redacted": text}

    # Anonymize
    # By default, Presidio replaces with <ENTITY_TYPE>
    # We want [ENTITY_TYPE_MASKED]
    from presidio_anonymizer.entities import OperatorConfig
    operators = {}
    for ent in active_entities:
        operators[ent] = OperatorConfig("replace", {"new_value": f"[{ent}_MASKED]"})
        
    anonymized_result = _get_anonymizer().anonymize(
        text=text,
        analyzer_results=results,
        operators=operators
    )

    found_types = list(set([r.entity_type for r in results]))

    return {
        "found": len(found_types) > 0,
        "types": found_types,
        "redacted": anonymized_result.text
    }

def detect_raw(text: str, active_entities: list[str]):
    if not text.strip() or not active_entities:
        return []
    return _get_analyzer().analyze(text=text, entities=active_entities, language='en')

