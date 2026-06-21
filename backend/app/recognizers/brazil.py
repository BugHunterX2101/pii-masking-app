from presidio_analyzer import PatternRecognizer, Pattern

# CPF: 000.000.000-00
cpf_pattern = Pattern(name="cpf_pattern", regex=r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', score=0.85)
cpf_recognizer = PatternRecognizer(supported_entity="BR_CPF", patterns=[cpf_pattern])

# CNPJ: 00.000.000/0000-00
cnpj_pattern = Pattern(name="cnpj_pattern", regex=r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', score=0.85)
cnpj_recognizer = PatternRecognizer(supported_entity="BR_CNPJ", patterns=[cnpj_pattern])

RECOGNIZERS = [cpf_recognizer, cnpj_recognizer]
