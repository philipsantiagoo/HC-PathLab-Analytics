from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from typing import List

from ..auth.auth import auth_handler
from ..resources.database import get_aghu_db_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api", tags=["Admin"])

class AdminData(BaseModel):
    message: str
    user_groups: List[str]

async def verify_admin_group(current_user: dict = Depends(auth_handler.decode_token)):
    ADMIN_GROUP = "GLO-SEC-HCPE-SETISD"
    if ADMIN_GROUP not in current_user.get("groups", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
    return current_user

@router.get("/admin-only-data", response_model=AdminData)
async def get_admin_data(current_user: dict = Depends(verify_admin_group)):
    """
    Returns data only accessible by users with admin privileges.
    """
    return AdminData(
        message="This is highly confidential admin data!",
        user_groups=current_user.get("groups", [])
    )

@router.get("/aghu/tabelas", response_model=List[str])
async def listar_tabelas_aghu(
    request: Request,
    current_user: dict = Depends(verify_admin_group),
    aghu_db: AsyncSession = Depends(get_aghu_db_session),
):
    """
    Lista todas as tabelas disponíveis no schema 'agh' do banco AGHU.
    Útil para descobrir quais tabelas estão disponíveis nesta instância.
    """
    if not hasattr(request.app.state, "aghu_db"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conexão com o AGHU não está configurada (POSTGRES_DSN ausente no .env)",
        )

    result = await aghu_db.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'agh' ORDER BY table_name"
        )
    )
    return [row[0] for row in result.fetchall()]
