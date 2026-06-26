from typing import List, Dict, Any

from ..providers.interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface

async def listar_solicitacoes(
    provider: SolicitacaoProviderInterface
) -> List[Dict[str, Any]]:
    return await provider.listar_solicitacoes()

async def listar_solicitacoes_por_prontuario(
    prontuario: int,
    provider: SolicitacaoProviderInterface
) -> List[Dict[str, Any]]:
    return await provider.listar_solicitacoes_por_prontuario(prontuario)
