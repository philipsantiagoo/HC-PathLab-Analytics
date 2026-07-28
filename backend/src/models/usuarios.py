"""Identidade local e RBAC. Senhas continuam sob responsabilidade do AD/Auth."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from ..resources.database import Base


class PerfilUsuario(Base):
    __tablename__ = "perfis_usuarios"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_externo = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    nome_exibicao = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    departamento = Column(String(255), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    ultimo_login_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Papel(Base):
    __tablename__ = "papeis"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo = Column(String(50), unique=True, nullable=False)
    nome = Column(String(100), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)


class PapelUsuario(Base):
    __tablename__ = "papeis_usuarios"

    id_usuario = Column(String, ForeignKey("perfis_usuarios.id"), primary_key=True)
    id_papel = Column(String, ForeignKey("papeis.id"), primary_key=True)
    unidade = Column(String(255), primary_key=True, nullable=False, default="")
    valido_desde = Column(DateTime, server_default=func.now(), nullable=False)
    valido_ate = Column(DateTime, nullable=True)
