from presidio_analyzer import Pattern, PatternRecognizer  # type: ignore
from backend.app.checksums import is_valid_npi
from backend.app.recognizers import ValidatedPatternRecognizer

# NPI — 10-digit National Provider Identifier with the official CMS
# check-digit algorithm (80840 prefix + Luhn). Hard-validated.
npi_pattern = Pattern(
    name="npi_pattern",
    regex=r"\b\d{10}\b",
    score=0.4,
)
npi_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_npi,
    supported_entity="PROVIDER_NPI",
    patterns=[npi_pattern],
    context=["npi", "provider", "physician", "doctor"],
)

mrn_pattern = Pattern(
    name="mrn_pattern",
    regex=r"\b(?:MRN|MR)[- ]?\d{4,9}\b",
    score=0.5,
)
mrn_recognizer = PatternRecognizer(
    supported_entity="MEDICAL_RECORD_NUMBER",
    patterns=[mrn_pattern],
    context=["medical record", "mrn", "patient id", "patient"],
)

icd10_pattern = Pattern(
    name="icd10_pattern",
    # Official ICD-10 structure: one letter (A-Z excluding U) followed by
    # exactly TWO digits, then an optional decimal with 1-3 digits and an
    # optional 7th-character extension letter (e.g. "E11.9", "S72.301A").
    # The old pattern (`[A-TV-Z][0-9][0-9AB]...`) also matched "B2B" — a
    # letter+digit+letter string that is not a valid ICD-10 code.
    regex=r"\b[A-TV-Z][0-9]{2}(?:\.[0-9]{1,3}[A-Z]?)?\b",
    score=0.3,
)
icd10_recognizer = PatternRecognizer(
    supported_entity="ICD10_CODE",
    patterns=[icd10_pattern],
    context=["diagnosis", "icd10", "icd-10", "disease", "condition"],
)

hpi_pattern = Pattern(
    name="hpi_pattern",
    # Require at least one digit in the body so ordinary prose ("plan should") is
    # never mistaken for a health plan identifier.
    regex=r"\b(?:HPI|Plan)[- ]?(?=[A-Z0-9]*[0-9])[A-Z0-9]{5,10}\b",
    score=0.4,
)
hpi_recognizer = PatternRecognizer(
    supported_entity="HEALTH_PLAN_ID",
    patterns=[hpi_pattern],
    context=["insurance", "health plan", "hpi", "coverage"],
)

RECOGNIZERS = [npi_recognizer, mrn_recognizer, icd10_recognizer, hpi_recognizer]
