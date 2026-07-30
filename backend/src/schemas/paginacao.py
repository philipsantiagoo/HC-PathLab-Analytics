"""Envelope de paginação no servidor.

As filas cresceram para dezenas de milhares de linhas e devolver tudo passou a
custar megabytes por requisição. Toda listagem grande usa este envelope.
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

# Defaults compartilhados entre os routers, para o frontend não precisar
# adivinhar o tamanho da página.
POR_PAGINA_PADRAO = 25
POR_PAGINA_MAXIMO = 200


class PaginaResposta(BaseModel, Generic[T]):
    itens: List[T]
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int


def montar_pagina(itens: List[T], total: int, pagina: int, por_pagina: int) -> dict:
    """Monta o envelope. ``total_paginas`` é no mínimo 1 para a UI não exibir
    "página 1 de 0" quando a fila está vazia."""
    return {
        "itens": itens,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total": total,
        "total_paginas": max(1, -(-total // por_pagina)),
    }
