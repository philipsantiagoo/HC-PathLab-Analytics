"""Gera códigos locais para todos os exames do schema pathlab.

O sequencial é por tipo, ano e semestre da data de solicitação. Reexecutar o
script não altera códigos já emitidos.
"""

import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.patologia import CasoPatologia, ExamePatologia, TipoExamePatologia
from src.resources.database import DatabaseManager


async def main() -> None:
    load_dotenv()
    dsn = os.getenv("APP_DATABASE_DSN")
    if not dsn:
        raise RuntimeError("APP_DATABASE_DSN não configurada.")
    banco = DatabaseManager(dsn)
    try:
        async with banco.async_session_maker() as session:
            registros = (
                await session.execute(
                    select(ExamePatologia, CasoPatologia, TipoExamePatologia)
                    .join(CasoPatologia, CasoPatologia.id == ExamePatologia.id_caso)
                    .join(TipoExamePatologia, TipoExamePatologia.id == ExamePatologia.id_tipo_exame)
                    .where(ExamePatologia.numero_local.is_(None))
                    .order_by(CasoPatologia.data_solicitacao, ExamePatologia.id)
                )
            ).all()
            contadores: dict[tuple[str, int, int], int] = defaultdict(int)
            for exame, caso, tipo in registros:
                data = caso.data_solicitacao
                if data is None:
                    raise ValueError(f"Exame {exame.id} sem data de solicitação.")
                semestre = 1 if data.month <= 6 else 2
                chave = (tipo.codigo, data.year, semestre)
                contadores[chave] += 1
                sequencial = contadores[chave]
                exame.sequencial = sequencial
                exame.ano = data.year
                exame.semestre = semestre
                exame.numero_local = f"{tipo.prefixo}-{sequencial:04d}/{data.year % 100:02d}.{semestre}"
            await session.commit()
            print(f"Códigos gerados: {len(registros)}")
    finally:
        await banco.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
