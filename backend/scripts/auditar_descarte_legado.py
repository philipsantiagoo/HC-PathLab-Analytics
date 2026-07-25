"""Lista as tabelas patológicas legadas e confere a cópia de segurança."""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text

from src.resources.database import DatabaseManager


LEGADO = (
    "pacientes_local", "exames", "frascos", "macroscopias",
    "partes_macroscopia", "cassetes", "lotes_processamento",
    "blocos_parafina", "laminas", "historico_movimentacao",
    "contador_numeracao_exame",
)
BACKUP = "legacy_public_20260725"


async def main() -> None:
    load_dotenv()
    banco = DatabaseManager(os.environ["APP_DATABASE_DSN"])
    async with banco.async_session_maker() as session:
        for tabela in LEGADO:
            existe = (await session.execute(text(
                "select exists (select 1 from information_schema.tables where table_schema='public' and table_name=:t)"
            ), {"t": tabela})).scalar_one()
            copia = (await session.execute(text(
                "select exists (select 1 from information_schema.tables where table_schema=:s and table_name=:t)"
            ), {"s": BACKUP, "t": tabela})).scalar_one()
            qtd_public = (await session.execute(text(f"select count(*) from public.{tabela}"))).scalar_one() if existe else None
            qtd_backup = (await session.execute(text(f"select count(*) from {BACKUP}.{tabela}"))).scalar_one() if copia else None
            backup_ok = bool(copia and qtd_backup is not None)
            removido = not existe
            print(f"{tabela}: removido_do_public={removido} backup={qtd_backup} backup_ok={backup_ok}")
    await banco.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
