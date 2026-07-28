from datetime import date
import unittest

from src.services.patologia import (
    CasoCandidato,
    LinhaPatologia,
    CodigoLaboratorioDesconhecido,
    agrupar_casos,
    tipo_por_codigo_lab,
)


def linha(
    ordem: int,
    numero: int,
    codigo_lab: str = "207",
    solicitacao: str = "S-1",
    conjunto: str | None = None,
) -> LinhaPatologia:
    return LinhaPatologia(
        ordem_origem=ordem,
        codigo_solicitacao=solicitacao,
        numero_amostra=numero,
        codigo_lab=codigo_lab,
        tipo_exame=tipo_por_codigo_lab(codigo_lab),
        prontuario="123",
        nome_paciente="Paciente de teste",
        data_nascimento=date(1980, 1, 1),
        data_solicitacao=date(2026, 7, 1),
        codigo_conjunto_amostras=conjunto,
        dados={},
    )


class PatologiaRulesTests(unittest.TestCase):
    def test_codigo_lab_e_a_fonte_unica_do_tipo(self):
        self.assertEqual(tipo_por_codigo_lab("139"), "CCV")
        self.assertEqual(tipo_por_codigo_lab("203"), "CG")
        self.assertEqual(tipo_por_codigo_lab("205"), "CONG")
        self.assertEqual(tipo_por_codigo_lab("207"), "HP")
        self.assertEqual(tipo_por_codigo_lab("209"), "IHQ")
        with self.assertRaises(CodigoLaboratorioDesconhecido):
            tipo_por_codigo_lab("999")

    def test_conjunto_aghu_une_solicitacoes_diferentes(self):
        casos = agrupar_casos([
            linha(10, 2, solicitacao="B", conjunto="500"),
            linha(20, 1, solicitacao="A", conjunto="500"),
        ])
        self.assertEqual(len(casos), 1)
        self.assertEqual([item.numero_amostra for item in casos[0].linhas], [2, 1])
        self.assertFalse(casos[0].exige_revisao)

    def test_fallback_une_pela_sequencia_sem_exigir_mesma_solicitacao(self):
        casos = agrupar_casos([
            linha(10, 1, solicitacao="A"),
            linha(17, 2, solicitacao="B"),
            linha(20, 3, solicitacao="C"),
        ])
        self.assertEqual(len(casos), 1)
        self.assertEqual({item.codigo_solicitacao for item in casos[0].linhas}, {"A", "B", "C"})
        self.assertFalse(casos[0].exige_revisao)

    def test_fallback_marca_amostra_sem_antecessora(self):
        casos = agrupar_casos([linha(10, 2)])
        self.assertEqual(len(casos), 1)
        self.assertTrue(casos[0].exige_revisao)
        self.assertIn("AMOSTRA_SEM_ANTECESSORA", casos[0].pendencias)


if __name__ == "__main__":
    unittest.main()
