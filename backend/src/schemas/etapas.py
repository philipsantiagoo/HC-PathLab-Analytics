"""Contrato compartilhado das filas e da posse por etapa.

As URLs continuam separadas por setor, mas o formato da fila, do bloco de posse
e do histórico é o mesmo nas quatro estações — é o que permite ao frontend ter
um único componente de fila e um único card de posse.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LinhaFilaOut(BaseModel):
    """Uma linha de fila — sempre um exame, nunca um item filho.

    Campos adicionais de cada estação (cassetes, lâminas, ciclos) vêm por cima
    destes; por isso o modelo não é ``extra="forbid"``.
    """

    id_exame: str
    numero_solicitacao: str
    tipo_exame: Optional[str] = None
    paciente_nome: str
    numero_exame_aghu: Optional[str] = None
    tipo_peca: Optional[str] = None
    total_frascos: int = 0
    etapa: str
    situacao: str
    subetapa: Optional[str] = None
    ciclo: int = 1
    responsavel: Optional[str] = None
    responsavel_nome: Optional[str] = None
    assumido_em: Optional[datetime] = None
    entrou_na_etapa_em: Optional[datetime] = None
    data_entrada: Optional[datetime] = None
    atrasado: bool = False
    status_exame: Optional[str] = None

    # Extras por estação (processamento, microscopia, congelamento).
    total_cassetes: Optional[int] = None
    cassetes_processados: Optional[int] = None
    cassetes_pendentes: Optional[int] = None
    total_blocos: Optional[int] = None
    total_laminas: Optional[int] = None
    papel_esperado: Optional[str] = None
    total_ciclos: Optional[int] = None
    situacao_resultado: Optional[str] = None


class ContadoresOut(BaseModel):
    meus: int
    aguardando: int
    em_andamento: int
    todos: int
    # Só a microscopia usa: as duas filas de espera dela são distintas.
    laudo_previo: Optional[int] = None
    revisao: Optional[int] = None


class FilaOut(BaseModel):
    """Página da fila + os contadores das abas.

    Os contadores vêm junto com a página de propósito: evita um round-trip
    extra e mantém os badges consistentes com a lista exibida.
    """

    itens: list[LinhaFilaOut]
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int
    contadores: ContadoresOut


class PosseOut(BaseModel):
    etapa: str
    situacao: str
    subetapa: Optional[str] = None
    ciclo: int = 1
    responsavel: Optional[str] = None
    responsavel_nome: Optional[str] = None
    assumido_em: Optional[datetime] = None
    sou_o_dono: bool = False
    pode_assumir: bool = False
    pode_liberar: bool = False
    pode_executar: bool = False


class EtapaHistoricoOut(BaseModel):
    etapa: str
    situacao: str
    subetapa: Optional[str] = None
    ciclo: int = 1
    responsavel_nome: Optional[str] = None
    assumido_em: Optional[datetime] = None
    concluido_em: Optional[datetime] = None
    criado_em: Optional[datetime] = None
