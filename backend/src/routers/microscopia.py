from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import Perfil, require_perfil
from ..controllers import microscopia_controller
from ..resources.database import get_app_db_session
from ..schemas.macroscopia import MicroscopiaReadCreate

router = APIRouter(prefix="/api/microscopia", tags=["Microscopia"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/pendencias", response_model=List[dict])
async def listar_pendencias(
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA)),
):
    return await microscopia_controller.listar_pendencias(session)


@router.post("", response_model=dict, status_code=201)
async def registrar_leitura(
    dados: MicroscopiaReadCreate,
    request: Request,
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil(Perfil.PATOLOGISTA)),
):
    return await microscopia_controller.registrar_leitura(
        session, dados, current_user.get("username"), _ip(request)
    )
