"""Normaliza a fila inicial v2 após a importação histórica.

O espelho legado já expunha esses itens na macroscopia.  Esta rotina preserva
essa etapa no modelo novo e cria um identificador de amostra para leitura e
etiquetagem. Pode ser executada novamente sem alterar identificadores existentes.
"""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import select

from src.models.patologia_v2 import AmostraPatologia, ExamePatologia
from src.resources.database import DatabaseManager


async def main() -> None:
    load_dotenv()
    banco = DatabaseManager(os.environ["APP_DATABASE_DSN"])
    async with banco.async_session_maker() as session:
        exames = list((await session.execute(select(ExamePatologia))).scalars())
        for exame in exames:
            if exame.status == "AGUARDANDO_RECEBIMENTO":
                exame.status = "Em Macroscopia"

        amostras = list((await session.execute(
            select(AmostraPatologia, ExamePatologia)
            .join(ExamePatologia, AmostraPatologia.id_exame == ExamePatologia.id)
        )).all())
        atualizadas = 0
        for amostra, exame in amostras:
            if amostra.status == "AGUARDANDO_RECEBIMENTO":
                amostra.status = "Aguardando Macroscopia"
            if not amostra.codigo_interno:
                # O UUID torna o código único mesmo nas pendências de revisão
                # que repetem o mesmo número de amostra.
                amostra.codigo_interno = f"{exame.numero_local or amostra.codigo_solicitacao}-A{amostra.numero_amostra}-{amostra.id[:8]}"
                atualizadas += 1
        await session.commit()
        print(f"exames={len(exames)} amostras={len(amostras)} codigos_amostra_criados={atualizadas}")
    await banco.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
