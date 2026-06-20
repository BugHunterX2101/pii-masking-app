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

def _apply_custom_regex(text: str, custom_patterns: list):
    import re
    from presidio_analyzer import RecognizerResult
    results = []
    if not custom_patterns: return results
    for pattern_dict in custom_patterns:
        try:
            for match in re.finditer(pattern_dict['pattern'], text):
                results.append(RecognizerResult(entity_type=pattern_dict['name'], start=match.start(), end=match.end(), score=1.0))
        except re.error:
            pass # Ignore invalid regex
    return results

def detect_and_mask_text(text: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None) -> dict:
    """
    Use Presidio to analyze and mask text based on active policies and custom regex.
    """
    if not text.strip():
        return {"found": False, "types": [], "redacted": text}

    # Analyze
    results = _get_analyzer().analyze(text=text, entities=active_entities, language='en') if active_entities else []
    
    # Add custom regex results
    results.extend(_apply_custom_regex(text, custom_patterns))
    
    if not results:
        return {"found": False, "types": [], "redacted": text}

    # Anonymize
    from presidio_anonymizer.entities import OperatorConfig
    operators = {}
    
    all_entity_types = set([r.entity_type for r in results])
    
    for ent in all_entity_types:
        if masking_style == "BLACKOUT":
            operators[ent] = OperatorConfig("replace", {"new_value": "████████"})
        elif masking_style == "ASTERISK":
            operators[ent] = OperatorConfig("replace", {"new_value": "***"})
        else: # LABEL
            operators[ent] = OperatorConfig("replace", {"new_value": f"[{ent}_MASKED]"})
        
    anonymized_result = _get_anonymizer().anonymize(
        text=text,
        analyzer_results=results,
        operators=operators
    )

    return {
        "found": True,
        "types": list(all_entity_types),
        "redacted": anonymized_result.text
    }

def detect_raw(text: str, active_entities: list[str], custom_patterns: list = None):
    if not text.strip():
        return []
    results = _get_analyzer().analyze(text=text, entities=active_entities, language='en') if active_entities else []
    results.extend(_apply_custom_regex(text, custom_patterns))
    return results

