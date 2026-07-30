from typing import List

from pydantic import BaseModel

from .cassete import CasseteOut
from .etiqueta import EtiquetaOut
from .exame import ExameOut
from .frasco import FrascoOut
from .macroscopia import MacroscopiaOut, ParteMacroscopiaOut


class TriagemResult(BaseModel):
    """Resposta do registro de recebimento (triagem)."""

    exame: ExameOut
    frasco: FrascoOut
    etiqueta: EtiquetaOut


class MacroscopiaResult(BaseModel):
    """Resposta do registro de macroscopia, com os cassetes gerados.

    ``frascos`` traz todas as amostras do exame — elas andam juntas. ``frasco``
    (a primeira) permanece por compatibilidade com o cliente antigo.
    """

    macroscopia: MacroscopiaOut
    frasco: FrascoOut
    frascos: List[FrascoOut] = []
    partes: List[ParteMacroscopiaOut]
    cassetes: List[CasseteOut]
    etiquetas: List[EtiquetaOut]
