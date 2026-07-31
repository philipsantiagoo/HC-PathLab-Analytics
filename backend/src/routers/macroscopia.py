from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, is_admin, require_perfil
from ..controllers import fluxo_controller as macroscopia_controller
from ..resources.database import get_app_db_session
from ..schemas.frasco import FrascoDetalhe
from ..schemas.etapas import LinhaFilaOut
from ..schemas.macroscopia import (
    ExameWorkspaceOut,
    FilaMacroscopiaOut,
    MacroscopiaCreate,
)
from ..schemas.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO
from ..schemas.resultados import MacroscopiaResult
from ..schemas.usuario import RepasseCreate

router = APIRouter(prefix="/api/macroscopia", tags=["Macroscopia"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _nome(current_user: dict) -> str | None:
    """Nome de exibição do token. O AD devolve ``displayName`` como lista."""
    display = current_user.get("displayName")
    if isinstance(display, list):
        return display[0] if display else None
    return display or current_user.get("username")


@router.get("/fila", response_model=FilaMacroscopiaOut)
async def listar_fila(
    filtro: str = Query(default="aguardando", pattern="^(meus|aguardando|em_andamento|todos)$"),
    busca: Optional[str] = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Fila da estação, por exame e paginada. Os contadores das abas vêm junto.

    O escopo ``meus`` usa o usuário do token — não é parâmetro, para ninguém
    conseguir ler a fila de outra pessoa.
    """
    return await macroscopia_controller.listar_fila_macroscopia(
        session, current_user.get("username"), filtro, busca, pagina, por_pagina
    )


@router.get("/exames/{id_exame}", response_model=ExameWorkspaceOut)
async def obter_workspace(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Exame + frascos + posse + clivagem, para abrir a estação."""
    return await macroscopia_controller.obter_workspace_macroscopia(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/assumir", response_model=LinhaFilaOut)
async def assumir(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Assume o exame para o usuário do token. 409 se já houver outro dono."""
    return await macroscopia_controller.assumir_exame(
        session, id_exame, current_user.get("username"), _nome(current_user)
    )


@router.post("/exames/{id_exame}/repassar", response_model=LinhaFilaOut)
async def repassar(
    id_exame: str,
    dados: RepasseCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Transfere a posse para outro usuário. Só o dono atual ou um admin."""
    return await macroscopia_controller.repassar_exame(
        session, id_exame, dados, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/liberar", response_model=LinhaFilaOut)
async def liberar(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Devolve o exame à fila — saída para quando o dono fica indisponível."""
    return await macroscopia_controller.liberar_exame(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.get("/pendencias", response_model=List[FrascoDetalhe], deprecated=True)
async def listar_pendencias(
    limite: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Fila antiga, por frasco. Substituída por ``GET /api/macroscopia/fila``."""
    return await macroscopia_controller.listar_pendencias_macroscopia(session, limite)


@router.post("", response_model=MacroscopiaResult, status_code=201)
async def registrar_macroscopia(
    dados: MacroscopiaCreate,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.MACROSCOPISTA)),
):
    """Persiste a clivagem do exame e gera seus cassetes (A ou A1, A2, ...)."""
    return await macroscopia_controller.registrar_macroscopia(
        session, dados, current_user.get("username"), _ip(request), is_admin(current_user)
    )
