from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from .etapas import EtapaHistoricoOut, LinhaFilaOut, PosseOut


class IniciarLoteRequest(BaseModel):
    # Sem campo de responsável: quem responde pelo lote é quem assumiu a etapa,
    # e é a conta autenticada que o controller registra. Aceitar um nome do
    # cliente abria espaço para assinar o lote em nome de outra pessoa.
    cassete_ids: List[str] = Field(..., min_length=1, description="IDs dos cassetes a incluir no lote")
    observacoes: Optional[str] = None


class ConcluirLoteRequest(BaseModel):
    observacoes: Optional[str] = None


class LoteOut(BaseModel):
    id: str
    responsavel: Optional[str]
    status: str
    data_inicio: Optional[datetime]
    data_fim: Optional[datetime]
    observacoes: Optional[str]
    data_criacao: Optional[datetime]

    model_config = {"from_attributes": True}


class CasseteFilaOut(BaseModel):
    id: str
    id_exame: Optional[str] = None
    letra_fragmento: str
    qr_code: str
    status: str
    codigo_interno_frasco: Optional[str] = None
    numero_solicitacao: Optional[str] = None
    paciente_nome: Optional[str] = None
    data_criacao: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LaminaResumoOut(BaseModel):
    id: str
    codigo_lamina: str
    numero_lamina: int
    coloracao: str
    qr_code: str
    status: str


class BlocoResumoOut(BaseModel):
    id: str
    codigo_bloco: str
    qr_code: str
    status: str


class CasseteWorkspaceOut(BaseModel):
    """O cassete com toda a sua descendência, para a bancada enxergar o exame
    inteiro em vez de um item de cada vez."""

    id: str
    identificador: str
    qr_code: str
    status: str
    coloracao_padrao: str
    descricao_estrutura: Optional[str] = None
    id_lote_processamento: Optional[str] = None
    bloco: Optional[BlocoResumoOut] = None
    laminas: list[LaminaResumoOut] = []


class ProgressoProcessamentoOut(BaseModel):
    total_cassetes: int
    cassetes_processados: int
    total_blocos: int
    total_laminas: int


class LoteResumoOut(BaseModel):
    id: str
    responsavel: Optional[str] = None
    status: str
    observacoes: Optional[str] = None
    iniciado_em: Optional[datetime] = None
    concluido_em: Optional[datetime] = None


class ProcessamentoWorkspaceOut(BaseModel):
    exame: LinhaFilaOut
    posse: PosseOut
    historico_etapas: list[EtapaHistoricoOut] = []
    cassetes: list[CasseteWorkspaceOut] = []
    lotes: list[LoteResumoOut] = []
    progresso: ProgressoProcessamentoOut
    # O que ainda impede o envio à Microscopia, em linguagem de bancada.
    pendencias_conclusao: list[str] = []
    pode_concluir: bool = False


class ConclusaoProcessamentoOut(BaseModel):
    id_exame: str
    numero_solicitacao: Optional[str] = None
    status: str
    total_laminas: int = 0
