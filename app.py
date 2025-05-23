import os
from mem0 import MemoryClient
import requests
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
import pprint
import json
import redis
from threading import Thread
import uuid
import requests as req_deepseek
import re

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

DEPSEEK_API_KEY = os.getenv("DEPSEEK_API_KEY")
DEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

app = Flask(__name__)

console = Console(
    color_system="truecolor",
    style="bold",
    emoji=True, 
)

PROMPT = (
    "Você é Geovana, agente virtual oficial da G4 Telecom.\n"
    "- Sempre cumprimente o cliente pelo nome (do IXC) no início da conversa ou em mudanças de assunto, mas nunca mais de uma vez por conversa.\n"
    "- Só peça o CPF se não houver no contexto (Redis).\n"
    "- Se já houver dados do IXC no Redis, use-os para responder, sem pedir novamente.\n"
    "- Só responda com informações de boleto, status de plano, cadastro, etc, se o usuário pedir explicitamente.\n"
    "- Use o histórico da conversa para manter o contexto e responder de forma natural e humana.\n"
    "- Se o usuário interromper um fluxo e voltar, retome o assunto anterior de forma cordial.\n"
    "- Sempre sugira próximos passos ao final de cada atendimento (ex: 'Posso te ajudar com mais alguma coisa, {nome_cliente}?').\n"
    "- Identifique as intenções do usuário (consulta_boleto, consulta_status_plano, estou_sem_internet, consulta_dados_cadastro, consulta_valor_plano, etc.) e responda de acordo, usando os dados reais do IXC.\n"
    "- Personalize as respostas usando o nome do cliente, status do contrato, valores, datas, etc.\n"
    "- Nunca repita cumprimentos ou o nome do cliente mais de uma vez por resposta.\n"
    "- Nunca envie informações não solicitadas. Só responda à intenção atual detectada.\n"
    "- Nunca misture dados ou respostas de outras intenções.\n"
    "- Se precisar abrir uma ordem de serviço, use a função abrir_os.\n"
    "- Se precisar transferir para um atendente humano, use a função transferir_para_humano e gere um resumo do atendimento para o humano.\n"
    "- Responda de forma clara, cordial, com listas, tópicos em negrito e poucos emojis, adaptando para leitura no WhatsApp.\n"
    "- Nunca envie informações não solicitadas e só peça dados ao backend se realmente necessário.\n"
    "- Se não conseguir resolver, oriente o usuário a falar com um atendente humano.\n"
    "- Ao final de cada atendimento, sempre sugira de forma cordial o que o cliente pode fazer a seguir, como: 'Posso te ajudar com mais alguma coisa, {nome_cliente}?'.\n"
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

# Configuração do Mem0AI
os.environ["MEM0_API_KEY"] = os.getenv("MEM0_API_KEY")
mem0_client = MemoryClient()

# Configuração do Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)

# Helpers para cache IXC no Redis
REDIS_TTL_IXC = 60 * 30  # 30 minutos

# Helpers para contexto de CPF

def get_cpf_from_context(remoteJid):
    key = f"conversa:{remoteJid}:cpf"
    cpf = redis_client.get(key)
    if cpf and is_cpf(cpf):
        return cpf
    return None

def salvar_cpf_contexto(remoteJid, cpf):
    if is_cpf(cpf):
        key = f"conversa:{remoteJid}:cpf"
        redis_client.setex(key, REDIS_TTL_IXC, cpf)

# Função para garantir que o CPF está no contexto antes de qualquer consulta
# Se não estiver, retorna None e a função chamadora deve lidar com isso

def garantir_cpf_contexto(remoteJid, user_message=None):
    cpf = get_cpf_from_context(remoteJid)
    if cpf:
        return cpf
    if user_message and is_cpf(user_message):
        salvar_cpf_contexto(remoteJid, user_message)
        return user_message
    return None

def get_namespace(remoteJid, cpf):
    return f"conversa:{remoteJid}:{cpf}:"

def processar_mensagem_usuario(remoteJid, message, messages, logs=None):
    # Detecta se é um CPF válido
    if is_cpf(message):
        # Salva o CPF no contexto
        salvar_cpf_contexto(remoteJid, message)
        # Busca no Redis
        dados_ixc = buscar_ixc_redis(remoteJid, message)
        if not dados_ixc:
            dados_ixc = consultar_dados_ixc(message, remoteJid)
            salvar_ixc_redis(remoteJid, message, dados_ixc)
        print(f"[LOG] Dados IXC retornados para CPF {message}: {dados_ixc}")
        # Salva apenas a mensagem do usuário no histórico Mem0AI
        salvar_historico_mem0(remoteJid, message, {"role": "user", "content": message})
        return True
    return False

# Função para classificar intenção e extrair entidades
# Retorna: {"intencao": ..., "entidades": {...}}
def classificar_intencao_deepseek(mensagem_usuario):
    prompt = (
        "Classifique a intenção da mensagem do usuário e extraia entidades relevantes.\n"
        "Responda em JSON no formato: {\"intencao\": <string>, \"entidades\": <dict>}\n"
        "Exemplos de intenções: consulta_boleto, suporte_internet, consulta_status_plano, consulta_cadastro, consulta_valor_plano, elogio, reclamacao, saudacao, despedida, outros.\n"
        f"Mensagem: {mensagem_usuario}"
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Você é um classificador de intenções para atendimento ao cliente."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 200
    }
    headers = {
        "Authorization": f"Bearer {DEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = req_deepseek.post(DEPSEEK_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            # Tenta converter para dict
            import json as _json
            return _json.loads(content)
    except Exception as e:
        print(f"[DeepSeek][ERRO] Falha ao classificar intenção: {str(e)}")
    return {"intencao": "outros", "entidades": {}}

# --- FLAG DE CUMPRIMENTO NO REDIS ---
CUMPRIMENTO_TTL = 60 * 60 * 6  # 6 horas (ajuste conforme necessário)

def cumprimentou_cliente(remoteJid):
    key = f"conversa:{remoteJid}:cumprimentou"
    return redis_client.get(key) == "1"

def setar_cumprimento_cliente(remoteJid):
    key = f"conversa:{remoteJid}:cumprimentou"
    redis_client.setex(key, CUMPRIMENTO_TTL, "1")

@app.route("/webhook", methods=["POST"])
def webhook():
    intencao = None  # valor padrão
    entidades = {}
    try:
        data = request.json
        logs = []
        console.rule("[bold green]Webhook Recebido")
        rprint(data)
        console.log(f"[LOG] Payload recebido: {json.dumps(data, ensure_ascii=False)}")

        if data.get("fromMe") or data.get("key", {}).get("fromMe") or data.get("isGroup") or data.get("broadcast"):
            console.log("[yellow] Ignorando mensagem enviada pelo próprio bot, grupo ou broadcast.")
            return jsonify({"status": "ignored"})

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

        if not phone or not user_message or len(phone) < 10:
            console.log(f"[red]Payload inesperado ou número inválido: {data}")
            return jsonify({"error": "Payload inesperado ou número inválido", "payload": data}), 400

        # Se o usuário informar um CPF válido, consultar e salvar dados do IXC
        if is_cpf(user_message):
            salvar_cpf_contexto(remote_jid, user_message)
            dados_ixc = buscar_ixc_redis(remote_jid, user_message)
            if not dados_ixc:
                dados_ixc = consultar_dados_ixc(user_message, remote_jid)
                salvar_ixc_redis(remote_jid, user_message, dados_ixc)
            console.log(f"[LOG] CPF informado e dados IXC salvos: {user_message} -> {dados_ixc}")

        # Garante que o CPF está no contexto
        cpf_contexto = garantir_cpf_contexto(remote_jid, user_message)
        console.log(f"[LOG] CPF no contexto: {cpf_contexto}")

        if not cpf_contexto:
            console.log(f"[LOG] CPF não encontrado no contexto. Solicitando ao usuário.")
            resposta = "Por favor, informe seu CPF (apenas números) para que eu possa te ajudar."
            send_whatsapp_message(phone, resposta)
            return jsonify({"status": "aguardando_cpf"})

        # Buscar dados do IXC do Redis, se não houver, consultar e salvar
        dados_ixc = buscar_ixc_redis(remote_jid, cpf_contexto)
        if not dados_ixc:
            dados_ixc = consultar_dados_ixc(cpf_contexto, remote_jid)
            salvar_ixc_redis(remote_jid, cpf_contexto, dados_ixc)
        console.log(f"[LOG] Dados IXC usados para contexto: {dados_ixc}")

        # Buscar histórico do Mem0AI (apenas user/assistant)
        historico = buscar_historico_mem0(remote_jid, phone)
        console.log(f"[LOG] Histórico Mem0AI retornado: {historico}")

        # Montar contexto para o Mistral
        messages = [{"role": "system", "content": PROMPT}]
        # Adicionar dados do contrato/cliente do Redis ao contexto
        nome_cliente = None
        status_contrato = None
        if dados_ixc and 'cliente' in dados_ixc:
            nome_cliente = dados_ixc['cliente'].get('razao_social') or dados_ixc['cliente'].get('nome')
        if dados_ixc and 'contrato' in dados_ixc:
            status_contrato = dados_ixc['contrato'].get('status')
        contexto_cliente = []
        if nome_cliente:
            contexto_cliente.append(f"O nome do cliente é {nome_cliente}.")
        if status_contrato:
            contexto_cliente.append(f"O status do contrato do cliente é {status_contrato}.")
        if contexto_cliente:
            messages.append({"role": "system", "content": " ".join(contexto_cliente)})
        console.log(f"[LOG] Contexto do cliente adicionado ao Mistral: {contexto_cliente}")

        # Filtrar histórico do Mem0AI: só intenções, sem dados sensíveis
        def is_intent_memory(mem):
            if not isinstance(mem, dict) or not mem.get("memory"): return False
            texto = mem["memory"].lower()
            # Palavras-chave de intenção
            if any(x in texto for x in ["preciso", "quero", "necessito", "estou sem", "reclamação", "elogio", "boleto", "status", "cadastro", "valor do plano", "abrir os", "transferir para humano", "ajuda", "suporte"]):
                # Não pode conter dados sensíveis
                if not any(x in texto for x in ["cpf", "endereço", "address", "contrato", "boleto de r$", "nome", "razao_social", "telefone", "pix", "linha_digitavel", "url_pdf", "gateway_link", "senha", "login", "mac", "ipv4"]):
                    return True
            return False
        # --- NOVO: Só adicionar histórico da mesma intenção ---
        def is_same_intent(mem, intencao):
            if not isinstance(mem, dict) or not mem.get("memory"): return False
            texto = mem["memory"].lower()
            if intencao == "consulta_boleto" and "boleto" in texto:
                return True
            if intencao == "consulta_status_plano" and "status" in texto:
                return True
            if intencao == "estou_sem_internet" and ("sem internet" in texto or "internet" in texto or "conexão" in texto):
                return True
            if intencao == "consulta_dados_cadastro" and ("cadastro" in texto or "dados cadastrais" in texto):
                return True
            if intencao == "consulta_valor_plano" and ("valor do plano" in texto or "mensalidade" in texto):
                return True
            if intencao == "fazer_contrato" and ("contrato" in texto or "assinar" in texto):
                return True
            if intencao in ["reclamar_atendimento", "elogiar_servico", "falar_com_atendente"] and ("reclamação" in texto or "elogio" in texto or "atendente" in texto):
                return True
            return False
        historico_intencoes = []
        if historico and isinstance(historico, dict) and "results" in historico:
            historico_intencoes = [m for m in historico["results"] if is_intent_memory(m) and is_same_intent(m, intencao)]
        elif historico and isinstance(historico, list):
            historico_intencoes = [m for m in historico if is_intent_memory(m) and is_same_intent(m, intencao)]
        # Adicionar intenções ao contexto (apenas da mesma intenção)
        for m in historico_intencoes[-5:]:
            messages.append({"role": "system", "content": m["memory"]})
        # Adicionar histórico user/assistant (últimas 10 interações, sem dados sensíveis, da mesma intenção)
        hist_msgs = []
        if historico and isinstance(historico, dict) and "results" in historico:
            hist_msgs = [m for m in mem0_to_mistral_messages(historico["results"]) if m.get("role") in ("user", "assistant") and is_same_intent(m, intencao)]
        elif historico and isinstance(historico, list):
            hist_msgs = [m for m in mem0_to_mistral_messages(historico) if m.get("role") in ("user", "assistant") and is_same_intent(m, intencao)]
        # Remove duplicidade e pega só as últimas 10
        last_msgs = []
        last_role = None
        for m in hist_msgs[-10:]:
            if last_role == m.get("role") == "user":
                continue  # pula user duplicado
            # Não adiciona mensagens com dados sensíveis
            if any(x in m.get("content", "").lower() for x in ["cpf", "endereço", "address", "contrato", "boleto de r$", "nome", "razao_social", "telefone", "pix", "linha_digitavel", "url_pdf", "gateway_link", "senha", "login", "mac", "ipv4"]):
                continue
            last_msgs.append(m)
            last_role = m.get("role")
        messages.extend(last_msgs)
        if last_role != "user":
            messages.append({"role": "user", "content": user_message})
        print("\n[LOG] Enviando para Mistral:")
        pprint.pprint(messages)
        console.log(f"[LOG] Mensagens enviadas para Mistral: {messages}")

        # Salvar mensagem do usuário no Mem0AI
        salvar_historico_mem0(remote_jid, phone, {"role": "user", "content": user_message})

        # Classificar intenção do usuário
        classificacao = classificar_intencao_deepseek(user_message)
        intencao = classificacao.get("intencao", "outros")
        entidades = classificacao.get("entidades", {})
        print(f"[DeepSeek][MICROAGENTE] Mensagem: {user_message}")
        print(f"[DeepSeek][MICROAGENTE] Intenção detectada: {intencao}")
        print(f"[DeepSeek][MICROAGENTE] Entidades extraídas: {entidades}")
        # Adiciona intenção detectada explicitamente ao contexto do Mistral
        messages.append({
            "role": "system",
            "content": f"A intenção detectada é: {intencao}. Entidades: {json.dumps(entidades, ensure_ascii=False)}"
        })
        # Se for saudação, elogio ou despedida, responder cordialmente
        if intencao in ["saudacao", "elogio", "despedida"]:
            resposta = "Olá! Como posso te ajudar hoje?"
            if intencao == "despedida":
                resposta = "Obrigado pelo contato! Se precisar de algo, estou à disposição."
            send_whatsapp_message(phone, resposta)
            return jsonify({"status": "ok", "intencao": intencao})
        # Se for outros, pedir para ser mais específico
        if intencao == "outros":
            resposta = "Não entendi seu pedido. Pode ser mais específico? Por exemplo: 'quero meu boleto', 'estou sem internet', etc."
            send_whatsapp_message(phone, resposta)
            return jsonify({"status": "ok", "intencao": intencao})
        # Se for intenção clara, seguir fluxo normal (já existente)

        # --- REGRAS DE NEGÓCIO NO BACKEND ---
        # Checagens antes de chamar o Mistral
        resposta_antecipada = None
        if intencao == "consulta_boleto":
            status_contrato = None
            if dados_ixc and 'contrato' in dados_ixc:
                status_contrato = dados_ixc['contrato'].get('status')
            if status_contrato and status_contrato.lower() != 'ativo':
                resposta_antecipada = f"Seu contrato está '{status_contrato}'. Não é possível exibir boletos. Por favor, regularize sua situação ou fale com um atendente."
        elif intencao == "estou_sem_internet":
            status_contrato = None
            status_internet = None
            if dados_ixc and 'contrato' in dados_ixc:
                status_contrato = dados_ixc['contrato'].get('status')
                status_internet = dados_ixc['contrato'].get('status_internet')
            if status_contrato and status_contrato.lower() == 'bloqueado':
                resposta_antecipada = "Seu contrato está bloqueado. Para reativação, regularize seus boletos ou fale com um atendente."
            elif status_internet and status_internet.lower() != 'ativo':
                resposta_antecipada = f"Sua internet está '{status_internet}'. Recomendo falar com o suporte."
        elif intencao == "consulta_valor_plano":
            status_contrato = None
            if dados_ixc and 'contrato' in dados_ixc:
                status_contrato = dados_ixc['contrato'].get('status')
            if status_contrato and status_contrato.lower() != 'ativo':
                resposta_antecipada = f"Seu contrato está '{status_contrato}'. Não é possível exibir o valor do plano."
        # Se houver resposta antecipada, envia e encerra
        if resposta_antecipada:
            resposta_antecipada = limpar_resposta(resposta_antecipada, nome_cliente, intencao)
            send_whatsapp_message(phone, resposta_antecipada)
            console.log(f"[LOG] Mensagem enviada para WhatsApp (regra de negócio): {resposta_antecipada}")
            return jsonify({"status": "regra_negocio", "mensagem": resposta_antecipada})

        # --- CICLO ROBUSTO DE TOOL_CALLS ---
        max_tool_calls = 5
        tool_call_count = 0
        resposta_final = None
        mistral_messages = messages.copy()
        while True:
            result = call_mistral(mistral_messages, tools)
            print("[LOG] Resposta do Mistral:")
            pprint.pprint(result)
            console.log(f"[LOG] Resposta do Mistral recebida: {result}")
            if not result or "choices" not in result or not result["choices"]:
                break
            msg = result["choices"][0]["message"]
            # Se houver tool_calls, executa e adiciona ao contexto
            if msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    # Garante que o CPF passado é sempre o do contexto
                    if "cpf" in tool_args:
                        tool_args["cpf"] = cpf_contexto
                    print(f"[LOG] Tool call recebida: {tool_name} | Args: {tool_args}")
                    # Executa a tool
                    if tool_name == "consultar_dados_ixc":
                        tool_result = consultar_dados_ixc(**tool_args)
                    elif tool_name == "consultar_boletos":
                        tool_result = consultar_boletos_ixc(**tool_args)
                    elif tool_name == "consultar_status_plano":
                        tool_result = consultar_status_plano_ixc(**tool_args)
                    elif tool_name == "consultar_dados_cadastro":
                        tool_result = consultar_dados_cadastro_ixc(**tool_args)
                    elif tool_name == "consultar_valor_plano":
                        tool_result = consultar_valor_plano_ixc(**tool_args)
                    elif tool_name == "abrir_os":
                        tool_result = abrir_os(**tool_args)
                    elif tool_name == "transferir_para_humano":
                        tool_result = transferir_para_humano(**tool_args)
                    else:
                        tool_result = {"erro": f"Tool {tool_name} não implementada"}
                    print("[LOG] Resultado da tool:", tool_result)
                    mistral_messages.append({
                        "role": "assistant",
                        "tool_call_id": tool_call["id"],
                        "content": "",
                        "tool_calls": [tool_call]
                    })
                    mistral_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                tool_call_count += 1
                if tool_call_count >= max_tool_calls:
                    print("[LOG][ERRO] Excesso de tool_calls, encerrando ciclo para evitar loop infinito.")
                    break
                continue  # Chama o Mistral novamente com o novo contexto
            # Se não houver tool_calls, pega a resposta final
            resposta_final = msg.get("content", "")
            # Ignora mensagens de transição
            if resposta_final.strip().lower() in ["estou buscando seus dados...", "aguarde...", "buscando informações..."]:
                print("[LOG] Ignorando mensagem de transição, aguardando resposta final.")
                continue
            break  # Sai do loop quando tiver resposta final útil
        # Cumprimento cordial na primeira resposta útil
        cumprimentou = cumprimentou_cliente(remote_jid)
        if not cumprimentou and nome_cliente and resposta_final:
            if not resposta_final.lower().startswith(f"olá, {nome_cliente.lower()}"):
                resposta_final = f"Olá, {nome_cliente}!\n" + resposta_final.lstrip()
            setar_cumprimento_cliente(remote_jid)
        elif cumprimentou and nome_cliente:
            resposta_final = re.sub(r"olá,?\s*" + re.escape(nome_cliente) + r"[!,\.\s]*", "", resposta_final, flags=re.IGNORECASE)
        resposta_final = limpar_resposta(resposta_final, nome_cliente, intencao)
        if resposta_final:
            send_whatsapp_message(phone, resposta_final)
            console.log(f"[LOG] Mensagem enviada para WhatsApp: {resposta_final}")
        return jsonify(result)
    except Exception as e:
        console.log(f"[red]Erro inesperado no webhook: {e}")
        console.log(f"[LOG][ERRO] Exceção capturada: {str(e)} | Payload: {json.dumps(request.json, ensure_ascii=False) if request.json else ''}")
        return jsonify({"error": str(e)}), 500

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

def validar_cpf(cpf):
    payload = {"cpf": cpf}
    url = f"{IXC_API_URL}/validarCpf"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_cliente(cpf):
    payload = {"cpf": cpf}
    url = f"{IXC_API_URL}/consultarCliente"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_contratos(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarContratos"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_boletos(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarBoletos"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_status_plano(id_cliente):
    payload = {"id_cliente": id_cliente}
    url = f"{IXC_API_URL}/consultarStatusPlano"
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

def consultar_dados_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc_redis(remoteJid, cpf)
        if cache:
            print(f"[LOG] Usando dados do IXC do cache Redis para CPF {cpf}")
            return cache
    payload = {"cpf": cpf}
    try:
        response = requests.post(IXC_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print("[LOG] Dados retornados do IXC para CPF", cpf, ":", json.dumps(data, ensure_ascii=False, indent=2))
        if remoteJid:
            salvar_ixc_redis(remoteJid, cpf, data)
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

def salvar_historico_mem0(remoteJid, cpf, mensagem):
    # Só salva mensagens de intenção/conversa, nunca dados sensíveis
    if mensagem.get("role") in ("user", "assistant"):
        # Proteção extra: não salva se mensagem contém dados sensíveis
        texto = mensagem.get("content", "").lower()
        if any(x in texto for x in ["cpf", "endereço", "address", "contrato", "boleto de r$", "nome", "razao_social", "telefone", "pix", "linha_digitavel", "url_pdf", "gateway_link", "senha", "login", "mac", "ipv4"]):
            return
        user_id = f"{remoteJid}:{cpf}"
        print(f"[MEM0AI] Salvando no histórico: {mensagem} para user_id={user_id}")
        mem0_client.add([mensagem], user_id=user_id, agent_id="geovana")

def buscar_historico_mem0(remoteJid, cpf, page=1, page_size=50):
    user_id = f"{remoteJid}:{cpf}"
    historico = mem0_client.get_all(user_id=user_id, page=page, page_size=page_size)
    print(f"[MEM0AI] Histórico retornado para user_id={user_id}: {historico}")
    return historico

def salvar_ixc_redis(remoteJid, cpf, dados_ixc):
    # Proteção extra: nunca salvar histórico de conversa aqui
    key = f"conversa:{remoteJid}:{cpf}:ixc"
    redis_client.setex(key, REDIS_TTL_IXC, json.dumps(dados_ixc, ensure_ascii=False))

def buscar_ixc_redis(remoteJid, cpf):
    key = f"conversa:{remoteJid}:{cpf}:ixc"
    val = redis_client.get(key)
    if val:
        return json.loads(val)
    return None

def mem0_to_mistral_messages(memories):
    messages = []
    for m in memories:
        # Se já está no formato correto, só adiciona
        if isinstance(m, dict) and "role" in m and "content" in m:
            msg = {"role": m["role"], "content": m["content"]}
            if "name" in m:
                msg["name"] = m["name"]
            messages.append(msg)
        # Se é um objeto do Mem0AI, tenta extrair
        elif isinstance(m, dict) and "memory" in m:
            # Por padrão, considera como mensagem de usuário
            # (Ajuste conforme necessário para distinguir user/assistant/tool)
            role = m.get("role", "user")
            content = m["memory"]
            messages.append({"role": role, "content": content})
    return messages

def transferir_para_humano(cpf, resumo):
    # Envia o resumo para o webhook Make.com
    url = "https://hook.us2.make.com/f1x53952bxirumz2gnfpoabdo397uws2"
    payload = {"cpf": cpf, "resumo": resumo}
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        console.log(f"[LOG] Resumo enviado para Make.com: {payload}")
        return {"status": "Transferido para humano", "resumo": resumo}
    except Exception as e:
        console.log(f"[LOG][ERRO] Falha ao transferir para humano: {str(e)} | Payload: {payload}")
        return {"erro": str(e)}

# Funções auxiliares para consultar dados específicos usando o cache geral do IXC

def consultar_boletos_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc_redis(remoteJid, cpf)
        if cache and 'boletos' in cache:
            print(f"[LOG] Usando boletos do cache IXC para CPF {cpf}")
            return cache['boletos']
    dados = consultar_dados_ixc(cpf, remoteJid)
    return dados.get('boletos', dados)

def consultar_status_plano_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc_redis(remoteJid, cpf)
        if cache and 'status_plano' in cache:
            print(f"[LOG] Usando status_plano do cache IXC para CPF {cpf}")
            return cache['status_plano']
    dados = consultar_dados_ixc(cpf, remoteJid)
    return dados.get('status_plano', dados)

def consultar_dados_cadastro_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc_redis(remoteJid, cpf)
        if cache and 'cadastro' in cache:
            print(f"[LOG] Usando cadastro do cache IXC para CPF {cpf}")
            return cache['cadastro']
    dados = consultar_dados_ixc(cpf, remoteJid)
    return dados.get('cadastro', dados)

def consultar_valor_plano_ixc(cpf, remoteJid=None):
    if remoteJid:
        cache = buscar_ixc_redis(remoteJid, cpf)
        if cache and 'valor_plano' in cache:
            print(f"[LOG] Usando valor_plano do cache IXC para CPF {cpf}")
            return cache['valor_plano']
    dados = consultar_dados_ixc(cpf, remoteJid)
    return dados.get('valor_plano', dados)

# --- SISTEMA DE FILAS COM REDIS ---
# Webhook apenas enfileira mensagem, processamento é feito por worker

def enqueue_message(data):
    msg_id = str(uuid.uuid4())
    redis_client.lpush("fila:mensagens", json.dumps({"id": msg_id, "data": data}))
    console.log(f"[FILA] Mensagem enfileirada com id {msg_id}")
    return msg_id

@app.route("/webhook_fila", methods=["POST"])
def webhook_fila():
    data = request.json
    enqueue_message(data)
    return jsonify({"status": "enfileirado"})

# Worker para processar mensagens da fila

def processar_mensagem_fila():
    while True:
        item = redis_client.brpop("fila:mensagens", timeout=5)
        if item:
            _, raw = item
            try:
                msg = json.loads(raw)
                console.log(f"[FILA] Processando mensagem id {msg['id']}")
                # Aqui você pode chamar a função webhook() ou refatorar o processamento para ser reutilizável
                # Exemplo: processar_payload(msg['data'])
            except Exception as e:
                console.log(f"[FILA][ERRO] Falha ao processar mensagem da fila: {str(e)} | Raw: {raw}")

# Para rodar o worker em thread separada (exemplo, não inicia automaticamente)
# Thread(target=processar_mensagem_fila, daemon=True).start()

def limpar_resposta(resposta, nome_cliente=None, intencao=None):
    if not resposta:
        return resposta
    # Remove cumprimentos duplicados
    if nome_cliente:
        resposta = re.sub(r"olá,?\s*" + re.escape(nome_cliente) + r"[!,\.\s]*", "Olá, " + nome_cliente + "! ", resposta, count=1, flags=re.IGNORECASE)
        resposta = re.sub(r"olá,?\s*" + re.escape(nome_cliente) + r"[!,\.\s]*", "", resposta, flags=re.IGNORECASE)
        # Garante que o nome só aparece uma vez
        resposta = re.sub(rf"({re.escape(nome_cliente)})[\s,!.]+(\1)+", r"\1", resposta, flags=re.IGNORECASE)
    # Remove frases genéricas não solicitadas se não for intenção de boleto
    if intencao and intencao != "consulta_boleto":
        resposta = re.sub(r"(aqui está (seu|o) boleto[\s\S]*?\n)+", "", resposta, flags=re.IGNORECASE)
        resposta = re.sub(r"segue o link para pagamento[\s\S]*?\n+", "", resposta, flags=re.IGNORECASE)
        resposta = re.sub(r"já estou consultando seu contrato[\s\S]*?\n+", "", resposta, flags=re.IGNORECASE)
    # Remove espaços e quebras de linha duplicadas
    resposta = re.sub(r"\n{2,}", "\n", resposta)
    resposta = re.sub(r"\s{2,}", " ", resposta)
    return resposta.strip()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)