import os
from dotenv import load_dotenv
import mem0ai

load_dotenv()
mem0 = mem0ai.Client(api_key=os.getenv("MEM0AI_API_KEY"))

async def salvar_dados_cliente(cpf: str, dados: dict):
    """Salva ou atualiza os dados do cliente e contratos no Mem0AI."""
    await mem0.upsert("clientes", {"cpf": cpf}, dados.get("cliente", {}))
    for contrato in dados.get("contratos", {}).get("contratosAtivos", []):
        await mem0.upsert("contratos", {"cliente_cpf": cpf, "id": contrato.get("id")}, contrato)
    for boleto in dados.get("boletos", []):
        await mem0.upsert("boletos", {"cliente_cpf": cpf, "id": boleto.get("id")}, boleto)
    if dados.get("login"):
        await mem0.upsert("logins", {"cliente_cpf": cpf}, dados["login"])

async def buscar_contexto_cliente(cpf: str):
    """Busca todos os dados relevantes do cliente no Mem0AI."""
    cliente = await mem0.get("clientes", {"cpf": cpf})
    contratos = await mem0.search("contratos", {"cliente_cpf": cpf})
    boletos = await mem0.search("boletos", {"cliente_cpf": cpf})
    login = await mem0.get("logins", {"cliente_cpf": cpf})
    historico = await mem0.search("conversas", {"cliente_cpf": cpf, "limit": 5})
    return {
        "cliente": cliente,
        "contratos": contratos,
        "boletos": boletos,
        "login": login,
        "historico_conversas": historico
    }

async def salvar_conversa(cpf: str, mensagem: str, resposta: str):
    """Salva uma interação no histórico de conversas do cliente."""
    await mem0.create("conversas", {
        "cliente_cpf": cpf,
        "mensagem_cliente": mensagem,
        "resposta_geovana": resposta,
        "timestamp": "now()"
    })

async def vincular_cpf_remotejid(remote_jid: str, cpf: str):
    """Vincula o remoteJid do WhatsApp ao CPF do cliente no Mem0AI."""
    await mem0.upsert("vinculos_whatsapp", {"remote_jid": remote_jid}, {"remote_jid": remote_jid, "cpf": cpf})

async def buscar_cpf_por_remotejid(remote_jid: str) -> str:
    """Busca o CPF vinculado a um remoteJid no Mem0AI."""
    vinculo = await mem0.get("vinculos_whatsapp", {"remote_jid": remote_jid})
    return vinculo["cpf"] if vinculo and "cpf" in vinculo else None
