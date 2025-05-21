import os
from dotenv import load_dotenv
import requests
from pydantic_ai import Agent, RunContext
from app.tools import buscar_e_salvar_dados_ixc, abrir_os
from app.memory import buscar_contexto_cliente, salvar_conversa
from datetime import datetime

# Carrega variáveis de ambiente
load_dotenv()

PROMPT = """
Você é Geovana, uma agente virtual simpática, eficiente e humana da G4 Telecom.
Seu papel é identificar a intenção do cliente e acionar a ferramenta (tool) mais adequada para resolver a dúvida ou problema dele.
Sempre que o cliente disser que está sem internet, inicie o checklist de suporte.
Se o cliente pedir boletos, envie os boletos.
Se o cliente pedir status do plano, envie o status.
Se não souber, peça para o cliente explicar melhor ou encaminhe para um atendente humano.
Nunca repita perguntas já feitas, use o histórico para manter a conversa fluida.
Responda sempre de forma clara, humana, com bullet points e emojis.
"""

GEOVANA = Agent(
    name="Geovana",
    model="mistral",
    api_key=os.getenv("MISTRAL_API_KEY"),
    agent_id=os.getenv("MISTRAL_AGENT_ID"),
    system_prompt="""
    Você é Geovana, agente virtual da G4 Telecom. Use sempre o contexto salvo no Mem0AI para personalizar as respostas. Siga as regras de negócio e o fluxo conversacional definido abaixo, mas seja natural, empática e evite respostas robotizadas. Nunca envie boletos pagos ou futuros, a menos que o cliente peça. Use o histórico para evitar repetições e contextualizar as respostas.
    
    Fluxo de intenções:
    - consulta_boleto: Mostre os 3 próximos boletos a vencer, se o contrato estiver ativo. Se bloqueado/inativo, informe a situação e oriente.
    - consulta_status_plano: Informe status do contrato, internet, pendências e desbloqueio de confiança.
    - estou_sem_internet: Verifique status do contrato, pendências, login, tempo conectado, e oriente reboot ou abertura de OS se necessário.
    - consulta_dados_cadastro: Mostre dados cadastrais e peça confirmação. Se divergente, oriente atualização.
    - consulta_valor_plano: Informe nome e valor do plano, se contrato ativo.
    - fazer_contrato: Capture dados iniciais e oriente criação de lead.
    - reclamar_atendimento/elogiar_servico/falar_com_atendente: Registre motivo e encaminhe para humano.
    Sempre aja de forma clara, amigável e personalizada.
    """
)

@GEOVANA.tool
def abrir_os_tool(cpf: str, motivo: str) -> str:
    return abrir_os(cpf, motivo)

@GEOVANA.depends
async def carregar_contexto(ctx: RunContext[dict]):
    cpf = ctx.deps.get("cpf")
    if not cpf:
        return {}
    # Busca e salva dados do IXC no Mem0AI, se necessário
    await buscar_e_salvar_dados_ixc(cpf)
    # Busca contexto completo do Mem0AI
    contexto = await buscar_contexto_cliente(cpf)
    return contexto

@GEOVANA.after_response
async def salvar_historico(ctx: RunContext[dict], input: str, output: str):
    cpf = ctx.deps.get("cpf")
    if cpf:
        await salvar_conversa(cpf, input, output)

@GEOVANA.fallback
def fallback_transferencia(ctx: RunContext[dict], input: str) -> str:
    cpf = ctx.deps.get("cpf")
    remote_jid = ctx.deps.get("remote_jid")
    make_url = os.getenv("MAKE_URL_HOOK")
    payload = {
        "cpf": cpf,
        "remote_jid": remote_jid,
        "mensagem": input
    }
    requests.post(make_url, json=payload)
    return "⚠️ Encaminhei sua mensagem para um atendente humano. Você será respondido em breve."

# TOOL: Consulta Boleto
@GEOVANA.tool
def consulta_boleto(ctx: RunContext[dict]) -> dict:
    contratos = ctx.context.get("contratos", [])
    boletos = ctx.context.get("boletos", [])
    login = ctx.context.get("login", {})
    if not contratos:
        return {"mensagem": "Não localizei contratos ativos para seu CPF."}
    contrato = contratos[0] if isinstance(contratos, list) else contratos
    status = contrato.get("status_contrato", "")
    if status.lower() not in ["ativo", "active"]:
        return {"mensagem": f"Seu contrato está '{status}'. Por favor, regularize para acessar os boletos."}
    # Filtra boletos futuros
    hoje = datetime.now().date()
    boletos_futuros = [b for b in boletos if datetime.strptime(b["data_vencimento"], "%Y-%m-%d").date() >= hoje]
    boletos_futuros = sorted(boletos_futuros, key=lambda b: b["data_vencimento"])[:3]
    if not boletos_futuros:
        return {"mensagem": "Não há boletos a vencer."}
    resposta = "Aqui estão seus próximos boletos:\n"
    for b in boletos_futuros:
        resposta += f"• Valor: R$ {b['valor']} | Vencimento: {b['data_vencimento']}\nPDF: {b['url_pdf']}\nPIX: {b['pix_copia_cola']}\n"
    return {"mensagem": resposta}

