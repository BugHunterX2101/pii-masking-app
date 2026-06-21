import importlib

AVAILABLE_PACKS = ['india', 'europe', 'brazil', 'usa']

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
