import importlib

from presidio_analyzer import PatternRecognizer  # type: ignore


class ValidatedPatternRecognizer(PatternRecognizer):
    """PatternRecognizer backed by a check-digit predicate.

    Presidio's PatternRecognizer exposes a `validate_result` hook: returning
    True promotes the match to full confidence (1.0) and returning False drops
    it (0.0). Subclassing is the only supported way to supply that hook, so
    this class turns a plain callable into it — e.g. is_valid_cpf wired onto
    the CPF regex turns noisy pattern matches into verified identifiers.

    An optional `span_adjuster` callable solves the "regex match is wider than
    the verified identifier" problem: when a pattern greedily swallows a
    trailing token (the spaced VAT form can absorb a following word), the
    validator accepts the *prefix* but the reported span still covers the
    swallowed text. The adjuster receives the matched text and returns the
    end offset (within the match) of the verified prefix, or None to drop.
    """

    def __init__(self, validator, span_adjuster=None, *args, **kwargs):
        self._validator = validator
        self._span_adjuster = span_adjuster
        super().__init__(*args, **kwargs)

    def validate_result(self, pattern_text):
        return self._validator(pattern_text)

    def analyze(self, text, entities=None, nlp_artifacts=None, regex_flags=None):
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        if not self._span_adjuster or not results:
            return results
        from presidio_analyzer import RecognizerResult
        trimmed = []
        for res in results:
            match = text[res.start:res.end]
            end_rel = self._span_adjuster(match)
            if end_rel is None or end_rel <= 0:
                continue  # nothing verified
            if end_rel >= len(match):
                trimmed.append(res)
                continue
            trimmed.append(RecognizerResult(
                entity_type=res.entity_type,
                start=res.start,
                end=res.start + end_rel,
                score=res.score,
            ))
        return trimmed


AVAILABLE_PACKS = ['india', 'europe', 'brazil', 'usa', 'healthcare']

def get_regional_recognizers(region_name):
    """Dynamically load and return recognizers for a specific region."""
    try:
        module = importlib.import_module(f".{region_name}", package="backend.app.recognizers")
        return module.RECOGNIZERS
    except ImportError:
        return []

def get_all_regional_recognizers():
    """Load all modular recognizers across all regions."""
    all_recognizers = []
    for pack in AVAILABLE_PACKS:
        all_recognizers.extend(get_regional_recognizers(pack))
    return all_recognizers
