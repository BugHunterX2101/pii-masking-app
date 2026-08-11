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


def _vat_prefix_end(match_text: str) -> int:
    """Return the end offset (within the match) of the verified VAT prefix.

    The patterns can absorb trailing characters beyond the real VAT:

    - the spaced form can swallow a following uppercase word ("DE 136 695 976
      S");
    - the compact form can be glued to trailing letters ("ATU57194903X").

    Try the full string first, then prefixes at separator boundaries (longest
    first), then the compact form with up to 4 trailing letters trimmed.
    Returns 0 when nothing validates, so callers can drop the match.
    """
    if is_valid_vat(match_text):
        return len(match_text)
    parts = _VAT_SEPARATOR_RE.split(match_text)
    for i in range(len(parts) - 1, 0, -1):
        if is_valid_vat("".join(parts[:i])):
            # Original character length: token lengths + the separators between.
            return sum(len(p) for p in parts[:i]) + (i - 1)
    trimmed = re.sub(r"[A-Z]+$", "", match_text)
    if trimmed != match_text and len(match_text) - len(trimmed) <= 4 and is_valid_vat(trimmed):
        return len(trimmed)
    return 0


def _vat_validator(match_text: str) -> bool:
    return _vat_prefix_end(match_text) > 0


def _vat_span_adjuster(match_text: str):
    """Span trims to the verified prefix so swallowed trailing words are not
    blacked out (e.g. "DE 136 695 976 S" masks only the VAT, not the "S")."""
    end = _vat_prefix_end(match_text)
    return end if end > 0 else None


vat_pattern = Pattern(name="vat_pattern", regex=_EU_VAT_COMPACT_RE, score=0.5)
vat_spaced_pattern = Pattern(name="vat_spaced_pattern", regex=_EU_VAT_SPACED_RE, score=0.5)
vat_recognizer = ValidatedPatternRecognizer(
    validator=_vat_validator,
    span_adjuster=_vat_span_adjuster,
    supported_entity="EU_VAT",
    patterns=[vat_pattern, vat_spaced_pattern],
)

RECOGNIZERS = [iban_recognizer, vat_recognizer]
