import os
from dotenv import load_dotenv
import requests
from datetime import datetime
import google.generativeai as genai
from app.tools import buscar_e_salvar_dados_ixc, abrir_os
from app.memory import buscar_contexto_cliente, salvar_conversa

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
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

def gerar_resposta_gemini(prompt: str) -> str:
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text

# Função principal para processar a mensagem do cliente
async def processar_mensagem_geovana(msg: str, contexto: dict) -> str:
    # Monta o prompt com contexto
    prompt = SYSTEM_PROMPT + "\n\nContexto do cliente:\n" + str(contexto) + f"\n\nMensagem do cliente:\n{msg}\n\nResposta:" 
    resposta = gerar_resposta_gemini(prompt)
    return resposta

# Fallback para humano
async def fallback_transferencia(cpf: str, remote_jid: str, mensagem: str) -> str:
    make_url = os.getenv("MAKE_URL_HOOK")
    payload = {
        "cpf": cpf,
        "remote_jid": remote_jid,
        "mensagem": mensagem
    }
    requests.post(make_url, json=payload)
    return "⚠️ Encaminhei sua mensagem para um atendente humano. Você será respondido em breve."

def consulta_dados_cadastro(ctx: dict) -> dict:
    cliente = ctx.get("cliente", {})
    contratos = ctx.get("contratos", [])
    contrato = contratos[0] if isinstance(contratos, list) and contratos else {}
    resposta = f"""Razão Social: {cliente.get('razao_social', '-')}
    Celular: {cliente.get('celular', '-')}
    WhatsApp: {cliente.get('whatsapp', '-')}
    Última atualização: {cliente.get('ultima_atualizacao', '-')}
    """
    endereco = contrato.get("endereco", "-")
    if endereco:
        resposta += f"Endereço: {endereco}\n"
    return {"mensagem": resposta + "Esses dados estão corretos? Se não, posso abrir uma OS para atualização."}

# As tools e lógica de negócio podem ser mantidas como funções auxiliares, chamadas dentro do fluxo do Gemini.