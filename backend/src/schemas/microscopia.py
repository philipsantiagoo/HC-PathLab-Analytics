"""Microscopia: laudo prévio, revisão e saídas da etapa.

Nenhum destes contratos aceita um campo ``responsavel``: quem assina é sempre o
usuário do token. Antes a tela mandava um nome escolhido num ``select``, o que
permitia registrar um laudo em nome de outra pessoa.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .etapas import EtapaHistoricoOut, LinhaFilaOut, PosseOut


class LaudoPrevioCreate(BaseModel):
    laudo: str = Field(min_length=1, max_length=20000)


class LiberacaoCreate(BaseModel):
    conclusao: Optional[str] = Field(default=None, max_length=20000)


class ComplementoCreate(BaseModel):
    marcadores: str = Field(min_length=1, max_length=1000)


class RevisaoInternaCreate(BaseModel):
    motivo: str = Field(min_length=3, max_length=2000)


class LaminaMicroscopiaOut(BaseModel):
    id: str
    codigo_lamina: str
    coloracao: str
    status: str
    qr_code: str
    codigo_bloco: Optional[str] = None
    cassete: Optional[str] = None


class LaudoOut(BaseModel):
    laudo_previo: Optional[str] = None
    residente: Optional[str] = None
    laudo_previo_em: Optional[datetime] = None
    conclusao: Optional[str] = None
    patologista: Optional[str] = None
    liberado_em: Optional[datetime] = None
    ciclo: int = 1


class MicroscopiaWorkspaceOut(BaseModel):
    exame: LinhaFilaOut
    posse: PosseOut
    historico_etapas: list[EtapaHistoricoOut] = []
    subetapa: Optional[str] = None
    papel_esperado: Optional[str] = None
    laminas: list[LaminaMicroscopiaOut] = []
    laudo: Optional[LaudoOut] = None
    pode_registrar_laudo_previo: bool = False
    pode_revisar: bool = False


class ResultadoEtapaOut(BaseModel):
    id_exame: str
    numero_solicitacao: Optional[str] = None
    status: str
