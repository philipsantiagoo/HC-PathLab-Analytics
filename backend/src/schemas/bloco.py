from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class GerarLaminasRequest(BaseModel):
    quantidade: int = Field(default=1, ge=1, le=20, description="Número de lâminas a gerar")
    coloracao: str = Field(default="HE", description="Coloração padrão (HE, PAS, Giemsa...)")
    # Uma coloração por lâmina. Antes o frontend pedia N lâminas e todas saíam
    # com a mesma coloração da primeira, então a especial pedida na macroscopia
    # sumia do registro.
    coloracoes: Optional[List[str]] = Field(
        default=None, max_length=20,
        description="Coloração de cada lâmina, na ordem. Se omitido, usa 'coloracao' para todas.",
    )

    @model_validator(mode="after")
    def conferir_coloracoes(self):
        if self.coloracoes is not None and len(self.coloracoes) != self.quantidade:
            raise ValueError("A lista de colorações precisa ter exatamente 'quantidade' itens.")
        return self


class BlocoOut(BaseModel):
    id: str
    id_cassete: str
    id_lote: str
    codigo_bloco: str
    qr_code: str
    status: str
    data_criacao: Optional[datetime]
    criado_por: Optional[str]

    model_config = {"from_attributes": True}


class BlocoDetalhe(BaseModel):
    id: str
    codigo_bloco: str
    status: str
    letra_fragmento: Optional[str] = None
    numero_solicitacao: Optional[str] = None
    paciente_nome: Optional[str] = None
    data_criacao: Optional[datetime] = None

    model_config = {"from_attributes": True}
