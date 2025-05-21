import re

def extrair_cpf(texto: str) -> str:
    match = re.search(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b', texto)
    return match.group(0) if match else "" 