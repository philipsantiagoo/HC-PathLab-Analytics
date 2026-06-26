from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.bloco_parafina import BlocoParafina
from ...models.cassete import Cassete
from ...models.exame import Exame
from ...models.frasco import Frasco
from ...models.lamina import Lamina


class ExameRepository:
    """Acesso ORM aos exames (App DB)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def adicionar(self, exame: Exame) -> None:
        self.session.add(exame)

    async def obter(self, id_exame: str) -> Optional[Exame]:
        return await self.session.get(Exame, id_exame)

    async def listar(self) -> List[Exame]:
        stmt = select(Exame).order_by(Exame.data_recebimento.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def obter_por_lamina(self, id_lamina: str) -> Optional[Exame]:
        stmt = (
            select(Exame)
            .join(Frasco, Exame.id == Frasco.id_exame)
            .join(Cassete, Frasco.id == Cassete.id_frasco)
            .join(BlocoParafina, Cassete.id == BlocoParafina.id_cassete)
            .join(Lamina, BlocoParafina.id == Lamina.id_bloco)
            .where(Lamina.id == id_lamina)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
