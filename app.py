import os
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from mem0_utils import save_context_mem0, get_context_mem0

load_dotenv()

# MegaAPI credentials
MEGAAPI_URL = os.getenv("MEGAAPI_URL")
MEGAAPI_KEY = os.getenv("MEGAAPI_KEY")
INSTANCE_KEY = os.getenv("INSTANCE_KEY")

# Mistral credentials
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID")

# IXC API URL
IXC_API_URL = os.getenv("IXC_API_URL")

app = Flask(__name__)

console = Console(
    color_system="truecolor",
    style="bold",
    emoji=True, 
)

def send_to_mistral(user_message, context=None):
    url = "https://api.mistral.ai/v1/agents/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    # Lista de tools (funções) disponíveis para o agente
    tools = [
        {
            "type": "function",
            "function": {
                "name": "consultar_boletos",
                "description": "Retorna os próximos boletos do cliente, status do contrato e login.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente, incluindo boletos, contratos, etc."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_status_plano",
                "description": "Retorna status do contrato, internet, desbloqueio confiança, observações e login.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente, incluindo contratos, login, etc."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "estou_sem_internet",
                "description": "Diagnostica problemas de conexão do cliente e executa checklist antes de encaminhar para humano.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente, incluindo contratos, login, OS, boletos, etc."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consulta_dados_cadastro",
                "description": "Retorna dados cadastrais e endereço do cliente.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente, incluindo dados cadastrais e contratos."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consulta_valor_plano",
                "description": "Retorna nome do plano, valor, status do contrato e login.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente, incluindo contratos, boletos e login."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fazer_contrato",
                "description": "Cria um lead para novo contrato no CRM.",
                "parameters": {
                    "dados_iniciais": {"type": "object", "description": "Dados iniciais do cliente para criar o lead."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "registrar_feedback",
                "description": "Registra reclamação, elogio ou motivo de falar com atendente.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente."},
                    "motivo": {"type": "string", "description": "Motivo do feedback."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "encaminhar_humano",
                "description": "Encaminha para atendimento humano.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente."},
                    "motivo": {"type": "string", "description": "Motivo do encaminhamento."}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "abrir_os",
                "description": "Abre uma ordem de serviço para o cliente.",
                "parameters": {
                    "contexto_cliente": {"type": "object", "description": "Contexto completo do cliente."},
                    "motivo": {"type": "string", "description": "Motivo da abertura da OS."}
                }
            }
        }
    ]
    # Monta as mensagens, incluindo o contexto do cliente se disponível
    messages = [
        {"role": "system", "content": "Você é Geovana, agente virtual oficial da G4 Telecom. Use sempre as ferramentas disponíveis para buscar dados reais do cliente antes de responder. Siga o checklist de diagnóstico antes de encaminhar para atendimento humano. Formate as respostas para WhatsApp, com listas, tópicos em negrito e poucos emojis. Nunca repita informações desnecessárias ou peça dados já informados pelo cliente. Se não souber a intenção, peça para o usuário explicar melhor. Se identificar intenção crítica, use a ferramenta de encaminhamento humano. Nunca envie informações não solicitadas."},
        {"role": "user", "content": user_message}
    ]
    if context:
        messages.append({"role": "user", "content": f"[contexto_cliente]: {context}"})
    payload = {
        "agent_id": MISTRAL_AGENT_ID,
        "messages": messages,
        "tools": tools,
        "response_format": {"type": "text"},
        "max_tokens": 500
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

def buscar_dados_ixc(cpf):
    payload = {"cpf": cpf}
    response = requests.post(IXC_API_URL, json=payload)
    response.raise_for_status()
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    console.rule("[bold green]Webhook Recebido")
    rprint(data)

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

    # Tenta buscar contexto do cliente na memória (Mem0) usando o telefone como chave
    context = get_context_mem0(phone) if phone else None

    # Se não houver contexto, pede o CPF ao usuário
    if not context:
        send_whatsapp_message(phone, "Por favor, me informe seu CPF para localizar seus dados.")
        return jsonify({"status": "aguardando_cpf"})

    # Se a mensagem for um CPF válido, busca dados no IXC_API e salva no Mem0
    if user_message and len(user_message) >= 11 and user_message.isdigit():
        cpf = user_message
        try:
            dados_ixc = buscar_dados_ixc(cpf)
            save_context_mem0(cpf, dados_ixc)
            send_whatsapp_message(phone, "Dados localizados! Como posso te ajudar?")
            return jsonify({"status": "contexto_salvo"})
        except Exception as e:
            send_whatsapp_message(phone, "Não consegui localizar seus dados. Por favor, confira o CPF informado.")
            return jsonify({"error": str(e)}), 400

    # Aqui segue o fluxo normal, usando o contexto já carregado
    resposta = send_to_mistral(user_message, context)
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