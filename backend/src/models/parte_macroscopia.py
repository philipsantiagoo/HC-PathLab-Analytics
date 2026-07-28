import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint

from ..resources.database import Base


class ParteMacroscopia(Base):
    """Parte anatômica identificada durante a macroscopia de uma peça."""

    __tablename__ = "partes_macroscopia"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_macroscopia = Column(
        String, ForeignKey("macroscopias.id"), nullable=False, index=True
    )
    ordinal = Column(Integer, nullable=False)
    letra_identificacao = Column(String, nullable=False)
    descricao_estrutura = Column(Text, nullable=False)
    quantidade_fragmentos = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "id_macroscopia",
            "ordinal",
            name="uq_parte_macroscopia_ordinal",
        ),
        UniqueConstraint(
            "id_macroscopia",
            "letra_identificacao",
            name="uq_parte_macroscopia_letra",
        ),
    )
