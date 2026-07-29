from typing import Optional

from pydantic import BaseModel, ConfigDict


class CasseteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    id_frasco: str
    id_parte_macroscopia: Optional[str] = None
    letra_fragmento: str
    qr_code: str
    descricao_estrutura: Optional[str] = None
    observacoes_macroscopia: Optional[str] = None
    coloracao_padrao: str
    status: str
