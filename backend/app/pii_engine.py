import copy
import re
from typing import Optional
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern  # type: ignore
from presidio_anonymizer import AnonymizerEngine  # type: ignore
from backend.app.nlp_engine import LazySpacyNlpEngine
from backend.app.recognizers import get_all_regional_recognizers
import langdetect  # type: ignore

# Lazy-loaded Presidio engines
_analyzer = None
_anonymizer = None

# ---------------------------------------------------------------------------
# Multilingual NER with small, lazy-loaded models.
#
# Each language uses a spaCy `_sm` model (~10-15 MB) instead of the former
# `_lg` models (~500 MB each, all loaded eagerly at startup — several GB of
# downloads and RAM before the first request). The LazySpacyNlpEngine loads a
# model only for the language actually requested, so cold start is near
# instant and memory is bounded. Regex-backed PII (email, phone, Aadhaar,
# PAN, credit cards, ...) needs no NLP model at all.
# ---------------------------------------------------------------------------
SPACY_SM_MODELS = {
    "en": "en_core_web_sm",
    "es": "es_core_news_sm",
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "it": "it_core_news_sm",
    "pt": "pt_core_news_sm",
    "ja": "ja_core_news_sm",
    "zh": "zh_core_web_sm",
    "nl": "nl_core_news_sm",
    "pl": "pl_core_news_sm",
    "ru": "ru_core_news_sm",
    "uk": "uk_core_news_sm",
    "da": "da_core_news_sm",
    "nb": "nb_core_news_sm",
    "sv": "sv_core_news_sm",
    "fi": "fi_core_news_sm",
    "el": "el_core_news_sm",
    "ko": "ko_core_news_sm",
    "ca": "ca_core_news_sm",
    "ro": "ro_core_news_sm",
    "hr": "hr_core_news_sm",
    "lt": "lt_core_news_sm",
    "mk": "mk_core_news_sm",
    "sl": "sl_core_news_sm",
}

SUPPORTED_LANGUAGES = sorted(SPACY_SM_MODELS)

# langdetect returns some codes that differ from the spaCy model codes
_LANGUAGE_ALIASES = {
    "no": "nb",       # Norwegian (langdetect) -> Norwegian Bokmål (spaCy)
    "zh-cn": "zh",    # Simplified Chinese
    "zh-tw": "zh",    # Traditional Chinese
}

def resolve_language(text: str) -> str:
    """Public helper: detect the language of a text once (used by the document
    handlers so they do not re-run langdetect for every paragraph).
    """
    return _resolve_language(None, text)


def _resolve_language(language: Optional[str] = None, text: Optional[str] = None) -> str:
    """Return a supported language code, falling back to detection then English.

    The caller-supplied language must be one of SUPPORTED_LANGUAGES or Presidio
    raises on unsupported codes; clamping here prevents a 500 on bad input.
    """
    if language:
        mapped = _LANGUAGE_ALIASES.get(language, language)
        if mapped in SUPPORTED_LANGUAGES:
            return mapped
    if text and text.strip():
        try:
            detected = langdetect.detect(text)
            mapped = _LANGUAGE_ALIASES.get(detected, detected)
            if mapped in SUPPORTED_LANGUAGES:
                return mapped
        except Exception:
            pass
    return 'en'

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        models = [
            {"lang_code": lang, "model_name": model}
            for lang, model in SPACY_SM_MODELS.items()
        ]
        try:
            nlp_engine = LazySpacyNlpEngine(models=models)
            _analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=SUPPORTED_LANGUAGES,
            )
        except Exception as e:
            # Fallback to the default English engine if initialization fails
            print(f"Failed to initialize multi-language engine: {e}. Falling back to default.")
            _analyzer = AnalyzerEngine()

        # Add modular recognizers from all regions, registered for EVERY
        # supported language. The regional recognizers are pure regex
        # (language-independent), but Presidio filters recognizers by
        # `language == supported_language` at analyze time — a recognizer
        # registered only for "en" silently never fires when the detected
        # language is Spanish, French, German, etc. (a real bug we hit with
        # "CIF ESS92174218" resolving to Spanish). A deepcopy preserves each
        # recognizer's subclass and check-digit validator.
        for recognizer in get_all_regional_recognizers():
            for lang in SUPPORTED_LANGUAGES:
                clone = copy.deepcopy(recognizer)
                clone.supported_language = lang
                _analyzer.registry.add_recognizer(clone)

    return _analyzer

def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer

