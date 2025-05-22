import os
import requests

MEM0_API_KEY = os.getenv("MEM0_API_KEY")
MEM0_API_URL = os.getenv("MEM0_API_URL")  # Agora carregado do .env

headers = {
    "Authorization": f"Bearer {MEM0_API_KEY}",
    "Content-Type": "application/json"
}

def save_context_mem0(user_id, context_dict):
    """
    Salva o contexto do cliente no Mem0, usando o user_id como chave.
    """
    payload = {
        "user_id": user_id,
        "memory": context_dict
    }
    response = requests.post(f"{MEM0_API_URL}/add_memory", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def get_context_mem0(user_id):
    """
    Busca o contexto do cliente no Mem0 pelo user_id.
    """
    params = {"user_id": user_id}
    response = requests.get(f"{MEM0_API_URL}/get", headers=headers, params=params)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("memory")

def consultar_boletos(contexto_cliente):
    contratos = contexto_cliente.get('contratos', {}).get('contratosAtivos', [])
    status_contrato = contratos[0]['status_contrato'] if contratos else None
    login_online = contexto_cliente.get('login', {}).get('online')
    boletos = contexto_cliente.get('boletos', [])
    # Ordena por data de vencimento
    boletos_ordenados = sorted(boletos, key=lambda b: b['data_vencimento'])[:3]
    resultado = {
        'status_contrato': status_contrato,
        'login_online': login_online,
        'boletos': [
            {
                'valor': b['valor'],
                'data_vencimento': b['data_vencimento'],
                'linha_digitavel': b['linha_digitavel'],
                'url_pdf': b['url_pdf'],
                'pix_copia_cola': b['pix_copia_cola']
            } for b in boletos_ordenados
        ]
    }
    return resultado

def consultar_status_plano(contexto_cliente):
    contratos = contexto_cliente.get('contratos', {}).get('contratosAtivos', [])
    contrato = contratos[0] if contratos else {}
    login = contexto_cliente.get('login', {})
    cliente = contexto_cliente.get('cliente', {})
    return {
        'status_contrato': contrato.get('status_contrato'),
        'status_internet': contrato.get('status_internet'),
        'desbloqueio_confianca_ativo': contrato.get('desbloqueio_confianca_ativo'),
        'obs': cliente.get('obs'),
        'login_online': login.get('online')
    }

def estou_sem_internet(contexto_cliente):
    contratos = contexto_cliente.get('contratos', {}).get('contratosAtivos', [])
    contrato = contratos[0] if contratos else {}
    login = contexto_cliente.get('login', {})
    cliente = contexto_cliente.get('cliente', {})
    os_abertas = contexto_cliente.get('OS', [])
    boletos = contexto_cliente.get('boletos', [])
    return {
        'status_contrato': contrato.get('status_contrato'),
        'status_internet': contrato.get('status_internet'),
        'obs': cliente.get('obs'),
        'login_online': login.get('online'),
        'tempo_conectado': login.get('tempo_conectado'),
        'ultima_conexao_inicial': login.get('ultima_conexao_inicial'),
        'os_abertas': os_abertas,
        'boletos': boletos
    }

def consulta_dados_cadastro(contexto_cliente):
    cliente = contexto_cliente.get('cliente', {})
    contratos = contexto_cliente.get('contratos', {}).get('contratosAtivos', [])
    contrato = contratos[0] if contratos else {}
    return {
        'razao_social': cliente.get('razao_social'),
        'celular': cliente.get('celular'),
        'whatsapp': cliente.get('whatsapp'),
        'ultima_atualizacao': cliente.get('ultima_atualizacao'),
        'endereco': contrato.get('endereco'),
        'numero': contrato.get('numero'),
        'bairro': contrato.get('bairro'),
        'cep': contrato.get('cep')
    }

def consulta_valor_plano(contexto_cliente):
    contratos = contexto_cliente.get('contratos', {}).get('contratosAtivos', [])
    contrato = contratos[0] if contratos else {}
    boletos = contexto_cliente.get('boletos', [])
    login = contexto_cliente.get('login', {})
    valor = boletos[0]['valor'] if boletos else None
    return {
        'contrato': contrato.get('contrato'),
        'valor': valor,
        'status_contrato': contrato.get('status_contrato'),
        'login_online': login.get('online')
    }

def fazer_contrato(dados_iniciais):
    # Aqui você integraria com o CRM para criar o lead
    return {'status': 'lead_criado', 'dados': dados_iniciais}

def registrar_feedback(contexto_cliente, motivo):
    # Aqui você pode registrar o feedback em um sistema próprio
    return {'status': 'feedback_registrado', 'motivo': motivo}

def encaminhar_humano(contexto_cliente, motivo):
    # Aqui você pode acionar o atendimento humano
    return {'status': 'encaminhado_humano', 'motivo': motivo}

def abrir_os(contexto_cliente, motivo):
    # Aqui você pode abrir uma ordem de serviço
    return {'status': 'os_aberta', 'motivo': motivo} 