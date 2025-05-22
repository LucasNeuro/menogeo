import requests
import os

IXC_API_URL = os.getenv("IXC_API_URL")

def buscar_dados_ixc(cpf):
    payload = {"cpf": cpf}
    response = requests.post(IXC_API_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    print(f"[DEBUG IXC] Retorno do IXC_API para CPF {cpf}: {data}")
    return data 