import csv
from typing import List, Dict, Any

from ..interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface

class SolicitacaoCsvProvider(SolicitacaoProviderInterface):
    def __init__(self, csv_path: str = 'data/vw_solicitacao.csv'):
        self.csv_path = csv_path

    def _ler_csv(self) -> List[Dict[str, Any]]:
        rows = []
        with open(self.csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row['codigo_solicitacao'] = int(row['codigo_solicitacao'])
                except (ValueError, KeyError):
                    pass
                try:
                    row['prontuario'] = int(row['prontuario'])
                except (ValueError, KeyError):
                    pass
                rows.append(row)
        return rows

    async def listar_solicitacoes(self) -> List[Dict[str, Any]]:
        return self._ler_csv()

    async def listar_solicitacoes_por_prontuario(self, prontuario: int) -> List[Dict[str, Any]]:
        return [s for s in self._ler_csv() if s.get('prontuario') == prontuario]
