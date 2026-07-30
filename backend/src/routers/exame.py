from typing import List

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, require_perfil
from ..controllers import fluxo_controller as exame_controller
from ..controllers import fluxo_controller as triagem_controller
from ..resources.database import get_app_db_session
from ..schemas.exame import DashboardExameOut, ExameCreate, ExameOut
from ..schemas.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO, PaginaResposta
from ..schemas.resultados import TriagemResult

router = APIRouter(prefix="/api/exames", tags=["Exames / Triagem"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", response_model=TriagemResult, status_code=201)
async def registrar_recebimento(
    dados: ExameCreate,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.RECEPCIONISTA)),
):
    """Triagem: registra o recebimento da peça, gera número de solicitação,
    cria o frasco com seu código de identificação e devolve a etiqueta."""
    return await triagem_controller.registrar_recebimento(
        session, dados, current_user.get("username"), _ip(request)
    )


@router.get("/dashboard/paginado", response_model=PaginaResposta[DashboardExameOut])
async def listar_dashboard_paginado(
    etapa: str | None = Query(None, max_length=40, description="Filtra por etapa do processo"),
    codigo_aghu: str | None = Query(None, max_length=120, description="Filtra por código do AGHU"),
    codigo_interno: str | None = Query(None, max_length=120, description="Filtra por código interno/solicitação"),
    nome_paciente: str | None = Query(None, max_length=120, description="Filtra por nome do paciente"),
    busca: str | None = Query(None, max_length=120, description="Busca única em código, AGHU ou paciente"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Dashboard por exame, paginado no servidor, com os filtros da barra de pesquisa."""
    return await exame_controller.listar_dashboard_paginado(
        session,
        etapa=etapa,
        busca=busca,
        pagina=pagina,
        por_pagina=por_pagina,
        codigo_aghu=codigo_aghu,
        codigo_interno=codigo_interno,
        nome_paciente=nome_paciente,
    )


@router.get("/dashboard", response_model=List[DashboardExameOut], deprecated=True)
async def listar_dashboard(
    etapa: str | None = Query(None, description="Filtra por etapa do processo"),
    codigo_aghu: str | None = Query(None, description="Filtra por código do AGHU"),
    codigo_interno: str | None = Query(None, description="Filtra por código interno/solicitação"),
    nome_paciente: str | None = Query(None, description="Filtra por nome do paciente"),
    limite: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Lista não paginada. Substituída por ``GET /api/exames/dashboard/paginado``."""
    return await exame_controller.listar_dashboard(
        session,
        limite=limite,
        etapa=etapa,
        codigo_aghu=codigo_aghu,
        codigo_interno=codigo_interno,
        nome_paciente=nome_paciente,
    )


@router.get("/dashboard/resumo")
async def resumo_dashboard(
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    return await exame_controller.resumo_dashboard(session)


@router.get("", response_model=List[ExameOut])
async def listar_exames(
    limite: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    return await exame_controller.listar_exames(session, limite)


@router.get("/{id_exame}/detalhe")
async def obter_detalhe(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Visão unificada do caso (exame + paciente + frasco + macroscopia +
    cassetes + blocos + lâminas) para o modal 'Ver detalhes' do dashboard."""
    return await exame_controller.obter_detalhe(session, id_exame)


@router.get("/{id_exame}", response_model=ExameOut)
async def obter_exame(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    return await exame_controller.obter_exame(session, id_exame)