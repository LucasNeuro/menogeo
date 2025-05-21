import os
import requests
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
    emoji=True
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

def send_whatsapp_message(phone, message):
    url = f"{MEGAAPI_URL}/rest/sendMessage/{INSTANCE_KEY}/text"
    headers = {
        "Authorization": f"Bearer {MEGAAPI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": phone,
        "text": message
    }
    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        console.log(f"[red]Erro ao enviar mensagem via MegaAPI: {e}")
        rprint(response.text)
        raise
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    console.rule("[bold green]Webhook Recebido")
    rprint(data)

    # Extrai o telefone e a mensagem do payload real
    phone = data.get("jid")
    if phone:
        # Remove o sufixo e mantém só os dígitos
        phone = phone.split("@")[0]
        phone = "".join(filter(str.isdigit, phone))
    user_message = data.get("message", {}).get("extendedTextMessage", {}).get("text")

    if not phone or not user_message:
        console.log(f"[red]Payload inesperado: {data}")
        return jsonify({"error": "Payload inesperado", "payload": data}), 400

    # 1. Envia mensagem para o agente Mistral
    resposta = send_to_mistral(user_message)
    console.log(f"[green]Resposta do agente: {resposta}")
    # 2. Responde no WhatsApp via MegaAPI
    send_whatsapp_message(phone, resposta)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)