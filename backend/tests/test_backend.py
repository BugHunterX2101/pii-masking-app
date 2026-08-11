"""
Lightweight backend tests — runnable without downloading the spaCy language
models (model loading is lazy in pii_engine, so the pure-logic units below
only need the base presidio/spacy packages).

Run with:  python -m pytest backend/tests -q
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import pii_engine, email_verification
from backend.app.checksums import (
    is_valid_aadhaar,
    is_valid_pan,
    is_valid_npi,
    is_valid_routing_number,
    is_valid_cpf,
    is_valid_cnpj,
    is_valid_iban,
    is_valid_vat,
)
from backend.app.recognizers import get_all_regional_recognizers


# ---------------------------------------------------------------------------
# Check-digit validators — ground-truth examples from official sources
# ---------------------------------------------------------------------------
def test_npi_check_digit():
    # 1234567893 is the canonical CMS-documented example NPI.
    assert is_valid_npi("1234567893") is True
    assert is_valid_npi("1234567892") is False
    assert is_valid_npi("123-456-789") is False


def test_routing_number_check_digit():
    # 021000021 is a well-known valid ABA routing number (JPMorgan Chase).
    assert is_valid_routing_number("021000021") is True
    assert is_valid_routing_number("021000022") is False
    assert is_valid_routing_number("0210000") is False


def test_cpf_check_digits():
    # 529.982.247-25 is the canonical valid CPF example.
    assert is_valid_cpf("52998224725") is True
    assert is_valid_cpf("529.982.247-25") is True
    assert is_valid_cpf("52998224726") is False
    assert is_valid_cpf("11111111111") is False  # all-same-digit rejection


def test_cnpj_check_digits():
    # 11.222.333/0001-81 is the canonical valid CNPJ example.
    assert is_valid_cnpj("11222333000181") is True
    assert is_valid_cnpj("11.222.333/0001-81") is True
    assert is_valid_cnpj("11222333000182") is False


def test_iban_mod97():
    # GB29 NWBK 6016 1331 9268 19 is the reference IBAN from the ISO 13616 spec.
    assert is_valid_iban("GB29NWBK60161331926819") is True
    assert is_valid_iban("GB29 NWBK 6016 1331 9268 19") is True
    assert is_valid_iban("GB29NWBK60161331926818") is False
    assert is_valid_iban("DE89370400440532013000") is True  # well-known valid DE IBAN


def test_vat_valid_examples_all_countries():
    # One checksum-valid example per country, generated via python-stdnum's
    # own algorithms (the EU Commission's published mod-11/mod-97/CIF checks).
    examples = [
        "ATU57194903", "BE428759497", "BG175074752", "CY10259033P",
        "DE136695976", "DK30792440", "EE841485253", "EL094259216",
        "ESS92174218", "FI52320444", "FR61954506077", "HR54176240103",
        "HU43313604", "IE6433435F", "IT74381650253", "LT397419217",
        "LU24181401", "LV84142429166", "MT11679112", "NL888498780B84",
        "PL1734521186", "PT188358889", "RO1319148890", "SE123456789701",
        "SI81458991", "GB980780684",
    ]
    for vat in examples:
        assert is_valid_vat(vat) is True, f"{vat} should validate"


def test_vat_tampered_and_formatted():
    assert is_valid_vat("ATU57194904") is False
    assert is_valid_vat("DE136695977") is False
    assert is_valid_vat("PL1734521187") is False
    # Separators are stripped before the checksum runs.
    assert is_valid_vat("AT U 57194903") is True
    assert is_valid_vat("DE 136 695 976") is True
    assert is_valid_vat("FR-61954506077") is True


def test_vat_cz_sk_format_only():
    # CZ/SK have no offline checksum by law — format is the only gate.
    assert is_valid_vat("CZ12345678") is True
    assert is_valid_vat("SK1234567890") is True
    assert is_valid_vat("CZ123") is False
    assert is_valid_vat("SK12345678901") is False


def test_vat_plain_words_rejected():
    # The old regex flagged ordinary words; the checksum gate must not.
    for word in ["beautiful", "detail", "Aadhaar", "routing", "IBAN",
                 "CNPJ", "partner", "DE2024", "BE12"]:
        assert is_valid_vat(word) is False, f"{word} must not validate as VAT"


def test_vat_recognizer_end_to_end():
    from backend.app.recognizers.europe import vat_recognizer
    # Letter-body formats validate in context.
    assert vat_recognizer.validate_result("ATU57194903") is True
    assert vat_recognizer.validate_result("NL888498780B84") is True
    assert vat_recognizer.validate_result("IE6433435F") is True
    assert vat_recognizer.validate_result("ESS92174218") is True
    # Spaced format and trailing words are tolerated.
    assert vat_recognizer.validate_result("FR 61 954 506 077") is True
    assert vat_recognizer.validate_result("DE136695976 on the") is True
    assert vat_recognizer.validate_result("DE 136 695 976 on the") is True
    # Plain words never validate.
    assert vat_recognizer.validate_result("beautiful") is False
    assert vat_recognizer.validate_result("detail") is False
    assert vat_recognizer.validate_result("DE2024") is False


def test_aadhaar_verhoeff():
    # No official public sample exists, so generate a valid number by brute
    # force (a random 12-digit string passes Verhoeff with p=1/10) and verify
    # that a single-digit mutation always breaks the checksum.
    rng = random.Random(42)
    valid = None
    for _ in range(2000):
        candidate = "".join(rng.choice("0123456789") for _ in range(12))
        if is_valid_aadhaar(candidate):
            valid = candidate
            break
    assert valid is not None
    assert is_valid_aadhaar(valid) is True
    mutated = (
        valid[:5] + ("9" if valid[5] != "9" else "8") + valid[6:]
    )
    assert is_valid_aadhaar(mutated) is False
    assert is_valid_aadhaar("1234 5678 9012") is False  # 12 raw digits required


def test_pan_checksum_boost():
    # The PAN checksum is not officially published — build a valid PAN by
    # computing the check digit from the first nine characters, then confirm
    # the checker accepts it and rejects a mutated variant.
    _chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    base = "ABCDE1234"
    total = sum(i * _chars.index(base[i - 1]) for i in range(1, 10))
    valid_pan = base + _chars[total % 36]
    assert is_valid_pan(valid_pan) is True
    mutated = valid_pan[:9] + ("A" if valid_pan[9] != "A" else "B")
    assert is_valid_pan(mutated) is False
    assert is_valid_pan("abcde1234f") is False  # lowercase rejected by format


def test_pan_checksum_recognizer_wired():
    from backend.app.recognizers import india as india_module
    checksum_recognizer = india_module.pan_checksum_recognizer
    plain_recognizer = india_module.pan_recognizer
    _chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    base = "ABCDE1234"
    total = sum(i * _chars.index(base[i - 1]) for i in range(1, 10))
    valid_pan = base + _chars[total % 36]
    # Plain recognizer keeps recall (no validator); checksum recognizer boosts.
    assert checksum_recognizer.validate_result(valid_pan) is True
    assert plain_recognizer.validate_result(valid_pan) is None


# ---------------------------------------------------------------------------
# Verified-email-provider policy
# ---------------------------------------------------------------------------
def test_email_verified_provider_allowed():
    allowed, reason = email_verification.validate_email("user@gmail.com")
    assert allowed is True, reason
    allowed, reason = email_verification.validate_email("someone@outlook.com")
    assert allowed is True, reason
    allowed, reason = email_verification.validate_email("x@protonmail.com")
    assert allowed is True, reason


def test_email_disposable_blocked():
    for addr in ["a@mailinator.com", "b@10minutemail.com", "c@yopmail.com", "d@guerrillamail.com"]:
        allowed, reason = email_verification.validate_email(addr)
        assert allowed is False, f"{addr} should be blocked, got: {reason}"


def test_email_invalid_format_blocked():
    for addr in ["not-an-email", "missing@tld", "@nodomain.com", "spaces in@x.com"]:
        allowed, _ = email_verification.validate_email(addr)
        assert allowed is False


def test_email_unknown_domain_requires_mx(monkeypatch):
    monkeypatch.setattr(email_verification, "_domain_has_mx", lambda d, timeout=3.0: False)
    allowed, reason = email_verification.validate_email("x@random-domain-xyz123.invalid")
    assert allowed is False
    assert "MX" in reason or "verified" in reason

    monkeypatch.setattr(email_verification, "_domain_has_mx", lambda d, timeout=3.0: True)
    allowed, reason = email_verification.validate_email("x@random-domain-xyz123.invalid")
    assert allowed is True


def test_email_case_and_whitespace_normalized():
    allowed, _ = email_verification.validate_email("  USER@GMAIL.COM  ")
    assert allowed is True


# ---------------------------------------------------------------------------
# Custom regex policy application
# ---------------------------------------------------------------------------
def test_custom_regex_detects_matches():
    sentence = "Employee EMP-12345 and EMP-67890 onboarded."
    first = sentence.index("EMP-12345")
    second = sentence.index("EMP-67890")
    results = pii_engine._apply_custom_regex(
        sentence,
        [{"name": "EMP_ID", "pattern": r"EMP-\d{5}"}],
    )
    assert len(results) == 2
    assert all(r.entity_type == "EMP_ID" for r in results)
    assert results[0].start == first
    assert results[0].end == first + len("EMP-12345")
    assert results[1].start == second


def test_custom_regex_invalid_pattern_is_ignored():
    results = pii_engine._apply_custom_regex("anything", [{"name": "BAD", "pattern": r"([unclosed"}])
    assert results == []


def test_custom_regex_none_patterns():
    assert pii_engine._apply_custom_regex("hello world", None) == []


# ---------------------------------------------------------------------------
# Overlap removal
# ---------------------------------------------------------------------------
def _result(start, end, etype):
    from presidio_analyzer import RecognizerResult
    return RecognizerResult(entity_type=etype, start=start, end=end, score=1.0)


def test_overlaps_keep_longest_first_match():
    results = [
        _result(0, 12, "PHONE_NUMBER"),
        _result(0, 5, "PERSON"),     # same start, shorter -> dropped
        _result(12, 20, "EMAIL_ADDRESS"),
        _result(14, 18, "URL"),       # nested in EMAIL -> dropped
    ]
    filtered = pii_engine._remove_overlaps(results)
    assert [r.entity_type for r in filtered] == ["PHONE_NUMBER", "EMAIL_ADDRESS"]


def test_no_overlaps_passthrough():
    results = [_result(0, 4, "A"), _result(5, 9, "B")]
    assert pii_engine._remove_overlaps(results) == results


def test_empty_results():
    assert pii_engine._remove_overlaps([]) == []


# ---------------------------------------------------------------------------
# Language resolution
# ---------------------------------------------------------------------------
def test_language_clamped_to_supported():
    assert pii_engine._resolve_language("xx") == "en"
    assert pii_engine._resolve_language(None, "   ") == "en"
    assert pii_engine._resolve_language("es", "anything") == "es"


# ---------------------------------------------------------------------------
# Regional recognizers — every declared pack must load with unique entities
# ---------------------------------------------------------------------------
def test_regional_recognizers_registered_for_every_language():
    # Regional regex recognizers are language-independent, so they must fire
    # regardless of the detected language. Presidio filters by
    # supported_language at analyze time — a recognizer registered only for
    # "en" silently never runs for Spanish/French/German texts.
    analyzer = pii_engine._get_analyzer()
    for lang in ["en", "es", "fr", "de", "pt", "nl"]:
        recs = analyzer.registry.get_recognizers(
            language=lang,
            entities=["BR_CPF", "AADHAAR", "EU_IBAN", "EU_VAT"],
        )
        entities = {e for r in recs for e in r.supported_entities}
        for expected in ["BR_CPF", "AADHAAR", "EU_IBAN", "EU_VAT"]:
            assert expected in entities, f"{expected} missing for language {lang}"


def test_all_regional_recognizers_load():
    recognizers = get_all_regional_recognizers()
    assert len(recognizers) >= 13  # india(4) + europe(2) + usa(1) + brazil(2) + healthcare(4)
    entities = [ent for r in recognizers for ent in r.supported_entities]
    # PAN_CARD intentionally appears twice: a plain regex recognizer (recall)
    # and a checksum-validated twin (precision boost). No other entity may
    # legitimately be duplicated across packs.
    from collections import Counter
    counts = Counter(entities)
    for entity, n in counts.items():
        if entity == "PAN_CARD":
            assert n == 2, f"PAN_CARD should have exactly 2 recognizers, got {n}"
        else:
            assert n == 1, f"Duplicate entity {entity} across recognizers ({n}x)"
    for expected in ["AADHAAR", "PAN_CARD", "VEHICLE_REG", "EU_IBAN", "EU_VAT",
                     "US_ROUTING_NUMBER", "BR_CPF", "BR_CNPJ", "PROVIDER_NPI",
                     "MEDICAL_RECORD_NUMBER", "ICD10_CODE", "HEALTH_PLAN_ID"]:
        assert expected in entities


def test_overlap_keeps_higher_score_extension():
    from presidio_analyzer import RecognizerResult
    low = RecognizerResult(entity_type="PAN_CARD", start=0, end=9, score=0.85)
    high = RecognizerResult(entity_type="PAN_CARD", start=3, end=14, score=1.0)
    filtered = pii_engine._remove_overlaps([low, high])
    assert len(filtered) == 1
    assert filtered[0] is high


def test_overlap_drops_lower_score_contained():
    from presidio_analyzer import RecognizerResult
    low = RecognizerResult(entity_type="PERSON", start=0, end=12, score=0.85)
    high = RecognizerResult(entity_type="PHONE_NUMBER", start=2, end=10, score=1.0)
    filtered = pii_engine._remove_overlaps([low, high])
    assert len(filtered) == 1
    assert filtered[0] is low


# ---------------------------------------------------------------------------
# Sanitizer replacement helpers (dataset synthesis)
# ---------------------------------------------------------------------------
def test_synthesize_empty_text():
    result = pii_engine.detect_and_synthesize_text("   ", ["PERSON"])
    assert result["found"] is False
    assert result["matches"] == 0


# ---------------------------------------------------------------------------
# PERSON verification gate + ICD-10 strictness (masked-document accuracy)
#
# Regression for the real resume that was over-redacted: spaCy's NER tagged
# tech/product words (Prometheus, Java, NumPy, Linux, Streamlit, Express.js,
# Keras Tuner, Tailwind CSS, "Chapter Bengaluru" ...) as PERSON with a
# 0.85 score, and the loose ICD-10 pattern matched "B2B". Both classes of
# false positive are now rejected; genuine names and codes still pass.
# ---------------------------------------------------------------------------
_DEFAULT_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "AADHAAR", "PAN_CARD", "VEHICLE_REG",
    "EU_IBAN", "EU_VAT",
    "US_ROUTING_NUMBER", "BR_CPF", "BR_CNPJ",
    "PROVIDER_NPI", "MEDICAL_RECORD_NUMBER", "ICD10_CODE", "HEALTH_PLAN_ID",
]

_RESUME_TEXT = (
    "Vedit Agrawal | veditagrawal21@gmail.com | +91 8000809591 | "
    "Education: BMS College of Engineering, Bengaluru India. "
    "Implemented system monitoring using Prometheus and Grafana. "
    "Built a B2B lead platform with Node.js, Express.js, Groq (LLaMA 3.3 70B). "
    "Tuned models with Keras Tuner, shipped a Streamlit dashboard. "
    "Skills: Python, C/C++, Java, JavaScript, NumPy, Tailwind CSS, Linux, Core CS. "
    "Volunteer: BMSCE GeeksForGeeks Student Chapter, Bengaluru India."
)


def _hit_types(text, entities):
    return [(r.entity_type, text[r.start:r.end]) for r in pii_engine.detect_raw(text, entities)]


def test_resume_produces_no_false_positive_redactions():
    """The exact resume scenario: only the email and phone may be flagged.

    Before the PERSON gate, this text produced 14 hits (10 hallucinated
    PERSON spans plus the ICD-10 "B2B"); after the fix it must be exactly
    the two real pieces of contact PII.
    """
    hits = _hit_types(_RESUME_TEXT, _DEFAULT_ENTITIES)
    types = sorted({t for t, _ in hits})
    assert types == ["EMAIL_ADDRESS", "PHONE_NUMBER"], f"unexpected hits: {hits}"
    assert all(t != "PERSON" for t, _ in hits)
    assert all(t != "ICD10_CODE" for t, _ in hits)


def test_person_gate_rejects_unknown_capitalized_words():
    """Brand/product words the NER calls PERSON must be dropped unless the
    token is a known common name."""
    for sentence in [
        "Prometheus monitors the Java cluster with NumPy and Linux.",
        "The Streamlit dashboard replaced the Express.js backend.",
    ]:
        hits = _hit_types(sentence, ["PERSON"])
        assert hits == [], f"unexpected PERSON hits: {hits}"


def test_person_gate_keeps_common_names():
    """Genuine names (present in the common-name list) still pass the gate."""
    text = "John Smith and Sarah Johnson presented the quarterly results."
    hits = _hit_types(text, ["PERSON"])
    names = {snippet for _, snippet in hits}
    assert "John" in names or "John Smith" in names, f"no John hit: {hits}"
    assert "Sarah" in names or "Sarah Johnson" in names, f"no Sarah hit: {hits}"


def test_icd10_requires_two_digits():
    """The ICD-10 pattern must match real codes and reject "B2B"-style strings.

    Old pattern `[A-TV-Z][0-9][0-9AB]...` matched letter+digit+letter (B2B,
    C3PO). Official codes are letter + TWO digits + optional decimal part.
    """
    text = "Diagnosis B2B C3PO versus E11.9 and S72.301A plus F41."
    hits = _hit_types(text, ["ICD10_CODE"])
    flagged = {snippet for _, snippet in hits}
    assert "E11.9" in flagged, f"E11.9 should flag: {hits}"
    assert "S72.301A" in flagged, f"S72.301A should flag: {hits}"
    assert "F41" in flagged, f"F41 should flag: {hits}"
    assert "B2B" not in flagged, f"B2B must not flag: {hits}"
    assert "C3PO" not in flagged, f"C3PO must not flag: {hits}"


# ---------------------------------------------------------------------------
# Name recall without false positives (marker contexts + header name lines)
# ---------------------------------------------------------------------------
def test_person_gate_accepts_marker_context_names():
    """Names the NER misses but that follow a strong marker are recovered.
    This is what fixes the "Vedit Agrawal not flagged" trade-off: the name is
    not in the common-name list, but the marker context verifies it."""
    for text, expected in [
        ("Name: Vedit Agrawal, Software Engineer", "Vedit Agrawal"),
        ("Regards, Vedit Agrawal", "Vedit Agrawal"),
        ("Prepared by: Sarah Johnson", "Sarah Johnson"),
        ("Best regards, Vedit Agrawal", "Vedit Agrawal"),
        ("From: Vedit Agrawal <vedit@x.com>", "Vedit Agrawal"),
    ]:
        hits = _hit_types(text, ["PERSON"])
        flagged = {snippet for _, snippet in hits}
        assert expected in flagged, f"{expected!r} missing in {hits}"


def test_person_span_never_includes_the_marker_word():
    """"Contact John Smith" must flag only "John Smith", not the marker."""
    hits = _hit_types("Contact John Smith at john@x.com", ["PERSON"])
    snippets = {snippet for _, snippet in hits}
    assert "John Smith" in snippets, f"John Smith missing: {hits}"
    assert not any(s.startswith("Contact") for s in snippets), f"marker leaked: {hits}"
    # "Contact Support Team" is not a person — no common name in the run.
    hits2 = _hit_types("Please contact Support Team for help", ["PERSON"])
    assert hits2 == [], f"Support Team should not flag: {hits2}"


def test_person_gate_still_rejects_unverified_words():
    """The precision guarantee must hold: brand/product words stay unflagged
    even in plausible sentences."""
    for text in [
        "monitoring using Prometheus and Keras Tuner",
        "powered by Tailwind CSS and Streamlit",
        "Dear CloudRaft Hiring Team,",
        "BMS College of Engineering, Bengaluru India",
    ]:
        hits = _hit_types(text, ["PERSON"])
        assert hits == [], f"unexpected PERSON hits for {text!r}: {hits}"


def test_vat_spaced_span_trimmed_to_verified_prefix():
    """The spaced VAT form must never over-mask a trailing uppercase word.
    "DE 136 695 976 S" masks only the VAT; the " S" stays visible."""
    text = "Ref DE 136 695 976 S here"
    result = pii_engine.detect_and_mask_text(text, ["EU_VAT"], "BLACKOUT")
    redacted = result["redacted"]
    assert "DE 136 695 976" not in redacted
    assert "S here" in redacted, f"trailing 'S' must survive: {redacted!r}"
    assert "Ref" in redacted

    glued = pii_engine.detect_and_mask_text("ATU57194903X end", ["EU_VAT"], "BLACKOUT")
    assert "X end" in glued["redacted"], f"trailing letter must survive: {glued['redacted']!r}"
