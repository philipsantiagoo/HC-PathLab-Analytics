"""
Pacote de modelos SQLAlchemy do banco de dados da aplicação (App DB).

Importar este pacote registra todos os modelos em `Base.metadata`, o que é
necessário para:
  - `Base.metadata.create_all` no startup (src/main.py);
  - `--autogenerate` do Alembic (alembic/env.py importa este pacote).
"""

from .refresh_token import RefreshToken
from .catalogo_aghu import (
    TipoExame,
    CatalogoExameAghu,
    MapeamentoTipoExameAghu,
    LoteIntegracao,
    SolicitacaoAghu,
    ItemSolicitacaoAghu,
    AmostraAghu,
    ItemAmostraAghu,
)
from .usuarios import PerfilUsuario, Papel, PapelUsuario

__all__ = [
    "RefreshToken",
    "TipoExame",
    "CatalogoExameAghu",
    "MapeamentoTipoExameAghu",
    "LoteIntegracao",
    "SolicitacaoAghu",
    "ItemSolicitacaoAghu",
    "AmostraAghu",
    "ItemAmostraAghu",
    "PerfilUsuario",
    "Papel",
    "PapelUsuario",
]
