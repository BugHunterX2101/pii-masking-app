import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from backend.app.recognizers import get_all_regional_recognizers
import langdetect

# Lazy-loaded Presidio engines
_analyzer = None
_anonymizer = None

# Languages supported based on requirements
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "ja", "zh"]

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_lg"},
                {"lang_code": "es", "model_name": "es_core_news_lg"},
                {"lang_code": "fr", "model_name": "fr_core_news_lg"},
                {"lang_code": "de", "model_name": "de_core_news_lg"},
                {"lang_code": "it", "model_name": "it_core_news_lg"},
                {"lang_code": "pt", "model_name": "pt_core_news_lg"},
                {"lang_code": "ja", "model_name": "ja_core_news_lg"},
                {"lang_code": "zh", "model_name": "zh_core_web_lg"},
            ],
        }
        try:
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=SUPPORTED_LANGUAGES)
        except Exception as e:
            # Fallback to default EN if custom models fail to load
            print(f"Failed to load multi-language models: {e}. Falling back to default.")
            _analyzer = AnalyzerEngine()
        
        # Add modular recognizers from all regions
        for recognizer in get_all_regional_recognizers():
            _analyzer.registry.add_recognizer(recognizer)

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

def _remove_overlaps(results):
    if not results: return []
    # Sort by start index, then descending end index (to keep the longest match if they start at the same place)
    sorted_results = sorted(results, key=lambda x: (x.start, -x.end))
    filtered = []
    last_end = -1
    for res in sorted_results:
        # If this result starts after the previous one ends, it's not an overlap
        if res.start >= last_end:
            filtered.append(res)
            last_end = max(last_end, res.end)
    return filtered

def detect_and_mask_text(text: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None, language: str = None) -> dict:
    """
    Use Presidio to analyze and mask text based on active policies and custom regex.
    """
    if not text.strip():
        return {"found": False, "types": [], "redacted": text}

    if not language:
        try:
            language = langdetect.detect(text)
            if language not in SUPPORTED_LANGUAGES:
                language = 'en'
        except:
            language = 'en'

    # Analyze
    results = _get_analyzer().analyze(text=text, entities=active_entities, language=language) if active_entities else []
    
    # Add custom regex results
    results.extend(_apply_custom_regex(text, custom_patterns))
    
    # CRITICAL FIX: Presidio Anonymizer crashes if there are overlapping entities
    results = _remove_overlaps(results)
    
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

def detect_raw(text: str, active_entities: list[str], custom_patterns: list = None, language: str = None):
    if not text.strip():
        return []
        
    if not language:
        try:
            language = langdetect.detect(text)
            if language not in SUPPORTED_LANGUAGES:
                language = 'en'
        except:
            language = 'en'
            
    results = _get_analyzer().analyze(text=text, entities=active_entities, language=language) if active_entities else []
    results.extend(_apply_custom_regex(text, custom_patterns))
    # Remove overlaps to prevent downstream processing errors
    return _remove_overlaps(results)

