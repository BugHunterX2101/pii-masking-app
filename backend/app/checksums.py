"""Check-digit validators for high-accuracy PII detection.

Many national identifiers end in a computed check digit. Validating it drops
the vast majority of regex false positives (random alphanumeric strings that
merely *look* like an Aadhaar, PAN, NPI, routing number, CPF, CNPJ or IBAN).

Each validator is a pure function returning True only for identifiers whose
check digit(s) verify, or whose checksum is otherwise officially standardized.

Note on PAN: India's tax authority has never published the PAN checksum, so
`is_valid_pan` is used as a *confidence boost* (a separate recognizer), never
as a hard gate — a DLP tool must err toward flagging.
"""

import re

_CHARS36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------------------------------------------------------------------------
# Verhoeff check digit (used by Aadhaar — the 12th digit is a Verhoeff check)
# ---------------------------------------------------------------------------
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def is_valid_aadhaar(aadhaar: str) -> bool:
    """Validate an Aadhaar number (12 digits) via its Verhoeff check digit."""
    digits = re.sub(r"\D", "", aadhaar or "")
    return len(digits) == 12 and _verhoeff_valid(digits)


def is_valid_pan(pan: str) -> bool:
    """Validate an Indian PAN against its widely used mod-36 checksum.

    Format: ABCDE1234F — 5 letters, 4 digits, 1 letter, where the 10th
    character is derived from the first nine. The government has never
    published this checksum, so treat a positive result as *supporting
    evidence* (boost), never as the sole gate.
    """
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan or ""):
        return False
    total = sum(i * _CHARS36.index(pan[i - 1]) for i in range(1, 10))
    return pan[9] == _CHARS36[total % 36]


def _luhn_with_check(number: str, check_digit: str) -> bool:
    """Standard Luhn check: double every second digit (odd 0-based index from
    the left — equivalent to doubling from the right on an even-length string),
    digit-sum the doublings, and require the check digit to complete the sum to
    a multiple of ten."""
    total = 0
    for idx, ch in enumerate(number):
        d = int(ch)
        if idx % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10 == int(check_digit)


def is_valid_npi(npi: str) -> bool:
    """Validate a US NPI (10 digits) using the official check-digit algorithm.

    Per CMS: prefix the first nine digits with 80840 (making a 14-digit
    number), compute the standard Luhn check digit, and require it to equal
    the tenth digit.
    """
    if not re.fullmatch(r"\d{10}", npi or ""):
        return False
    return _luhn_with_check("80840" + npi[:9], npi[9])


def is_valid_routing_number(routing: str) -> bool:
    """Validate a US ABA routing number (9 digits, mod-10 with 3-7-1 weights)."""
    if not re.fullmatch(r"\d{9}", routing or ""):
        return False
    weights = [3, 7, 1, 3, 7, 1, 3, 7, 1]
    return sum(int(d) * w for d, w in zip(routing, weights)) % 10 == 0


def is_valid_cpf(cpf: str) -> bool:
    """Validate a Brazilian CPF (11 digits) using its two mod-11 check digits."""
    digits = re.sub(r"\D", "", cpf or "")
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for j in range(9, 11):
        total = sum(int(digits[i]) * (j + 1 - i) for i in range(j))
        d = (total * 10) % 11
        d = 0 if d == 10 else d
        if int(digits[j]) != d:
            return False
    return True


def is_valid_cnpj(cnpj: str) -> bool:
    """Validate a Brazilian CNPJ (14 digits) using its two mod-11 check digits."""
    digits = re.sub(r"\D", "", cnpj or "")
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(digits[i]) * weights_1[i] for i in range(12))
    d1 = 11 - (total % 11)
    d1 = 0 if d1 >= 10 else d1
    if int(digits[12]) != d1:
        return False
    weights_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(digits[i]) * weights_2[i] for i in range(13))
    d2 = 11 - (total % 11)
    d2 = 0 if d2 >= 10 else d2
    return int(digits[13]) == d2


def is_valid_iban(iban: str) -> bool:
    """Validate an IBAN using the official ISO 13616 mod-97 check.

    The first four characters (country + check digits) are moved to the end,
    letters are converted to numbers (A=10..Z=35), and the resulting integer
    must be congruent to 1 modulo 97.
    """
    iban = re.sub(r"\s+", "", iban or "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(10 + ord(ch) - ord("A"))
    # Modular reduction to keep the arithmetic cheap.
    remainder = 0
    for ch in numeric:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder == 1


def is_valid_vat(vat: str) -> bool:
    """Validate a European VAT number via its official per-country checksum.

    VAT numbers are *not* a uniform format: the body may be pure digits
    (DE, IT, PL, ...), a letter plus digits (AT `ATU...`, ES CIF), a letter
    suffix (IE, CY), or an embedded letter (NL `...B..`). Each member state
    also defines its own checksum (mod-11 weighted, mod-97, CIF, ISO 7064,
    ...). This delegates to python-stdnum, which implements the algorithms
    the European Commission publishes, so formats like Austria's `ATU...`
    are validated instead of being dropped or falsely flagged.

    Czech (CZ) and Slovak (SK) numbers have no offline checksum by law —
    only their format is checked. UK (GB) numbers use the HMRC mod-97
    scheme.
    """
    vat = re.sub(r"[\s-]+", "", vat or "").upper()
    if not vat:
        return False
    if vat.startswith("CZ"):
        return bool(re.fullmatch(r"CZ\d{8,10}", vat))
    if vat.startswith("SK"):
        return bool(re.fullmatch(r"SK\d{10}", vat))
    try:
        if vat.startswith("GB"):
            import stdnum.gb.vat as gb_vat  # type: ignore

            gb_vat.validate(vat)
        else:
            import stdnum.eu.vat as eu_vat  # type: ignore

            eu_vat.validate(vat)
        return True
    except Exception:
        return False
