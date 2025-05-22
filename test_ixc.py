import os
import requests

IXC_API_URL = os.getenv("IXC_API_URL", "https://n8n.rafaeltoshiba.com.br/webhook/ixc/consultaCliente")

def consultar_tudo_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(IXC_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder (timeout). Tente novamente mais tarde.")
    except requests.exceptions.RequestException as e:
        print(f"Erro de requisição: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")
    return None

if __name__ == "__main__":
    cpf = input("Digite o CPF para consulta: ")
    dados = consultar_tudo_ixc(cpf)
    if dados:
        print("\nPayload retornado do IXC:")
        print(dados)
    else:
        print("Não foi possível obter os dados do IXC.") 