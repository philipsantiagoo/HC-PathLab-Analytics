from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, is_admin, nome_de_exibicao, require_perfil
from ..controllers import congelamento_controller
from ..resources.database import get_app_db_session
from ..schemas.congelamento import CicloCongelamentoCreate, CongelamentoWorkspaceOut
from ..schemas.etapas import FilaOut, LinhaFilaOut
from ..schemas.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO
from ..schemas.usuario import RepasseCreate

router = APIRouter(prefix="/api/congelamento", tags=["Congelamento"])


@router.get("/fila", response_model=FilaOut)
async def listar_fila(
    filtro: str = Query(default="aguardando", pattern="^(meus|aguardando|em_andamento|todos)$"),
    busca: Optional[str] = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Fila da congelação: exames do tipo CONG, com ciclos e situação do resultado."""
    return await congelamento_controller.listar_fila(
        session, current_user.get("username"), filtro, busca, pagina, por_pagina
    )


@router.get("/exames/{id_exame}", response_model=CongelamentoWorkspaceOut)
async def obter_workspace(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Exame + posse + todos os ciclos registrados + o HP correlato, se houver."""
    return await congelamento_controller.obter_workspace(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/assumir", response_model=LinhaFilaOut)
async def assumir(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Assume o exame inteiro para o usuário do token. 409 se já houver dono."""
    return await congelamento_controller.assumir(
        session, id_exame, current_user.get("username"), nome_de_exibicao(current_user)
    )


@router.post("/exames/{id_exame}/repassar", response_model=LinhaFilaOut)
async def repassar(
    id_exame: str,
    dados: RepasseCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Transfere a posse para outro usuário. Só o dono atual ou um admin."""
    return await congelamento_controller.repassar(
        session, id_exame, dados, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/liberar", response_model=LinhaFilaOut)
async def liberar(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Devolve o exame à fila — não confundir com liberar o resultado."""
    return await congelamento_controller.liberar(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/ciclos", response_model=CongelamentoWorkspaceOut, status_code=201)
async def registrar_ciclo(
    id_exame: str,
    dados: CicloCongelamentoCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Registra uma rodada de análise.

    ``conduta=COMPROMETIDA`` mantém o exame em andamento aguardando novo
    fragmento; ``LIVRE`` encerra a etapa e gera o HP correlato no backend,
    dentro da mesma transação — o contador do navegador não gera código
    definitivo.
    """
    return await congelamento_controller.registrar_ciclo(
        session, id_exame, dados, current_user.get("username"),
        nome_de_exibicao(current_user), is_admin(current_user),
    )


@router.get("/buscar", response_model=dict)
async def buscar(
    codigo: str = Query(max_length=120),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Resolve o código para um exame de congelação. Aceita o antigo prefixo CO."""
    return await congelamento_controller.buscar_por_codigo(session, codigo)
