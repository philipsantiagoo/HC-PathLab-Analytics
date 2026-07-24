"""
Pacote de modelos SQLAlchemy do banco de dados da aplicação (App DB).

Importar este pacote registra todos os modelos em `Base.metadata`, o que é
necessário para:
  - `Base.metadata.create_all` no startup (src/main.py);
  - `--autogenerate` do Alembic (alembic/env.py importa este pacote).
"""

from .refresh_token import RefreshToken
from .paciente_local import PacienteLocal
from .exame import Exame
from .frasco import Frasco
from .cassete import Cassete
from .macroscopia import Macroscopia
from .parte_macroscopia import ParteMacroscopia
from .historico_movimentacao import HistoricoMovimentacao
from .lote_processamento import LoteProcessamento
from .bloco_parafina import BlocoParafina
from .lamina import Lamina
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
from .contador_numeracao import ContadorNumeracaoExame

__all__ = [
    "RefreshToken",
    "PacienteLocal",
    "Exame",
    "Frasco",
    "Cassete",
    "Macroscopia",
    "ParteMacroscopia",
    "HistoricoMovimentacao",
    "LoteProcessamento",
    "BlocoParafina",
    "Lamina",
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
    "ContadorNumeracaoExame",
]
