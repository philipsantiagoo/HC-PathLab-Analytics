import os
from typing import Callable
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .providers.interfaces.paciente_provider_interface import PacienteProviderInterface
from .providers.implementations.paciente_postgres_provider import PacientePostgresProvider
from .providers.implementations.paciente_csv_provider import PacienteCsvProvider
from .providers.interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface
from .providers.implementations.solicitacao_postgres_provider import SolicitacaoPostgresProvider
from .providers.implementations.solicitacao_csv_provider import SolicitacaoCsvProvider
from .resources.database import get_aghu_db_session

# --- Paciente ---

def _get_paciente_postgres_provider(
    session: AsyncSession = Depends(get_aghu_db_session)
) -> PacienteProviderInterface:
    return PacientePostgresProvider(session=session)

def _get_paciente_csv_provider() -> PacienteProviderInterface:
    csv_path = os.getenv("PACIENTE_CSV_PATH", "data/pacientes.csv")
    return PacienteCsvProvider(csv_path=csv_path)

def get_paciente_provider(strategy: str) -> Callable[..., PacienteProviderInterface]:
    if strategy.upper() == "POSTGRES":
        return _get_paciente_postgres_provider
    elif strategy.upper() == "CSV":
        return _get_paciente_csv_provider
    else:
        raise ValueError(f"Estratégia de provedor desconhecida: {strategy}")

# --- Solicitação ---

def _get_solicitacao_postgres_provider(
    session: AsyncSession = Depends(get_aghu_db_session)
) -> SolicitacaoProviderInterface:
    return SolicitacaoPostgresProvider(session=session)

def _get_solicitacao_csv_provider() -> SolicitacaoProviderInterface:
    csv_path = os.getenv("SOLICITACAO_CSV_PATH", "data/vw_solicitacao.csv")
    return SolicitacaoCsvProvider(csv_path=csv_path)

def get_solicitacao_provider(strategy: str) -> Callable[..., SolicitacaoProviderInterface]:
    if strategy.upper() == "POSTGRES":
        return _get_solicitacao_postgres_provider
    elif strategy.upper() == "CSV":
        return _get_solicitacao_csv_provider
    else:
        raise ValueError(f"Estratégia de provedor desconhecida: {strategy}")
