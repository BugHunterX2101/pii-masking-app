import re

from presidio_analyzer import PatternRecognizer, Pattern  # type: ignore
from backend.app.checksums import is_valid_iban, is_valid_vat
from backend.app.recognizers import ValidatedPatternRecognizer

# IBAN (General European Bank Account) — official ISO 13616 mod-97 check digit.
iban_pattern = Pattern(name="iban_pattern", regex=r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b', score=0.85)
iban_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_iban,
    supported_entity="EU_IBAN",
    patterns=[iban_pattern],
)

# EU VAT — per-country official checksums validated via python-stdnum. This
# covers the letter-body formats the old pure-digit regex missed: Austria's
# `ATU...`, Spain's CIF, Ireland's letter suffix, the Netherlands' `...B..`.
#
# Two patterns are needed. A *compact* one (`DE136695976`) matches the exact
# alphanumeric run; a *spaced* one (`FR 61 954 506 077`) tolerates single
# space/dash group separators. The checksum validator is the real filter: the
# digit-lookahead keeps plain words ("beautiful", "detail") from ever reaching
# it, and anything that does reach it either passes the official checksum or
# is dropped.
_EU_VAT_CODES = (
    "ATU|AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|GB"
)
_EU_VAT_COMPACT_RE = rf"\b(?:{_EU_VAT_CODES})(?=[A-Z0-9]*[0-9])[A-Z0-9]{{5,16}}\b"
# The leading separator is required because spaced VATs write the code and the
# first group with a space between them ("FR 61 954 506 077", "DE 136 695 976").
_EU_VAT_SPACED_RE = rf"\b(?:{_EU_VAT_CODES})(?=[A-Z0-9 -]*[0-9])[ -][A-Z0-9]{{1,4}}(?:[ -][A-Z0-9]{{1,4}}){{1,5}}\b"

_VAT_SEPARATOR_RE = re.compile(r"[\s-]+")


def _vat_validator(match_text: str) -> bool:
    """Validate a candidate VAT match, allowing for trailing words.

    The spaced pattern can greedily swallow a following word ("DE 136 695 976
    on the"). If the full match fails its checksum, retry each prefix at a
    separator boundary (longest first) so the genuine VAT still validates.
    """
    if is_valid_vat(match_text):
        return True
    parts = _VAT_SEPARATOR_RE.split(match_text)
    for i in range(len(parts) - 1, 0, -1):
        if is_valid_vat("".join(parts[:i])):
            return True
    return False


vat_pattern = Pattern(name="vat_pattern", regex=_EU_VAT_COMPACT_RE, score=0.5)
vat_spaced_pattern = Pattern(name="vat_spaced_pattern", regex=_EU_VAT_SPACED_RE, score=0.5)
vat_recognizer = ValidatedPatternRecognizer(
    validator=_vat_validator,
    supported_entity="EU_VAT",
    patterns=[vat_pattern, vat_spaced_pattern],
)

RECOGNIZERS = [iban_recognizer, vat_recognizer]
