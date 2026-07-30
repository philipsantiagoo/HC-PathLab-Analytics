from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ExameFilaMacroOut(BaseModel):
    """Uma linha da fila da macroscopia — sempre um exame, nunca um frasco."""

    id_exame: str
    numero_solicitacao: str
    tipo_exame: Optional[str] = None
    paciente_nome: str
    numero_exame_aghu: Optional[str] = None
    tipo_peca: Optional[str] = None
    total_frascos: int
    etapa_macroscopia: str
    responsavel_macroscopia: Optional[str] = None
    responsavel_macroscopia_nome: Optional[str] = None
    assumido_em: Optional[datetime] = None
    data_entrada: Optional[datetime] = None
    atrasado: bool = False


class ContadoresFilaMacro(BaseModel):
    meus: int
    aguardando: int
    em_andamento: int
    todos: int


class FilaMacroscopiaOut(BaseModel):
    """Página da fila + os contadores das abas.

    Os contadores vêm junto com a página de propósito: evita um round-trip
    extra e mantém os badges consistentes com a lista exibida.
    """

    itens: list[ExameFilaMacroOut]
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int
    contadores: ContadoresFilaMacro


class PosseExameOut(BaseModel):
    responsavel: Optional[str] = None
    responsavel_nome: Optional[str] = None
    assumido_em: Optional[datetime] = None
    etapa_macroscopia: str
    sou_o_dono: bool
    pode_liberar: bool


class ExameWorkspaceOut(BaseModel):
    """Tudo que a estação de macroscopia precisa para abrir um exame."""

    exame: ExameFilaMacroOut
    posse: PosseExameOut
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
