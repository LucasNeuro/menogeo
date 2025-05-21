import os
import requests
from dotenv import load_dotenv
from app.memory import salvar_dados_cliente

load_dotenv()

IXC_API_URL = os.getenv("IXC_API_URL")

async def buscar_e_salvar_dados_ixc(cpf: str) -> dict:
    """Consulta o IXC pelo CPF, salva os dados no Mem0AI e retorna o payload."""
    response = requests.post(IXC_API_URL, json={"cpf": cpf})
    dados = response.json()
    await salvar_dados_cliente(cpf, dados)
    return dados

def abrir_os(cpf: str, motivo: str) -> str:
    requests.post("https://hook.us2.make.com/f1x53952bxirumz2gnfpoabdo397uws2", json={"cpf": cpf, "motivo": motivo})
    return "🛠️ Solicitação registrada! Equipe técnica notificada."