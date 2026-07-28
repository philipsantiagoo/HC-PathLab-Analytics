"""Contador transacional da numeração local por tipo, ano e semestre."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from ..resources.database import Base


class ContadorNumeracaoExame(Base):
    __tablename__ = "contadores_numeracao_exames"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tipo_exame = Column(String, ForeignKey("tipos_exame.id"), nullable=False)
    ano = Column(Integer, nullable=False)
    semestre = Column(Integer, nullable=False)
    ultimo_sequencial = Column(Integer, nullable=False, default=0)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_tipo_exame", "ano", "semestre", name="uq_contador_tipo_ano_semestre"),
    )
