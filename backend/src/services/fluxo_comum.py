"""Vocabulário e utilitários compartilhados pelos controllers do fluxo.

Antes cada controller repetia as constantes de status e os helpers de data e
movimentação. Com quatro estações usando a mesma mecânica, uma divergência de
string entre dois arquivos tira exames da fila em silêncio.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from ..models.patologia import AmostraPatologia, ExamePatologia, MovimentacaoPatologia


# --- Status globais do exame (posição geral no fluxo) --------------------
S_RECEPCAO = "Na Recepção"
S_AGUARDANDO_MACRO = "Aguardando Macroscopia"
S_EM_MACRO = "Em Macroscopia"
S_EM_PROCESSAMENTO = "Em Processamento"
S_EM_MICRO = "Em Microscopia"
S_REVISAO = "Revisão Pendente"
S_LIBERADO = "Liberado"
S_EM_CONGELAMENTO = "Em Congelamento"

# --- Status de itens (amostra, cassete, bloco, lâmina) -------------------
S_AGUARDANDO_PROCESSAMENTO = "Aguardando Processamento"
S_PROCESSAMENTO = "Em Processamento"
S_PROCESSADO = "Processamento Completo"
S_AGUARDANDO_CORTE = "Aguardando Corte"
S_AGUARDANDO_MICRO = "Aguardando Microscopia"
S_CORTADO = "Cortado"

SLA_DIAS = 20


def agora() -> datetime:
    """UTC sem tzinfo — as colunas são ``timestamp without time zone``."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def atrasado(entrada: Optional[datetime], referencia: Optional[datetime] = None) -> bool:
    """SLA estourado. ``referencia`` é passada pelos laços para não recalcular por linha."""
    if entrada is None:
        return False
    return ((referencia or agora()) - entrada).days >= SLA_DIAS


async def proximo_numero_exame(session, tipo) -> tuple[str, int, int, int]:
    """Próximo código local do tipo: ``PREFIXO-NNNN/AA.S``.

    ``exames.ano`` guarda o ano com quatro dígitos (2026) — é assim que os
    19 mil exames importados estão gravados. O cálculo filtrava por ``26`` e
    portanto não achava nada, voltava ao sequencial 1 e colidia com a UNIQUE de
    ``numero_local``. Só o rótulo exibido usa dois dígitos.

    Resta uma janela de corrida entre o MAX e o INSERT; quem chama trata o
    ``IntegrityError`` devolvendo 409. A solução definitiva é um contador com
    ``ON CONFLICT ... RETURNING`` por (tipo, ano, semestre), como o que existe
    em ``helpers.identificacao`` para o schema legado.
    """
    from sqlalchemy import func as _func

    from ..models.patologia import ExamePatologia as _Exame

    referencia = agora()
    ano = referencia.year
    semestre = 1 if referencia.month <= 6 else 2
    maior = (await session.execute(
        select(_func.max(_Exame.sequencial)).where(
            _Exame.id_tipo_exame == tipo.id,
            _Exame.ano == ano,
            _Exame.semestre == semestre,
        )
    )).scalar_one() or 0
    sequencial = maior + 1
    return f"{tipo.prefixo}-{sequencial:04d}/{ano % 100:02d}.{semestre}", sequencial, ano, semestre


def registrar_movimentacao(
    session,
    *,
    exame=None,
    amostra=None,
    etapa: str,
    anterior: Optional[str],
    novo: str,
    usuario: Optional[str],
    observacoes: Optional[str] = None,
) -> None:
    """Trilha de auditoria. Só adiciona à sessão; quem chama controla o commit."""
    session.add(MovimentacaoPatologia(
        id=str(uuid.uuid4()),
        id_exame=exame.id if exame else None,
        id_amostra=amostra.id if amostra else None,
        etapa=etapa,
        status_anterior=anterior,
        status_novo=novo,
        usuario_responsavel=usuario,
        observacoes=observacoes,
    ))


# Contagem de frascos como subquery escalar correlacionada. Com JOIN + GROUP BY
# o LIMIT passaria a ser aplicado depois de agregar as 28k amostras; aqui roda
# uma vez por linha da página, cada uma um index scan em ix_amostras_id_exame.
TOTAL_FRASCOS = (
    select(func.count(AmostraPatologia.id))
    .where(AmostraPatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("total_frascos")
)
