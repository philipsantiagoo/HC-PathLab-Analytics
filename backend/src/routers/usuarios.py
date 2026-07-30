from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.perfis import require_perfil
from ..controllers import fluxo_controller as usuarios_controller
from ..resources.database import get_app_db_session
from ..schemas.usuario import UsuarioCandidatoOut

router = APIRouter(prefix="/api/usuarios", tags=["Usuários"])


@router.get("/candidatos", response_model=List[UsuarioCandidatoOut])
async def listar_candidatos(
    busca: Optional[str] = Query(default=None, max_length=120),
    limite: int = Query(default=30, ge=1, le=200),
    session: AsyncSession = Depends(get_app_db_session),
    current_user: dict = Depends(require_perfil()),
):
    """Usuários que podem receber um repasse.

    Combina ``perfis_usuarios`` com os usernames já vistos no fluxo — a tabela
    de perfis só ganha linha no login, então sozinha ela nasceria vazia.
    """
    return await usuarios_controller.listar_usuarios_candidatos(session, busca, limite)
