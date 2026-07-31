from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .etapas import EtapaHistoricoOut, FilaOut, LinhaFilaOut, PosseOut

# A fila da macroscopia usa o mesmo contrato das demais estações; o alias existe
# só para os routers continuarem legíveis.
FilaMacroscopiaOut = FilaOut


class FragmentoMacroscopiaCreate(BaseModel):
    coloracao: str = Field(default="HE", min_length=1, max_length=100)
    observacoes: Optional[str] = Field(default=None, max_length=2000)


class ParteMacroscopiaCreate(BaseModel):
    estrutura: str = Field(min_length=1, max_length=500)
    fragmentos: list[FragmentoMacroscopiaCreate] = Field(
        min_length=1, max_length=200
    )


class MacroscopiaCreate(BaseModel):
    """Registro da macroscopia com partes e fragmentos a serem identificados.

    A clivagem é por exame. ``id_frasco`` continua aceito por compatibilidade
    com o cliente antigo — o controller resolve o exame a partir da amostra.
    """

    id_exame: Optional[str] = None
    id_frasco: Optional[str] = None
    descricao: str
    partes: list[ParteMacroscopiaCreate] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def exigir_um_identificador(self):
        if bool(self.id_exame) == bool(self.id_frasco):
            raise ValueError("Informe exatamente um entre id_exame e id_frasco.")
        return self

    @model_validator(mode="after")
    def limitar_total_fragmentos(self):
        total = sum(len(parte.fragmentos) for parte in self.partes)
        if total > 200:
            raise ValueError("A macroscopia pode gerar no máximo 200 fragmentos.")
        return self


class MacroscopiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_exame: str
    descricao: str
    data_realizacao: Optional[datetime] = None
    responsavel: Optional[str] = None
    numero_cassetes: int


class ExameWorkspaceOut(BaseModel):
    """Tudo que a estação de macroscopia precisa para abrir um exame."""

    exame: LinhaFilaOut
    posse: PosseOut
    historico_etapas: list[EtapaHistoricoOut] = []
    frascos: list[dict]
    macroscopia: Optional[MacroscopiaOut] = None
    partes: list[dict] = []
    cassetes: list[dict] = []


class ParteMacroscopiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_macroscopia: str
    ordinal: int
    letra_identificacao: str
    descricao_estrutura: str
    quantidade_fragmentos: int
