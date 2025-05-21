from fastapi import FastAPI, Request, HTTPException
import logging
import os
import httpx

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
    payload = await request.json()
    logging.info(f"Payload bruto recebido: {payload}")
    # Tentar identificar o número para resposta
    numero = None
    texto_recebido = None
    if isinstance(payload, dict):
        if 'data' in payload and isinstance(payload['data'], dict):
            numero = payload['data'].get('from') or payload['data'].get('to')
            texto_recebido = payload['data'].get('body')
        elif 'messageData' in payload and isinstance(payload['messageData'], dict):
            numero = payload['messageData'].get('from') or payload['messageData'].get('to')
            texto_recebido = payload['messageData'].get('text')
    if numero:
        resposta = await enviar_mensagem_whatsapp(numero, "Recebido com sucesso!")
        logging.info(f"Resposta enviada: {resposta}")
        return {"status": "received", "resposta": resposta}
    else:
        logging.warning("Não foi possível identificar o número para resposta.")
        return {"status": "received", "detalhe": "Número não identificado no payload."} 