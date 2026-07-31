from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, is_admin, nome_de_exibicao, require_perfil
from ..controllers import microscopia_controller
from ..resources.database import get_app_db_session
from ..schemas.etapas import FilaOut, LinhaFilaOut
from ..schemas.microscopia import (
    ComplementoCreate,
    LaudoPrevioCreate,
    LiberacaoCreate,
    MicroscopiaWorkspaceOut,
    ResultadoEtapaOut,
    RevisaoInternaCreate,
)
from ..schemas.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO
from ..schemas.usuario import RepasseCreate
from ..services import etapas

router = APIRouter(prefix="/api/microscopia", tags=["Microscopia"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- Fila e posse ---

@router.get("/fila", response_model=FilaOut)
async def listar_fila(
    filtro: str = Query(default="aguardando", pattern="^(meus|aguardando|em_andamento|todos)$"),
    subetapa: Optional[str] = Query(default=None, pattern="^(LAUDO_PREVIO|REVISAO)$"),
    busca: Optional[str] = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Fila da microscopia. ``subetapa`` separa quem aguarda laudo prévio de
    quem aguarda revisão do patologista."""
    return await microscopia_controller.listar_fila(
        session, current_user.get("username"), filtro, busca, subetapa, pagina, por_pagina
    )


@router.get("/exames/{id_exame}", response_model=MicroscopiaWorkspaceOut)
async def obter_workspace(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Exame + lâminas + laudo do ciclo atual + o papel esperado."""
    return await microscopia_controller.obter_workspace(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/assumir", response_model=LinhaFilaOut)
async def assumir(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Assume o exame para o usuário do token. 409 se já houver outro dono."""
    return await microscopia_controller.assumir(
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
    return await microscopia_controller.repassar(
        session, id_exame, dados, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/liberar", response_model=LinhaFilaOut)
async def liberar(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Devolve o exame à fila — saída para quando o dono fica indisponível."""
    return await microscopia_controller.liberar(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.get("/buscar", response_model=dict)
async def buscar_por_codigo(
    codigo: str = Query(max_length=255),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Resolve o código de uma lâmina, bloco ou solicitação para o exame."""
    return await microscopia_controller.buscar_por_codigo(session, codigo)


# --- Ações da etapa ---

@router.post("/exames/{id_exame}/laudo-previo", response_model=LinhaFilaOut)
async def registrar_laudo_previo(
    id_exame: str,
    dados: LaudoPrevioCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.RESIDENTE, Perfil.PATOLOGISTA)),
):
    """Residente conclui o laudo prévio; o exame volta à fila do patologista.

    O responsável é o usuário do token — a tela antiga mandava um nome escolhido
    num ``select``, o que permitia assinar em nome de outra pessoa.
    """
    return await microscopia_controller.registrar_laudo_previo(
        session, id_exame, dados.laudo, current_user.get("username"),
        nome_de_exibicao(current_user), is_admin(current_user),
    )


@router.post("/exames/{id_exame}/liberar-laudo", response_model=ResultadoEtapaOut)
async def liberar_laudo(
    id_exame: str,
    dados: LiberacaoCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA)),
):
    """Patologista aprova o laudo e encerra o exame."""
    return await microscopia_controller.liberar_laudo(
        session, id_exame, dados.conclusao, current_user.get("username"),
        nome_de_exibicao(current_user), is_admin(current_user),
    )


@router.post("/exames/{id_exame}/complemento", response_model=ResultadoEtapaOut)
async def solicitar_complemento(
    id_exame: str,
    dados: ComplementoCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """IHQ/complemento: encerra a posse e reabre o Processamento em novo ciclo."""
    return await microscopia_controller.solicitar_complemento(
        session, id_exame, dados.marcadores, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/revisao", response_model=LinhaFilaOut)
async def solicitar_revisao(
    id_exame: str,
    dados: RevisaoInternaCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA)),
):
    """Revisão interna: encerra a posse e abre um novo ciclo de revisão."""
    return await microscopia_controller.solicitar_revisao(
        session, id_exame, dados.motivo, current_user.get("username"), is_admin(current_user)
    )


# --- Rota antiga ---

class LaudoRequest(BaseModel):
    acao: Literal["liberar", "revisao", "complemento"]
    responsavel: Optional[str] = None
    laudo: Optional[str] = None
    observacoes: Optional[str] = None


@router.get("/pendencias", response_model=List[dict], deprecated=True)
async def listar_pendencias(
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Lista antiga sem paginação. Substituída por ``GET /api/microscopia/fila``."""
    return await microscopia_controller.listar_pendencias_microscopia(session)


@router.post("/{id_exame}/laudo", response_model=dict, deprecated=True)
async def registrar_laudo(
    id_exame: str,
    dados: LaudoRequest,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA, Perfil.RESIDENTE)),
):
    """Rota única antiga. Delega para a ação correspondente do novo fluxo, para
    não existirem dois caminhos com regras de posse diferentes.

    ``dados.responsavel`` é ignorado de propósito: quem assina é o token.
    """
    usuario = current_user.get("username")
    nome = nome_de_exibicao(current_user)
    admin = is_admin(current_user)
    registro = await etapas.exigir_etapa(session, id_exame, etapas.MICROSCOPIA)

    if dados.acao == "complemento":
        return await microscopia_controller.solicitar_complemento(
            session, id_exame, dados.observacoes or dados.laudo or "Complemento", usuario, admin
        )
    if dados.acao == "liberar":
        return await microscopia_controller.liberar_laudo(
            session, id_exame, dados.laudo, usuario, nome, admin
        )
    # "revisao" servia a dois casos distintos: encaminhar o laudo prévio do
    # residente, e o patologista pedir uma revisão interna. A subetapa resolve.
    if registro.subetapa == etapas.SUB_LAUDO_PREVIO:
        linha = await microscopia_controller.registrar_laudo_previo(
            session, id_exame, dados.laudo or "", usuario, nome, admin
        )
    else:
        linha = await microscopia_controller.solicitar_revisao(
            session, id_exame, dados.observacoes or "Revisão interna", usuario, admin
        )
    return {"exame_id": id_exame, "numero_solicitacao": linha["numero_solicitacao"], "status": linha["status_exame"]}
