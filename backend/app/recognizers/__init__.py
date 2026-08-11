import importlib

from presidio_analyzer import PatternRecognizer  # type: ignore


class ValidatedPatternRecognizer(PatternRecognizer):
    """PatternRecognizer backed by a check-digit predicate.

    Presidio's PatternRecognizer exposes a `validate_result` hook: returning
    True promotes the match to full confidence (1.0) and returning False drops
    it (0.0). Subclassing is the only supported way to supply that hook, so
    this class turns a plain callable into it — e.g. is_valid_cpf wired onto
    the CPF regex turns noisy pattern matches into verified identifiers.
    """

    def __init__(self, validator, *args, **kwargs):
        self._validator = validator
        super().__init__(*args, **kwargs)

    def validate_result(self, pattern_text):
        return self._validator(pattern_text)


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
