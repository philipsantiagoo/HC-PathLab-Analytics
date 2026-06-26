from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.exame import Exame
from ..models.lamina import Lamina
from ..providers.implementations.exame_repository import ExameRepository
from ..providers.implementations.lamina_repository import LaminaRepository
from ..schemas.lamina import LaminaOut
from ..schemas.macroscopia import MicroscopiaReadCreate
from ..services.maquina_estados import Etapa, StatusExame, StatusLamina, transicionar


async def listar_pendencias(session: AsyncSession) -> List[dict]:
    lamina_repo = LaminaRepository(session)
    laminas = await lamina_repo.listar_todas_pendentes()
    return [
        {
            "id": lamina.id,
            "codigo_lamina": lamina.codigo_lamina,
            "status": lamina.status,
            "numero_lamina": lamina.numero_lamina,
            "id_bloco": lamina.id_bloco,
            "coloracao": lamina.coloracao,
            "codigo_bloco": getattr(lamina, "codigo_bloco", None),
        }
        for lamina in laminas
    ]


async def registrar_leitura(
    session: AsyncSession,
    dados: MicroscopiaReadCreate,
    usuario: Optional[str],
    ip: Optional[str],
) -> dict:
    lamina_repo = LaminaRepository(session)
    exame_repo = ExameRepository(session)

    lamina = await lamina_repo.obter(dados.id_lamina)
    if lamina is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lâmina não encontrada.")

    if lamina.status == StatusLamina.LIDA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lâmina já foi lida.")

    transicionar(
        session,
        lamina,
        StatusLamina.EM_LEITURA,
        etapa=Etapa.MICROSCOPIA,
        usuario=usuario,
        ip=ip,
        observacoes=dados.observacoes or "Início de leitura microscópica",
    )
    transicionar(
        session,
        lamina,
        StatusLamina.LIDA,
        etapa=Etapa.MICROSCOPIA,
        usuario=usuario,
        ip=ip,
        observacoes=dados.observacoes or "Leitura microscópica concluída",
    )

    exame = await exame_repo.obter_por_lamina(lamina.id)
    if exame is not None and exame.status == StatusExame.EM_PROCESSAMENTO:
        transicionar(
            session,
            exame,
            StatusExame.EM_MICROSCOPIA,
            etapa=Etapa.MICROSCOPIA,
            usuario=usuario,
            ip=ip,
            observacoes=f"Lâmina {lamina.codigo_lamina} concluída",
        )

    await session.commit()
    await session.refresh(lamina)

    return {
        "lamina": lamina,
        "exame": exame,
    }
