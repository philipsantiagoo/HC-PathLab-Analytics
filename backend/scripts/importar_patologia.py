"""Carrega um CSV homologado no schema pathlab.

Uso:
    python scripts/importar_patologia.py caminho\\vw_solicitacao_atualizado.csv
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.resources.database import DatabaseManager
from src.services.patologia_importer import importar_csv_patologia


async def main(caminho: str) -> None:
    load_dotenv()
    dsn = os.getenv("APP_DATABASE_DSN")
    if not dsn:
        raise RuntimeError("APP_DATABASE_DSN não configurada.")
    banco = DatabaseManager(dsn)
    try:
        async with banco.async_session_maker() as session:
            lote = await importar_csv_patologia(session, caminho)
            print(
                f"Importação {lote.status}: {lote.linhas_lidas} linhas; "
                f"{lote.casos_prontos} casos prontos; {lote.casos_revisao} para revisão."
            )
    finally:
        await banco.close_connection()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Informe o caminho do CSV atualizado.")
    asyncio.run(main(sys.argv[1]))
