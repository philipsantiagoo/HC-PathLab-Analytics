import os
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface

def _get_sql(file_path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sql_path = os.path.join(base_dir, '..', 'sql', file_path)
    with open(sql_path, 'r') as f:
        return f.read()

class SolicitacaoPostgresProvider(SolicitacaoProviderInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def listar_solicitacoes(self) -> List[Dict[str, Any]]:
        query = text(_get_sql("solicitacao/listar_solicitacoes.sql"))
        result = await self.session.execute(query)
        return [dict(row) for row in result.mappings().all()]

    async def listar_solicitacoes_por_prontuario(self, prontuario: int) -> List[Dict[str, Any]]:
        sql = _get_sql("solicitacao/listar_solicitacoes.sql")
        # Injeta o filtro de prontuário antes do ORDER BY
        sql_filtrado = sql.replace(
            "ORDER BY sol.criado_em DESC;",
            "AND pac.prontuario = :prontuario\nORDER BY sol.criado_em DESC;"
        )
        result = await self.session.execute(text(sql_filtrado), {"prontuario": prontuario})
        return [dict(row) for row in result.mappings().all()]
