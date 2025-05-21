from fastapi import FastAPI, Request
from app.agent import processar_mensagem_geovana, fallback_transferencia
from app.utils import extrair_cpf
from app.memory import buscar_cpf_por_remotejid, vincular_cpf_remotejid, buscar_contexto_cliente
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

MEGAAPI_URL = os.getenv("MEGAAPI_URL")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

def extrair_numero_whatsapp(remote_jid: str) -> str:
    return remote_jid.split('@')[0]

@app.post("/webhook/whatsapp")
async def receber_mensagem(req: Request):
    body = await req.json()
    remote_jid = body["key"]["remoteJid"]
    msg = body["message"]["extendedTextMessage"]["text"]
    jid = body["jid"]

    cpf = await buscar_cpf_por_remotejid(remote_jid)
    if not cpf:
        cpf_extraido = extrair_cpf(msg)
        if cpf_extraido:
            await vincular_cpf_remotejid(remote_jid, cpf_extraido)
            cpf = cpf_extraido
        else:
            numero = extrair_numero_whatsapp(remote_jid)
            await httpx.post(
                f"{MEGAAPI_URL}/instance{INSTANCE_KEY}/sendMessage",
                headers={"Authorization": MEGAAPI_KEY},
                json={
                    "chatId": numero,
                    "text": "Olá! Para continuar, por favor, informe seu CPF (apenas números)."
                }
            )
            return {"status": "aguardando_cpf"}

    contexto = await buscar_contexto_cliente(cpf)
    resposta = await processar_mensagem_geovana(msg, contexto)
    numero = extrair_numero_whatsapp(remote_jid)

    await httpx.post(
        f"{MEGAAPI_URL}/instance{INSTANCE_KEY}/sendMessage",
        headers={"Authorization": MEGAAPI_KEY},
        json={
            "chatId": numero,
            "text": resposta
        }
    )
    return {"status": "ok"}