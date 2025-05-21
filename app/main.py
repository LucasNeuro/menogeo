from fastapi import FastAPI, Request
from app.agent import GEOVANA
from app.utils import extrair_cpf
from app.memory import buscar_cpf_por_remotejid, vincular_cpf_remotejid
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

MEGAAPI_URL = os.getenv("MEGAAPI_URL")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

@app.post("/webhook/whatsapp")
async def receber_mensagem(req: Request):
    body = await req.json()
    # Extrai remoteJid corretamente do payload MegaAPI
    remote_jid = body["key"]["remoteJid"]
    msg = body["message"]["extendedTextMessage"]["text"]
    jid = body["jid"]

    # Busca CPF vinculado ao remoteJid
    cpf = await buscar_cpf_por_remotejid(remote_jid)
    if not cpf:
        # Tenta extrair CPF da mensagem
        cpf_extraido = extrair_cpf(msg)
        if cpf_extraido:
            await vincular_cpf_remotejid(remote_jid, cpf_extraido)
            cpf = cpf_extraido
        else:
            # Pede o CPF ao cliente
            await httpx.post(
                f"{MEGAAPI_URL}/instance{INSTANCE_KEY}/sendMessage",
                headers={"Authorization": MEGAAPI_KEY},
                json={
                    "chatId": jid,
                    "text": "Olá! Para continuar, por favor, informe seu CPF (apenas números)."
                }
            )
            return {"status": "aguardando_cpf"}

    resposta = await GEOVANA.run(input=msg, context={"cpf": cpf})

    await httpx.post(
        f"{MEGAAPI_URL}/instance{INSTANCE_KEY}/sendMessage",
        headers={"Authorization": MEGAAPI_KEY},
        json={
            "chatId": jid,
            "text": resposta.output
        }
    )
    return {"status": "ok"}