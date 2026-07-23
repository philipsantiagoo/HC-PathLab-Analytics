from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ParteMacroscopiaCreate(BaseModel):
    identificador: str = Field(min_length=1, max_length=20)
    estrutura: str = Field(min_length=1, max_length=500)
    coloracao: str = Field(default="HE", min_length=1, max_length=100)
    observacoes: Optional[str] = Field(default=None, max_length=2000)


class MacroscopiaCreate(BaseModel):
    """Registro da macroscopia de um frasco + quantidade de cassetes a gerar."""

    id_frasco: str
    descricao: str
    partes: list[ParteMacroscopiaCreate] = Field(min_length=1, max_length=200)


class MacroscopiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_frasco: str
    descricao: str
    data_realizacao: Optional[datetime] = None
    responsavel: Optional[str] = None
    numero_cassetes: int
