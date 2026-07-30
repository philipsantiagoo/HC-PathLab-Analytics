"""Cria uma cópia de dados do schema public antes do corte para o schema pathlab."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.resources.database import DatabaseManager


SCHEMA_DESTINO = "legacy_public_20260725"


async def main() -> None:
    load_dotenv()
    dsn = os.getenv("APP_DATABASE_DSN")
    if not dsn:
        raise RuntimeError("APP_DATABASE_DSN não configurada.")
    banco = DatabaseManager(dsn)
    try:
        async with banco.engine.begin() as conn:
            existe = await conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name=:schema"),
                {"schema": SCHEMA_DESTINO},
            )
            if existe.scalar_one_or_none() is not None:
                raise RuntimeError(f"Backup já existe: {SCHEMA_DESTINO}")

            tabelas = (
                await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                )
            ).scalars().all()
            await conn.execute(text(f'CREATE SCHEMA "{SCHEMA_DESTINO}"'))
            for tabela in tabelas:
                await conn.execute(
                    text(
                        f'CREATE TABLE "{SCHEMA_DESTINO}"."{tabela}" '
                        f'AS TABLE public."{tabela}"'
                    )
                )
            print(f"Backup criado: {SCHEMA_DESTINO} ({len(tabelas)} tabelas)")
    finally:
        await banco.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
