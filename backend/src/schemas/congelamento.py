"""Congelamento: ciclos de análise e resultado."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .etapas import EtapaHistoricoOut, LinhaFilaOut, PosseOut


class CicloCongelamentoCreate(BaseModel):
    residente: Optional[str] = Field(default=None, max_length=255)
    patologista: Optional[str] = Field(default=None, max_length=255)
    quantidade_laminas: int = Field(default=1, ge=1, le=50)
    diagnostico: str = Field(min_length=1, max_length=5000)
    # LIVRE encerra a etapa e gera o HP correlato; COMPROMETIDA mantém o exame
    # em andamento aguardando novo fragmento; AGUARDANDO só salva o parcial.
    conduta: Literal["LIVRE", "COMPROMETIDA", "AGUARDANDO"]
    observacao: Optional[str] = Field(default=None, max_length=5000)


class CicloCongelamentoOut(BaseModel):
    id: str
    ordinal: int
    residente: Optional[str] = None
    patologista: Optional[str] = None
    quantidade_laminas: int
    diagnostico: str
    conduta: str
    observacao: Optional[str] = None
    registrado_por: Optional[str] = None
    criado_em: Optional[datetime] = None


class CongelamentoOut(BaseModel):
    id: str
    status: str
    resultado_final: Optional[str] = None
    numero_hp_correlato: Optional[str] = None
    id_exame_hp: Optional[str] = None
    liberado_em: Optional[datetime] = None
    liberado_por: Optional[str] = None


class CongelamentoWorkspaceOut(BaseModel):
    exame: LinhaFilaOut
    posse: PosseOut
    historico_etapas: list[EtapaHistoricoOut] = []
    congelamento: Optional[CongelamentoOut] = None
    ciclos: list[CicloCongelamentoOut] = []
    pode_registrar: bool = False
