from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, is_admin, nome_de_exibicao, require_perfil
from ..controllers import processamento_controller
from ..resources.database import get_app_db_session
from ..schemas.bloco import BlocoOut, GerarLaminasRequest
from ..schemas.etapas import FilaOut, LinhaFilaOut
from ..schemas.lamina import LaminaOut, GerarLaminasResult
from ..schemas.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO
from ..schemas.processamento import (
    ConclusaoProcessamentoOut,
    ConcluirLoteRequest,
    IniciarLoteRequest,
    LoteOut,
    ProcessamentoWorkspaceOut,
)
from ..schemas.usuario import RepasseCreate

router = APIRouter(prefix="/api/processamento", tags=["Processamento Técnico"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- Fila e posse do exame ---

@router.get("/fila", response_model=FilaOut)
async def listar_fila(
    filtro: str = Query(default="aguardando", pattern="^(meus|aguardando|em_andamento|todos)$"),
    busca: Optional[str] = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Fila do processamento, por exame e paginada, com cassetes, blocos e lâminas.

    O escopo ``meus`` usa o usuário do token — não é parâmetro, para ninguém
    conseguir ler a fila de outra pessoa.
    """
    return await processamento_controller.listar_fila(
        session, current_user.get("username"), filtro, busca, pagina, por_pagina
    )


@router.get("/exames/{id_exame}", response_model=ProcessamentoWorkspaceOut)
async def obter_workspace(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Exame + todos os cassetes com bloco e lâminas + o que falta para concluir."""
    return await processamento_controller.obter_workspace(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/assumir", response_model=LinhaFilaOut)
async def assumir(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Assume o exame para o usuário do token. 409 se já houver outro dono."""
    return await processamento_controller.assumir(
        session, id_exame, current_user.get("username"), nome_de_exibicao(current_user)
    )


@router.post("/exames/{id_exame}/repassar", response_model=LinhaFilaOut)
async def repassar(
    id_exame: str,
    dados: RepasseCreate,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Transfere a posse para outro usuário. Só o dono atual ou um admin."""
    return await processamento_controller.repassar(
        session, id_exame, dados, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/liberar", response_model=LinhaFilaOut)
async def liberar(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Devolve o exame à fila — saída para quando o dono fica indisponível."""
    return await processamento_controller.liberar(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.post("/exames/{id_exame}/concluir", response_model=ConclusaoProcessamentoOut)
async def concluir_exame(
    id_exame: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Envia o exame à Microscopia. 409 com a lista do que falta, se faltar algo.

    Única porta de saída do processamento: antes um lote concluído já avançava
    o exame, mesmo com metade dos cassetes ainda na bancada.
    """
    return await processamento_controller.concluir_exame(
        session, id_exame, current_user.get("username"), is_admin(current_user)
    )


@router.get("/cassetes/buscar", response_model=dict)
async def buscar_cassete(
    codigo: str = Query(max_length=255),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Resolve o QR Code (ou o código legível) de um cassete para o exame dono."""
    return await processamento_controller.buscar_cassete(session, codigo)


# --- Lotes ---

@router.post("/lote", response_model=dict, status_code=201)
async def iniciar_lote(
    dados: IniciarLoteRequest,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Inicia um ciclo de processamento. Exige posse dos exames envolvidos."""
    result = await processamento_controller.iniciar_lote(
        session, dados, current_user.get("username"), _ip(request), is_admin(current_user)
    )
    return {
        "lote": LoteOut.model_validate(result["lote"]).model_dump(),
        "total_cassetes": len(result["cassetes"]),
    }


@router.post("/lote/{id_lote}/concluir", response_model=dict)
async def concluir_lote(
    id_lote: str,
    dados: ConcluirLoteRequest,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Gera um bloco por cassete. Não avança o exame — isso é ``/concluir``."""
    result = await processamento_controller.concluir_lote(
        session, id_lote, dados, current_user.get("username"), _ip(request), is_admin(current_user)
    )
    return {
        "lote": LoteOut.model_validate(result["lote"]).model_dump(),
        "blocos_gerados": len(result["blocos"]),
        "blocos": [BlocoOut.model_validate(b).model_dump() for b in result["blocos"]],
    }


# --- Blocos e lâminas ---

@router.get("/blocos/pendencias", response_model=List[dict])
async def listar_blocos_pendentes(
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Fila de blocos aguardando corte microtômico."""
    return await processamento_controller.listar_blocos_pendentes(session)


@router.get("/blocos/buscar", response_model=List[dict])
async def buscar_bloco(
    codigo_bloco: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Busca manual de bloco por código (mesma rota que o leitor QR usaria)."""
    return await processamento_controller.buscar_bloco(session, codigo_bloco)


@router.post("/blocos/{id_bloco}/laminas", response_model=GerarLaminasResult, status_code=201)
async def gerar_laminas(
    id_bloco: str,
    dados: GerarLaminasRequest,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Gera as lâminas do bloco. Exige posse do exame a que o bloco pertence."""
    result = await processamento_controller.gerar_laminas(
        session, id_bloco, dados, current_user.get("username"), _ip(request), is_admin(current_user)
    )
    return GerarLaminasResult(
        bloco_id=result["bloco_id"],
        codigo_bloco=result["codigo_bloco"],
        laminas=[LaminaOut.model_validate(l) for l in result["laminas"]],
        etiquetas=result["etiquetas"],
    )


@router.get("/blocos/{id_bloco}/laminas", response_model=List[LaminaOut])
async def listar_laminas(
    id_bloco: str,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Lista todas as lâminas de um bloco."""
    laminas = await processamento_controller.listar_laminas(session, id_bloco)
    return [LaminaOut.model_validate(l) for l in laminas]


@router.get("/pendencias", response_model=List[dict], deprecated=True)
async def listar_pendencias(
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.TECNICO)),
):
    """Fila antiga, por cassete. Substituída por ``GET /api/processamento/fila``."""
    return await processamento_controller.listar_pendencias_processamento(session)
