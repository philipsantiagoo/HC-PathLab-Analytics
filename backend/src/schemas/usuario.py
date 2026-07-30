"""Usuários candidatos a receber um repasse."""

from typing import Optional

from pydantic import BaseModel, Field


class UsuarioCandidatoOut(BaseModel):
    """Candidato ao repasse.

    ``origem`` diz de onde o nome veio: ``perfil`` para quem já está em
    ``perfis_usuarios`` (populada no login) e ``historico`` para usernames
    deduzidos do que já foi gravado no fluxo. A tabela de perfis só ganha uma
    linha por login, então sem o histórico a lista nasceria praticamente vazia.
    """

    username: str
    nome_exibicao: Optional[str] = None
    email: Optional[str] = None
    departamento: Optional[str] = None
    origem: str = "perfil"


class RepasseCreate(BaseModel):
    para_username: str = Field(min_length=1, max_length=255)
    # Opcional: quando o destinatário ainda não tem linha em perfis_usuarios,
    # o frontend manda o nome para a fila dele já sair legível.
    para_nome: Optional[str] = Field(default=None, max_length=255)
    motivo: str = Field(min_length=3, max_length=1000)