# TOOL: Consulta Status Plano
@GEOVANA.tool
def consulta_status_plano(ctx: RunContext[dict]) -> dict:
    contratos = ctx.context.get("contratos", [])
    login = ctx.context.get("login", {})
    cliente = ctx.context.get("cliente", {})
    if not contratos:
        return {"mensagem": "Não localizei contratos ativos para seu CPF."}
    contrato = contratos[0] if isinstance(contratos, list) else contratos
    status = contrato.get("status_contrato", "")
    status_internet = contrato.get("status_internet", "")
    desbloqueio = contrato.get("desbloqueio_confianca_ativo", "Não")
    obs = cliente.get("obs", "")
    resposta = f"Status do contrato: {status}\nStatus da internet: {status_internet}\nDesbloqueio confiança: {desbloqueio}\n"
    if obs:
        resposta += f"Observação: {obs}\n"
    return {"mensagem": resposta}

# TOOL: Estou Sem Internet
@GEOVANA.tool
def estou_sem_internet(ctx: RunContext[dict]) -> dict:
    contratos = ctx.context.get("contratos", [])
    login = ctx.context.get("login", {})
    cliente = ctx.context.get("cliente", {})
    boletos = ctx.context.get("boletos", [])
    if not contratos:
        return {"mensagem": "Não localizei contratos ativos para seu CPF."}
    contrato = contratos[0] if isinstance(contratos, list) else contratos
    status = contrato.get("status_contrato", "")
    status_internet = contrato.get("status_internet", "")
    obs = cliente.get("obs", "")
    hoje = datetime.now().date()
    # Regras de bloqueio e reativação
    if status.lower() == "bloqueado":
        boletos_vencidos = [b for b in boletos if datetime.strptime(b["data_vencimento"], "%Y-%m-%d").date() < hoje]
        if boletos_vencidos:
            return {"mensagem": "Seu contrato está bloqueado por pendência. Encaminhando para atendimento humano."}
        else:
            return {"mensagem": "Seu contrato está bloqueado, mas não há boletos vencidos. Encaminhando para reativação."}
    if status.lower() != "ativo":
        boletos_vencidos = [b for b in boletos if datetime.strptime(b["data_vencimento"], "%Y-%m-%d").date() < hoje]
        if boletos_vencidos:
            return {"mensagem": "Seu contrato não está ativo e há boletos vencidos. Encaminhando para atendimento humano."}
        else:
            return {"mensagem": "Seu contrato não está ativo, mas não há pendências. Encaminhando para reativação."}
    if obs:
        return {"mensagem": f"Há uma pendência: {obs}. Por favor, regularize para restabelecer o serviço."}
    if login.get("online", "Não") == "Sim" and int(login.get("tempo_conectado", "0")) > 30:
        return {"mensagem": "Detectamos conexão longa. Por favor, tente reiniciar seu roteador."}
    # Se problema persistir, abrir OS
    return {"mensagem": "Persistindo o problema? Posso abrir uma OS para você."}

# TOOL: Consulta Dados Cadastro
@GEOVANA.tool
def consulta_dados_cadastro(ctx: RunContext[dict]) -> dict:
    cliente = ctx.context.get("cliente", {})
    contratos = ctx.context.get("contratos", [])
    contrato = contratos[0] if isinstance(contratos, list) and contratos else {}
    resposta = f"Razão Social: {cliente.get('razao_social', '-')}
Celular: {cliente.get('celular', '-')}
WhatsApp: {cliente.get('whatsapp', '-')}
Última atualização: {cliente.get('ultima_atualizacao', '-')}
"
    endereco = contrato.get("endereco", "-")
    if endereco:
        resposta += f"Endereço: {endereco}\n"
    return {"mensagem": resposta + "Esses dados estão corretos? Se não, posso abrir uma OS para atualização."}

# TOOL: Consulta Valor Plano
@GEOVANA.tool
def consulta_valor_plano(ctx: RunContext[dict]) -> dict:
    contratos = ctx.context.get("contratos", [])
    boletos = ctx.context.get("boletos", [])
    login = ctx.context.get("login", {})
    if not contratos:
        return {"mensagem": "Não localizei contratos ativos para seu CPF."}
    contrato = contratos[0] if isinstance(contratos, list) else contratos
    status = contrato.get("status_contrato", "")
    if status.lower() not in ["ativo", "active"]:
        return {"mensagem": f"Seu contrato está '{status}'. Por favor, regularize para consultar o valor do plano."}
    valor = boletos[0]["valor"] if boletos else "-"
    nome_plano = contrato.get("contrato", "-")
    return {"mensagem": f"Seu plano atual é {nome_plano}, com valor R$ {valor}/mês."}

# TOOL: Fazer Contrato
@GEOVANA.tool
def fazer_contrato(ctx: RunContext[dict]) -> dict:
    # Aqui pode-se acionar integração com CRM futuramente
    return {"mensagem": "Ótimo! Para fazer um novo contrato, preciso de alguns dados iniciais. Por favor, envie seu nome completo, CPF e endereço."}

# TOOL: Reclamar Atendimento / Elogiar Serviço / Falar com Atendente
@GEOVANA.tool
def encaminhar_para_humano(ctx: RunContext[dict], motivo: str = "") -> dict:
    return {"mensagem": "Encaminhei sua solicitação para um atendente humano. Em breve você será atendido."}