from fastapi import APIRouter, Depends
from typing import List

from ..controllers import solicitacao_controller
from ..dependencies import get_solicitacao_provider
from ..providers.interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface
from ..auth.auth import auth_handler

# Trocar para "postgres" quando o POSTGRES_DSN estiver configurado apontando para o AGHU
STRATEGY = "csv"

router = APIRouter(
    prefix="/api/solicitacoes",
    tags=["Solicitações AGHU"],
    dependencies=[Depends(auth_handler.decode_token)]
)

@router.get("", response_model=List[dict])
async def listar_solicitacoes(
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY))
):
    """Lista todas as solicitações de exames do AGHU."""
    return await solicitacao_controller.listar_solicitacoes(provider)

@router.get("/prontuario/{prontuario}", response_model=List[dict])
async def listar_solicitacoes_por_prontuario(
    prontuario: int,
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY))
):
    """Lista as solicitações de exames de um paciente pelo número de prontuário."""
    return await solicitacao_controller.listar_solicitacoes_por_prontuario(prontuario, provider)
