from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SolicitacaoProviderInterface(ABC):
    """Interface (contrato) para provedores de dados de solicitações de exames do AGHU."""

    @abstractmethod
    async def listar_solicitacoes(self) -> List[Dict[str, Any]]:
        """Retorna todas as solicitações de exames."""
        pass

    @abstractmethod
    async def listar_solicitacoes_por_prontuario(self, prontuario: int) -> List[Dict[str, Any]]:
        """Retorna as solicitações de exames de um paciente pelo prontuário."""
        pass
