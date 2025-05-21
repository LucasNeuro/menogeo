# Geovana - Agente Virtual G4 Telecom

## Objetivo
Agente virtual humanizado para atendimento via WhatsApp, integrando IA, Mem0AI e IXC, com fallback para humano.

## Tecnologias
- Python 3.10+
- FastAPI
- pydantic_ai
- mem0ai
- httpx
- requests

## Instalação
```bash
pip install -r requirements.txt
```

## Estrutura
```
app/
  main.py           # FastAPI app
  agent.py          # Definição do agente Geovana
  tools.py          # Ferramentas (tools) integradas ao agente
  mem0_resources.ts # Resources do Mem0AI
  utils.py          # Funções auxiliares
requirements.txt
README.md
```

## Configuração dos Resources (Mem0AI)
Veja `app/mem0_resources.ts` para definição dos resources.

## Execução
```bash
uvicorn app.main:app --reload
```

## Fluxo
1. Mensagem recebida do WhatsApp via webhook
2. CPF extraído da mensagem
3. Agente Geovana processa intenção, consulta Mem0AI/IXC
4. Resposta enviada ao cliente
5. Fallback automático para humano se necessário

## Exemplos de respostas
- Consulta boleto: `Aqui está seu boleto atual: ...`
- Sem internet: `Detected queda de conexão. Tente reiniciar o roteador...`
- Consulta plano: `Seu plano atual é ...`

## Observações
- Toda memória (inclusive conversas) pode ser armazenada no Mem0AI para maior fluidez.
- Personalize prompts e regras conforme necessidade do negócio. 