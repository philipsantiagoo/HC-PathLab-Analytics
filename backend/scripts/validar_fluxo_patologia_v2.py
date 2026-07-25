"""Verificação mínima de leitura do fluxo operacional v2."""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from src.controllers import fluxo_v2_controller as fluxo
from src.resources.database import DatabaseManager


async def main() -> None:
    load_dotenv()
    banco = DatabaseManager(os.environ["APP_DATABASE_DSN"])
    async with banco.async_session_maker() as session:
        dashboard = await fluxo.listar_dashboard(session)
        print(f"dashboard_v2={len(dashboard)}")
        if dashboard:
            print(f"primeiro_codigo={dashboard[0]['solicitacao']}")
        v2_status = (await session.execute(text("select status, count(*) from pathlab_v2.exames group by status order by status"))).all()
        print(f"status_v2={v2_status}")
        legado_existe = (await session.execute(text(
            "select exists (select 1 from information_schema.tables where table_schema='public' and table_name='exames')"
        ))).scalar_one()
        print(f"legado_exames_removido={not legado_existe}")
    await banco.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
