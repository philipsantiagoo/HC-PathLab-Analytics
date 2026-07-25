"""Dados de referência que precisam existir antes de receber exames."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.catalogo_aghu import TipoExame
from ..models.usuarios import Papel


TIPOS_EXAME_INICIAIS = (
    ("HP", "Histopatológico", "HP", 20),
    ("CG", "Citologia Geral", "CG", 20),
    ("CCV", "Citologia Cérvico-vaginal", "CV", 20),
    ("IHQ", "Imuno-histoquímica", "IHQ", 20),
    ("CONG", "Congelação", "CONG", 1),
)

PAPEIS_INICIAIS = (
    ("ADMIN", "Administrador"),
    ("RECEPCIONISTA", "Recepcionista"),
    ("MACROSCOPISTA", "Macroscopista"),
    ("TECNICO", "Técnico de Laboratório"),
    ("RESIDENTE", "Residente"),
    ("PATOLOGISTA", "Médico Patologista"),
)


async def garantir_catalogos_iniciais(session: AsyncSession) -> None:
    """Insere somente os registros ausentes; é seguro chamar no startup."""
    for codigo, nome, prefixo, sla_dias in TIPOS_EXAME_INICIAIS:
        existe = (
            await session.execute(select(TipoExame.id).where(TipoExame.codigo == codigo))
        ).scalar_one_or_none()
        if existe is None:
            session.add(TipoExame(codigo=codigo, nome=nome, prefixo=prefixo, sla_dias=sla_dias))

    for codigo, nome in PAPEIS_INICIAIS:
        existe = (await session.execute(select(Papel.id).where(Papel.codigo == codigo))).scalar_one_or_none()
        if existe is None:
            session.add(Papel(codigo=codigo, nome=nome))

    await session.commit()
