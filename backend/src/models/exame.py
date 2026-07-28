import uuid

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from ..resources.database import Base


class Exame(Base):
    """
    Solicitação patológica (nível superior da hierarquia de rastreabilidade).

    `numero_solicitacao` segue o formato PREFIXO-NNNN/AA.S (ex: HP-0001/26.1),
    igual ao padrão usado pela equipe e pelo frontend.
    `status` é gerido pela máquina de estados (src/services/maquina_estados.py)
    e deve bater com os valores de frontend/src/constants/statuses.ts.
    """

    __tablename__ = "exames"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    numero_solicitacao = Column(String, unique=True, index=True, nullable=False)

    # Campos de codificação do exame (derivam numero_solicitacao)
    tipo_exame = Column(String, nullable=False, default="HP")  # HP | CG | CCV | IH | CO
    id_tipo_exame = Column(String, ForeignKey("tipos_exame.id"), nullable=True, index=True)
    sequencial = Column(Integer, nullable=True)   # sequencial por tipo+ano+semestre
    ano = Column(Integer, nullable=True)
    semestre = Column(Integer, nullable=True)     # 1 = jan-jun, 2 = jul-dez

    id_paciente = Column(
        String, ForeignKey("pacientes_local.id"), nullable=False, index=True
    )
    numero_exame_aghu = Column(String, nullable=True)
    id_item_solicitacao_aghu = Column(
        String, ForeignKey("itens_solicitacao_aghu.id"), nullable=True, unique=True, index=True
    )
    id_exame_pai = Column(String, ForeignKey("exames.id"), nullable=True, index=True)
    tipo_peca = Column(String, nullable=True)
    topografia = Column(String, nullable=True)
    status = Column(String, nullable=False, default="Na Recepção")
    data_recebimento = Column(DateTime, server_default=func.now())
    data_conclusao = Column(DateTime, nullable=True)
    data_criacao = Column(DateTime, server_default=func.now())
    criado_por = Column(String, nullable=True)
    id_criado_por = Column(String, ForeignKey("perfis_usuarios.id"), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("tipo_exame", "ano", "semestre", "sequencial", name="uq_exame_tipo_ano_semestre_sequencial"),
    )
