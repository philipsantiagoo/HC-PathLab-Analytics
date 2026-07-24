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
    """Registro da macroscopia com partes e fragmentos a serem identificados."""

    id_frasco: str
    descricao: str
    partes: list[ParteMacroscopiaCreate] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def limitar_total_fragmentos(self):
        total = sum(len(parte.fragmentos) for parte in self.partes)
        if total > 200:
            raise ValueError("A macroscopia pode gerar no máximo 200 fragmentos.")
        return self


class MacroscopiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_frasco: str
    descricao: str
    data_realizacao: Optional[datetime] = None
    responsavel: Optional[str] = None
    numero_cassetes: int


class ParteMacroscopiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_macroscopia: str
    ordinal: int
    letra_identificacao: str
    descricao_estrutura: str
    quantidade_fragmentos: int
