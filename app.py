import os
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console

load_dotenv()

# MegaAPI credentials
MEGAAPI_URL = os.getenv("MEGAAPI_URL")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

# Mistral credentials
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID")

app = Flask(__name__)


console = Console(
    color_system="truecolor",
    style="bold",
    emoji=True, 
)

def send_to_mistral(user_message):
    url = "https://api.mistral.ai/v1/agents/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "agent_id": MISTRAL_AGENT_ID,
        "messages": [
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "text"}
    }
    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        console.log(f"[red]Erro na requisição para Mistral: {e}")
        rprint(response.text)
        raise
    return response.json()["choices"][0]["message"]["content"]

def send_whatsapp_message(phone, message, max_retries=3, timeout=10):
    """
    Envia mensagem via MegaAPI. O campo 'to' deve ser apenas o número puro para chat individual, e terminar com @g.us para grupos.
    """
    # Log detalhado das variáveis de ambiente e payload
    console.log(f"[magenta]MEGAAPI_URL: {MEGAAPI_URL}")
    console.log(f"[magenta]INSTANCE_KEY: {INSTANCE_KEY}")
    console.log(f"[magenta]MEGAAPI_KEY: {MEGAAPI_KEY[:6]}... (ocultado)")
    # Garante que não há sufixo para chat individual
    if phone.endswith("@s.whatsapp.net"):
        phone = phone.replace("@s.whatsapp.net", "")
    payload = {
        "to": phone,  # Exemplo: "5511970364501" (apenas número puro)
        "text": message
    }
    console.log(f"[magenta]Payload: {payload}")
    url = f"{MEGAAPI_URL}/rest/sendMessage/{INSTANCE_KEY}/text"
    headers = {
        "Authorization": f"Bearer {MEGAAPI_KEY}",
        "Content-Type": "application/json"
    }
    console.log(f"[cyan]Enviando requisição para MegaAPI: {payload}")
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.log(f"[red]Tentativa {attempt} - Erro ao enviar mensagem via MegaAPI: {e}")
            if attempt == max_retries:
                rprint(response.text if 'response' in locals() else str(e))
                raise
            time.sleep(2)  # Espera 2 segundos antes de tentar novamente

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    console.rule("[bold green]Webhook Recebido")
    rprint(data)

    # Ignora mensagens enviadas pelo próprio bot, grupo ou broadcast
    if data.get("fromMe") or data.get("key", {}).get("fromMe") or data.get("isGroup") or data.get("broadcast"):
        console.log("[yellow] Ignorando mensagem enviada pelo próprio bot, grupo ou broadcast.")
        return jsonify({"status": "ignored"})

    # Extrai o número do usuário (remoteJid)
    remote_jid = data.get("remoteJid") or data.get("key", {}).get("remoteJid")
    phone = None
    if remote_jid:
        phone_original = remote_jid
        phone = remote_jid.split("@")[0]
        phone = "".join(filter(str.isdigit, phone))
        console.log(f"[yellow]Telefone original: {phone_original} | Telefone extraído: {phone}")
    else:
        console.log(f"[red]Campo 'remoteJid' não encontrado no payload!")

    user_message = data.get("message", {}).get("extendedTextMessage", {}).get("text")

    # Validação adicional do número (mínimo 10 dígitos)
    if not phone or not user_message or len(phone) < 10:
        console.log(f"[red]Payload inesperado ou número inválido: {data}")
        return jsonify({"error": "Payload inesperado ou número inválido", "payload": data}), 400

    resposta = send_to_mistral(user_message)
    console.log(f"[green]Resposta do agente: {resposta}")
    console.log(f"[cyan]Enviando para MegaAPI: to={phone}, text={resposta}")
    try:
        megaapi_response = send_whatsapp_message(phone, resposta)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok", "megaapi_response": megaapi_response})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)