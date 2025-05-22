import unittest
from unittest.mock import patch, MagicMock
import app

class TestMem0AIIntegration(unittest.TestCase):
    def setUp(self):
        self.remoteJid = "5511999999999@s.whatsapp.net"
        self.cpf = "12345678901"
        self.mensagem = {"role": "user", "content": "Teste de mensagem"}
        self.dados_ixc = {"cliente": {"nome": "Lucas Teste"}, "contratos": [], "boletos": []}

    @patch('app.mem0_client')
    def test_salvar_e_buscar_historico(self, mock_mem0):
        mock_mem0.get_all.return_value = [self.mensagem]
        app.salvar_historico_mem0(self.remoteJid, self.cpf, self.mensagem)
        historico = app.buscar_historico_mem0(self.remoteJid, self.cpf)
        mock_mem0.add.assert_called()
        self.assertEqual(historico, [self.mensagem])

    @patch('app.mem0_client')
    def test_salvar_e_buscar_ixc(self, mock_mem0):
        mock_mem0.search.return_value = [{"content": app.json.dumps(self.dados_ixc)}]
        app.salvar_ixc_mem0(self.remoteJid, self.cpf, self.dados_ixc)
        resultado = app.buscar_ixc_mem0(self.remoteJid, self.cpf)
        mock_mem0.add.assert_called()
        self.assertEqual(resultado, self.dados_ixc)

if __name__ == "__main__":
    unittest.main() 