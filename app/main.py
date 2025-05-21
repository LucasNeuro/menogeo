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
    # Validação básica do payload
    if not isinstance(payload, dict) or 'event' not in payload or 'data' not in payload:
        raise HTTPException(status_code=400, detail="Payload inválido: faltando 'event' ou 'data'.")
    data = payload['data']
    required_fields = ['from', 'to', 'body']
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Payload inválido: faltando campo '{field}' em 'data'.")
    logging.info(f"Webhook MegaAPI recebido: event={payload['event']}, from={data['from']}, to={data['to']}, body={data['body']}")
    # Enviar resposta automática
    resposta = await enviar_mensagem_whatsapp(data['from'], "Recebido com sucesso!")
    logging.info(f"Resposta enviada: {resposta}")
    return {"status": "received", "resposta": resposta} 