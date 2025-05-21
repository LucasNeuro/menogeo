from fastapi import FastAPI, Request, HTTPException
import logging

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/webhook/megaapi")
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
    return {"status": "received"} 