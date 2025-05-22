import os
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
import pprint
import json
import redis

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

PROMPT = (
    "Você é Geovana, agente virtual oficial da G4 Telecom.\n"
    "- Sempre que receber um CPF do usuário, chame imediatamente a função consultar_dados_ixc passando o CPF.\n"
    "- Use SEMPRE os dados retornados do IXC para responder conforme a intenção do usuário, buscando nos campos do JSON: cliente, boletos, contratos, login, OS.\n"
    "- Identifique as intenções do usuário (consulta_boleto, consulta_status_plano, estou_sem_internet, consulta_dados_cadastro, consulta_valor_plano, etc.) e responda de acordo, usando os dados reais do IXC.\n"
    "- Personalize as respostas usando o nome do cliente, status do contrato, valores, datas, etc.\n"
    "- Não repita cumprimentos ou apresentações em todas as respostas.\n"
    "- Se precisar abrir uma ordem de serviço, use a função abrir_os.\n"
    "- Se precisar transferir para um atendente humano, use a função transferir_para_humano.\n"
    "- Responda de forma clara, cordial, com listas, tópicos em negrito e poucos emojis, adaptando para leitura no WhatsApp.\n"
    "- Nunca envie informações não solicitadas e só peça dados ao backend se realmente necessário.\n"
    "- Se não conseguir resolver, oriente o usuário a falar com um atendente humano.\n"
    "\n"
    "Exemplos de respostas personalizadas usando dados do IXC:\n"
    "- Para consulta de boleto: 'Olá, {nome_cliente}! Seu boleto de R$ {valor} vence em {data_vencimento}. Segue o link para pagamento: {url_pdf}. Se precisar do código de barras: {linha_digitavel}'\n"
    "- Para status do plano: 'Seu plano está {status_contrato} e sua internet está {status_internet}. Última conexão: {ultima_conexao_inicial}. Se precisar de suporte, posso abrir uma ordem de serviço.'\n"
    "- Para consulta de cadastro: 'Seus dados cadastrais: Nome: {nome_cliente}, Telefone: {telefone}, Endereço: {endereco}, Status: {status}'\n"
    "- Sempre use os dados reais do IXC para responder, nunca invente informações.\n"
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
            "name": "consultar_boletos",
            "description": "Consulta os boletos do cliente no IXC a partir do CPF.",
            "parameters": {
                "cpf": {"type": "string", "description": "CPF do cliente"}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_status_plano",
            "description": "Consulta o status do plano do cliente no IXC a partir do CPF.",
            "parameters": {
                "cpf": {"type": "string", "description": "CPF do cliente"}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_dados_cadastro",
            "description": "Consulta os dados cadastrais do cliente no IXC a partir do CPF.",
            "parameters": {
                "cpf": {"type": "string", "description": "CPF do cliente"}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_valor_plano",
            "description": "Consulta o valor do plano do cliente no IXC a partir do CPF.",
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
            "name": "transferir_para_humano",
            "description": "Transfere o atendimento para um humano e envia um resumo do atendimento para o webhook Make.com.",
            "parameters": {
                "cpf": {"type": "string", "description": "CPF do cliente"},
                "resumo": {"type": "string", "description": "Resumo da conversa"}
            }
        }
    }
]

# Configuração do Redis via .env
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_USERNAME = os.getenv("REDIS_USERNAME", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_TTL = int(os.getenv("REDIS_TTL", 1800))  # 30 minutos padrão

redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    username=REDIS_USERNAME,
    db=REDIS_DB,
    decode_responses=True
)

def get_namespace(remoteJid, cpf):
    return f"conversa:{remoteJid}:{cpf}:"

# Função para salvar dados do IXC com TTL
def salvar_ixc(remoteJid, cpf, dados_ixc):
    key = get_namespace(remoteJid, cpf) + "ixc"
    redis_client.setex(key, REDIS_TTL, json.dumps(dados_ixc))
    salvar_log(remoteJid, cpf, f"[LOG] Dados IXC salvos no cache: {json.dumps(dados_ixc, ensure_ascii=False)}")

def buscar_ixc(remoteJid, cpf):
    key = get_namespace(remoteJid, cpf) + "ixc"
    valor = redis_client.get(key)
    if valor:
        salvar_log(remoteJid, cpf, f"[LOG] Dados IXC recuperados do cache.")
        return json.loads(valor)
    return None

# Função para salvar histórico da conversa (append)
def salvar_historico(remoteJid, cpf, mensagem):
    key = get_namespace(remoteJid, cpf) + "historico"
    redis_client.rpush(key, json.dumps(mensagem))
    salvar_log(remoteJid, cpf, f"[LOG] Mensagem adicionada ao histórico: {json.dumps(mensagem, ensure_ascii=False)}")

def buscar_historico(remoteJid, cpf):
    key = get_namespace(remoteJid, cpf) + "historico"
    return [json.loads(m) for m in redis_client.lrange(key, 0, -1)]

# Função para salvar logs (append)
def salvar_log(remoteJid, cpf, log):
    key = get_namespace(remoteJid, cpf) + "logs"
    redis_client.rpush(key, log)

def buscar_logs(remoteJid, cpf):
    key = get_namespace(remoteJid, cpf) + "logs"
    return redis_client.lrange(key, 0, -1)

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

def consultar_dados_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc(remoteJid, cpf)
        if cache:
            print(f"[LOG] Usando dados do IXC do cache para CPF {cpf}")
            return cache
    payload = {"cpf": cpf}
    try:
        response = requests.post(IXC_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print("[LOG] Dados retornados do IXC para CPF", cpf, ":", json.dumps(data, ensure_ascii=False, indent=2))
        if remoteJid:
            salvar_ixc(remoteJid, cpf, data)
        return data
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

def is_cpf(text):
    return isinstance(text, str) and text.isdigit() and len(text) == 11

def processar_mensagem_usuario(remoteJid, message, messages, logs=None):
    # Detecta se é um CPF válido
    if is_cpf(message):
        # Busca no Redis
        dados_ixc = buscar_ixc(remoteJid, message)
        if not dados_ixc:
            dados_ixc = consultar_dados_ixc(message)
            salvar_ixc(remoteJid, message, dados_ixc)
        # Log detalhado
        print(f"[LOG] Dados IXC retornados para CPF {message}: {dados_ixc}")
        # Salva histórico e logs
        salvar_historico(remoteJid, message, {"role": "user", "content": message})
        salvar_log(remoteJid, message, f"[LOG] Mensagem processada: {message}")
        return True  # Indica que processou CPF
    return False

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        logs = []  # Corrige o erro de variável não definida
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

        # Detecta e processa CPF
        cpf_processado = processar_mensagem_usuario(remote_jid, user_message, messages, logs)
        # Se processou CPF, já adicionou os dados ao contexto
        # Agora envia para o Mistral normalmente
        result = call_mistral(messages, tools)
        print("[LOG] Resposta do Mistral:")
        pprint.pprint(result)
        # Loop para processar tool_calls até o agente não pedir mais nenhuma
        while result and "choices" in result and result["choices"] and result["choices"][0]["message"].get("tool_calls"):
            for tool_call in result["choices"][0]["message"]["tool_calls"]:
                print("[LOG] Tool call recebida:", tool_call)
                tool_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                if tool_name == "consultar_dados_ixc":
                    tool_result = consultar_dados_ixc(args["cpf"], remote_jid)
                elif tool_name == "consultar_boletos":
                    tool_result = consultar_boletos_ixc(args["cpf"])
                elif tool_name == "consultar_status_plano":
                    tool_result = consultar_status_plano_ixc(args["cpf"])
                elif tool_name == "consultar_dados_cadastro":
                    tool_result = consultar_dados_cadastro_ixc(args["cpf"])
                elif tool_name == "consultar_valor_plano":
                    tool_result = consultar_valor_plano_ixc(args["cpf"])
                elif tool_name == "transferir_para_humano":
                    tool_result = transferir_para_humano(args["cpf"], args["resumo"])
                elif tool_name == "abrir_os":
                    tool_result = abrir_os(args["id_cliente"], args["motivo"])
                else:
                    tool_result = {"erro": "Tool não implementada"}
                print("[LOG] Resultado da tool:", tool_result)
                # Adiciona o resultado da tool ao histórico como mensagem de tool_call
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
                salvar_historico(remote_jid, args.get("cpf", phone), {
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
                salvar_log(remote_jid, args.get("cpf", phone), f"[LOG] Tool {tool_name} chamada com resultado: {tool_result}")
            # Nova chamada ao Mistral com o histórico atualizado
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
    except Exception as e:
        console.log(f"[red]Erro inesperado no webhook: {e}")
        return jsonify({"error": str(e)}), 500

# Nova tool: consultar_boletos

def consultar_boletos_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(f"{IXC_API_URL}/consultarBoletos", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao consultar boletos"}
    except Exception as e:
        return {"erro": str(e)}

# Nova tool: consultar_status_plano

def consultar_status_plano_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(f"{IXC_API_URL}/consultarStatusPlano", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao consultar status do plano"}
    except Exception as e:
        return {"erro": str(e)}

# Nova tool: consultar_dados_cadastro

def consultar_dados_cadastro_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(f"{IXC_API_URL}/consultarDadosCadastro", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao consultar dados cadastrais"}
    except Exception as e:
        return {"erro": str(e)}

# Nova tool: consultar_valor_plano

def consultar_valor_plano_ixc(cpf):
    payload = {"cpf": cpf}
    try:
        response = requests.post(f"{IXC_API_URL}/consultarValorPlano", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao consultar valor do plano"}
    except Exception as e:
        return {"erro": str(e)}

# Nova tool: transferir_para_humano

def transferir_para_humano(cpf, resumo):
    payload = {
        "cpf": cpf,
        "resumo": resumo
    }
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        return {"status": "ok", "mensagem": "Transferência para humano solicitada."}
    except requests.exceptions.Timeout:
        return {"erro": "Timeout ao transferir para humano"}
    except Exception as e:
        return {"erro": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)