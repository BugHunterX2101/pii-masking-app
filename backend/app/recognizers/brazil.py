from presidio_analyzer import PatternRecognizer, Pattern  # type: ignore
from backend.app.checksums import is_valid_cpf, is_valid_cnpj
from backend.app.recognizers import ValidatedPatternRecognizer

# CPF: 000.000.000-00 — two official mod-11 check digits.
cpf_pattern = Pattern(name="cpf_pattern", regex=r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', score=0.85)
cpf_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_cpf,
    supported_entity="BR_CPF",
    patterns=[cpf_pattern],
)

# CNPJ: 00.000.000/0000-00 — two official mod-11 check digits.
cnpj_pattern = Pattern(name="cnpj_pattern", regex=r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', score=0.85)
cnpj_recognizer = ValidatedPatternRecognizer(
    validator=is_valid_cnpj,
    supported_entity="BR_CNPJ",
    patterns=[cnpj_pattern],
)

RECOGNIZERS = [cpf_recognizer, cnpj_recognizer]
