from presidio_analyzer import Pattern, PatternRecognizer  # type: ignore

npi_pattern = Pattern(
    name="npi_pattern",
    regex=r"\b\d{10}\b",  # National Provider Identifier is a 10-digit intelligence-free numeric identifier
    score=0.4
)
npi_recognizer = PatternRecognizer(
    supported_entity="PROVIDER_NPI",
    patterns=[npi_pattern],
    context=["npi", "provider", "physician", "doctor"]
)

mrn_pattern = Pattern(
    name="mrn_pattern",
    regex=r"\b(?:MRN|MR)[- ]?\d{4,9}\b",
    score=0.5
)
mrn_recognizer = PatternRecognizer(
    supported_entity="MEDICAL_RECORD_NUMBER",
    patterns=[mrn_pattern],
    context=["medical record", "mrn", "patient id", "patient"]
)

icd10_pattern = Pattern(
    name="icd10_pattern",
    regex=r"\b[A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4}\b",
    score=0.3
)
icd10_recognizer = PatternRecognizer(
    supported_entity="ICD10_CODE",
    patterns=[icd10_pattern],
    context=["diagnosis", "icd10", "icd-10", "disease", "condition"]
)

hpi_pattern = Pattern(
    name="hpi_pattern",
    regex=r"\b(?:HPI|Plan)[- ]?[A-Z0-9]{5,10}\b",
    score=0.4
)
hpi_recognizer = PatternRecognizer(
    supported_entity="HEALTH_PLAN_ID",
    patterns=[hpi_pattern],
    context=["insurance", "health plan", "hpi", "coverage"]
)

RECOGNIZERS = [npi_recognizer, mrn_recognizer, icd10_recognizer, hpi_recognizer]
