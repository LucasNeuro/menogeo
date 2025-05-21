from fastapi import FastAPI, Request, HTTPException
import logging
import os
import httpx
import json
from pprint import pformat

app = FastAPI()

MEGAAPI_URL = os.getenv("MEGAAPI_URL", "https://apibusiness1.megaapi.com.br")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

async def enviar_mensagem_whatsapp(numero, texto):
    url = f"{MEGAAPI_URL}/rest/sendMessage/{INSTANCE_KEY}/text"
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {MEGAAPI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messageData": {
            "to": numero,
            "text": texto,
            "linkPreview": False
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/webhook/whatsapp")
async def megaapi_webhook(request: Request):
    raw_body = await request.body()
    logging.info(f"Corpo cru recebido: {raw_body}")
    try:
        payload = await request.json()
    except Exception as e:
        logging.warning(f"Falha ao decodificar JSON: {e}")
        payload = None
    logging.info(f"Tipo do payload: {type(payload)}, valor: {payload}")
    # Log detalhado do payload
    logging.info("Payload bruto recebido:\n" + pformat(payload))
    numero = None
    texto_recebido = None
    # Tentar extrair de diferentes formatos
    if isinstance(payload, dict):
        if 'data' in payload and isinstance(payload['data'], dict):
            data = payload['data']
            numero = data.get('from') or data.get('to')
            texto_recebido = data.get('body')
            # Tentar extrair do remoteJid
            if not numero and 'key' in data and isinstance(data['key'], dict):
                remote_jid = data['key'].get('remoteJid')
                if remote_jid and remote_jid.endswith('@s.whatsapp.net'):
                    numero = remote_jid.replace('@s.whatsapp.net', '')
        elif 'messageData' in payload and isinstance(payload['messageData'], dict):
            msg_data = payload['messageData']
            numero = msg_data.get('from') or msg_data.get('to')
            texto_recebido = msg_data.get('text')
            # Tentar extrair do remoteJid
            if not numero and 'key' in msg_data and isinstance(msg_data['key'], dict):
                remote_jid = msg_data['key'].get('remoteJid')
                if remote_jid and remote_jid.endswith('@s.whatsapp.net'):
                    numero = remote_jid.replace('@s.whatsapp.net', '')
    if numero:
        resposta = await enviar_mensagem_whatsapp(numero, "Recebido com sucesso!")
        logging.info(f"Resposta enviada: {resposta}")
        return {"status": "received", "resposta": resposta}
    else:
        logging.warning("Não foi possível identificar o número para resposta.")
        return {"status": "received", "detalhe": "Número não identificado no payload."} 