def _apply_custom_regex(text: str, custom_patterns: Optional[list] = None):
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
    """Resolve overlapping detections by keeping the strongest match.

    Two recognizers can flag the same span (e.g. the PAN regex recognizer and
    its checksum-validated twin, or a regional recognizer and Presidio's own).
    Sort by (start, -end, -score) so that for equal starts the longest,
    highest-confidence result wins, then greedily keep the best candidate per
    span. This is deterministic and mirrors Presidio's own score-based
    overlap handling.
    """
    if not results:
        return []
    sorted_results = sorted(results, key=lambda x: (x.start, -x.end, -x.score))
    filtered = []
    last_end = -1
    for res in sorted_results:
        if res.start >= last_end:
            filtered.append(res)
            last_end = res.end
        elif filtered and res.end > filtered[-1].end and res.score > filtered[-1].score:
            # The new match starts inside the previous one but extends past it
            # with a higher score — it is the better detection. Replace.
            filtered[-1] = res
            last_end = res.end
    return filtered

def detect_and_mask_text(text: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: Optional[list] = None, language: Optional[str] = None) -> dict:
    """
    Use Presidio to analyze and mask text based on active policies and custom regex.
    """
    if not text.strip():
        return {"found": False, "types": [], "matches": 0, "redacted": text}

    language = _resolve_language(language, text)

    # Analyze
    results = _get_analyzer().analyze(text=text, entities=active_entities, language=language) if active_entities else []
    
    # Add custom regex results
    results.extend(_apply_custom_regex(text, custom_patterns))
    
    # CRITICAL FIX: Presidio Anonymizer crashes if there are overlapping entities
    results = _remove_overlaps(results)
    
    if not results:
        return {"found": False, "types": [], "matches": 0, "redacted": text}

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
        "matches": len(results),
        "redacted": anonymized_result.text
    }

def detect_raw(text: str, active_entities: list[str], custom_patterns: Optional[list] = None, language: Optional[str] = None):
    if not text.strip():
        return []

    language = _resolve_language(language, text)

    results = _get_analyzer().analyze(text=text, entities=active_entities, language=language) if active_entities else []
    results.extend(_apply_custom_regex(text, custom_patterns))
    # Remove overlaps to prevent downstream processing errors
    return _remove_overlaps(results)

_faker_instances = {}

def _get_faker(language: str):
    from faker import Faker
    locale_map = {
        'en': 'en_US', 'es': 'es_ES', 'fr': 'fr_FR', 'de': 'de_DE',
        'it': 'it_IT', 'pt': 'pt_BR', 'ja': 'ja_JP', 'zh': 'zh_CN'
    }
    locale = locale_map.get(language, 'en_US')
    if locale not in _faker_instances:
        _faker_instances[locale] = Faker(locale)
    return _faker_instances[locale]

def detect_and_synthesize_text(text: str, active_entities: list[str], custom_patterns: Optional[list] = None, language: Optional[str] = None) -> dict:
    """
    Analyzes text and replaces PII with statistically realistic synthetic data using Faker.
    Used for AI Training Data Sanitization to preserve utility.
    """
    if not text.strip():
        return {"found": False, "types": [], "matches": 0, "redacted": text}

    language = _resolve_language(language, text)

    results = _get_analyzer().analyze(text=text, entities=active_entities, language=language) if active_entities else []
    results.extend(_apply_custom_regex(text, custom_patterns))
    results = _remove_overlaps(results)
    
    if not results:
        return {"found": False, "types": [], "matches": 0, "redacted": text}

    all_entity_types = set([r.entity_type for r in results])
    fake = _get_faker(language)
    
    def generate_fake(entity_type):
        if entity_type == "PERSON": return fake.name()
        if entity_type == "EMAIL_ADDRESS": return fake.email()
        if entity_type == "PHONE_NUMBER": return fake.phone_number()
        if entity_type == "CREDIT_CARD": return fake.credit_card_number()
        if entity_type in ["IBAN", "IBAN_CODE"]: return fake.iban()
        if entity_type in ["US_SSN"]: return fake.ssn()
        if entity_type in ["LOCATION", "ADDRESS"]: return fake.address().replace('\n', ', ')
        if entity_type == "DATE_TIME": return str(fake.date())
        # Healthcare fallback
        if entity_type == "PROVIDER_NPI": return str(fake.random_number(digits=10, fix_len=True))
        if entity_type == "MEDICAL_RECORD_NUMBER": return fake.bothify(text='MRN-####-????').upper()
        if entity_type == "HEALTH_PLAN_ID": return fake.bothify(text='HPI-######')
        if entity_type == "ICD10_CODE": return fake.bothify(text='?##.#').upper()
        return f"[{entity_type}_SYNTHETIC]"

    # Replace from back to front to avoid index shifting
    redacted = text
    results.sort(key=lambda x: x.start, reverse=True)
    
    for res in results:
        fake_val = generate_fake(res.entity_type)
        redacted = redacted[:res.start] + fake_val + redacted[res.end:]

    return {
        "found": True,
        "types": list(all_entity_types),
        "matches": len(results),
        "redacted": redacted
    }

