import os
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
import pprint

load_dotenv()

# MegaAPI credentials
MEGAAPI_URL = os.getenv("MEGAAPI_URL")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

# Mistral credentials
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID")
MISTRAL_URL = "https://api.mistral.ai/v1/agents/completions"

IXC_API_URL = os.getenv("IXC_API_URL", "https://n8n.rafaeltoshiba.com.br/webhook/ixc/consultaCliente")

app = Flask(__name__)

console = Console(
    color_system="truecolor",
    style="bold",
    emoji=True, 
)



tools = [
    {
        "type": "function",
        "function": {
            "name": "consultar_dados_ixc",
            "description": "Consulta todos os dados do cliente no IXC a partir do CPF.",
            "parameters": {
                "cpf": {"type": "string", "description": "CPF do cliente"}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_os",
            "description": "Abre uma ordem de serviço para o cliente.",
            "parameters": {
                "id_cliente": {"type": "string", "description": "ID do cliente"},
                "motivo": {"type": "string", "description": "Motivo da OS"}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "encaminhar_humano",
            "description": "Transfere o atendimento para um humano.",
            "parameters": {
                "id_cliente": {"type": "string", "description": "ID do cliente"},
                "resumo": {"type": "string", "description": "Resumo da conversa"}
            }
        }
    }
]

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
    O payload deve ser enviado dentro de 'messageData', conforme documentação MegaAPI.
    """
    console.log(f"[magenta]MEGAAPI_URL: {MEGAAPI_URL}")
    console.log(f"[magenta]INSTANCE_KEY: {INSTANCE_KEY}")
    console.log(f"[magenta]MEGAAPI_KEY: {MEGAAPI_KEY[:6]}... (ocultado)")
    if phone.endswith("@s.whatsapp.net"):
        phone = phone.replace("@s.whatsapp.net", "")
    payload = {
        "messageData": {
            "to": phone,
            "text": message,
            "linkPreview": False
        }
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

# Função para validar CPF

def validar_cpf(cpf):
    payload = {"cpf": cpf}
    url = f"{IXC_API_URL}/validarCpf"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

# Função para consultar cliente

def consultar_cliente(cpf):
    payload = {"cpf": cpf}
    url = f"{IXC_API_URL}/consultarCliente"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

# Função para consultar contratos ativos

def consultar_contratos(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarContratos"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

# Função para consultar boletos

def consultar_boletos(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarBoletos"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

# Função para consultar status do plano

def consultar_status_plano(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarStatusPlano"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_dados_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(IXC_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao consultar IXC"}
    except Exception as e:
        return {"erro": str(e)}

def abrir_os(id_cliente, motivo):
    payload = {"id_cliente": id_cliente, "motivo": motivo}
    url = f"{IXC_API_URL}/abrirOS"
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao abrir OS"}
    except Exception as e:
        return {"erro": str(e)}

def encaminhar_humano(id_cliente, resumo):
    payload = {"id_cliente": id_cliente, "resumo": resumo}
    url = f"{IXC_API_URL}/encaminharHumano"
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao encaminhar para humano"}
    except Exception as e:
        return {"erro": str(e)}

def call_mistral(messages, tools=None):
    payload = {
        "agent_id": MISTRAL_AGENT_ID,
        "messages": messages,
        "tools": tools,
        "response_format": {"type": "text"},
        "max_tokens": 500,
        "presence_penalty": 0.5,
        "frequency_penalty": 0.5,
        "parallel_tool_calls": True
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(MISTRAL_URL, headers=headers, json=payload)
    return response.json()

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

    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": user_message}
    ]
    print("\n[LOG] Enviando para Mistral:")
    pprint.pprint(messages)
    result = call_mistral(messages, tools)
    print("[LOG] Resposta do Mistral:")
    pprint.pprint(result)
    # Loop para processar tool_calls até o agente não pedir mais nenhuma
    while "tool_calls" in result and result["tool_calls"]:
        for tool_call in result["tool_calls"]:
            print("[LOG] Tool call recebida:", tool_call)
            tool_name = tool_call["name"]
            args = tool_call["arguments"]
            if tool_name == "consultar_dados_ixc":
                tool_result = consultar_dados_ixc(args["cpf"])
            elif tool_name == "abrir_os":
                tool_result = abrir_os(args["id_cliente"], args["motivo"])
            elif tool_name == "encaminhar_humano":
                tool_result = encaminhar_humano(args["id_cliente"], args["resumo"])
            else:
                tool_result = {"erro": "Tool não implementada"}
            print("[LOG] Resultado da tool:", tool_result)
            messages.append({
                "role": "function",
                "name": tool_name,
                "content": str(tool_result)
            })
        result = call_mistral(messages, tools)
        print("[LOG] Nova resposta do Mistral após tool_call:")
        pprint.pprint(result)
    print("[LOG] Resposta final do agente:", result)
    # Extrai a resposta final do Mistral
    final_response = None
    if result and "choices" in result and result["choices"]:
        final_response = result["choices"][0]["message"]["content"]
    if final_response:
        send_whatsapp_message(phone, final_response)
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)