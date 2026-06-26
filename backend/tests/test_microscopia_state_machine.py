import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.lamina import Lamina
from src.services.maquina_estados import StatusLamina, transicionar


class DummySession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


class MicroscopiaStateMachineTests(unittest.TestCase):
    def test_lamina_can_transition_from_pending_to_reading_to_done(self):
        session = DummySession()
        lamina = Lamina(id="lamina-1", id_bloco="bloco-1", numero_lamina=1, codigo_lamina="BL-1-L1", qr_code="qr-1")
        lamina.status = StatusLamina.AGUARDANDO_LEITURA

        transicionar(
            session,
            lamina,
            StatusLamina.EM_LEITURA,
            etapa="Microscopia",
            usuario="user",
            ip="127.0.0.1",
        )
        self.assertEqual(lamina.status, StatusLamina.EM_LEITURA)

        transicionar(
            session,
            lamina,
            StatusLamina.LIDA,
            etapa="Microscopia",
            usuario="user",
            ip="127.0.0.1",
        )
        self.assertEqual(lamina.status, StatusLamina.LIDA)
        self.assertGreaterEqual(len(session.added), 2)


if __name__ == "__main__":
    unittest.main()
