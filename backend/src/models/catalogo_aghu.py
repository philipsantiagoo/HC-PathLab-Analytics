"""Catálogos e espelho imutável da integração com o AGHU."""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from ..resources.database import Base


class TipoExame(Base):
    __tablename__ = "tipos_exame"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo = Column(String(8), unique=True, nullable=False, index=True)  # HP | CG | CCV | IH | CO
    nome = Column(String(100), nullable=False)
    prefixo = Column(String(8), unique=True, nullable=False)
    sla_dias = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)


class CatalogoExameAghu(Base):
    __tablename__ = "catalogo_exames_aghu"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo_laboratorio = Column(String(30), nullable=False)
    sigla_aghu = Column(String(30), nullable=False)
    nome_aghu = Column(String(255), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    primeira_vez_visto_em = Column(DateTime, server_default=func.now(), nullable=False)
    ultima_vez_visto_em = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("codigo_laboratorio", "sigla_aghu", name="uq_catalogo_aghu_lab_sigla"),
    )


class MapeamentoTipoExameAghu(Base):
    __tablename__ = "mapeamentos_tipo_exame_aghu"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_catalogo_exame_aghu = Column(String, ForeignKey("catalogo_exames_aghu.id"), nullable=False, index=True)
    id_tipo_exame = Column(String, ForeignKey("tipos_exame.id"), nullable=False, index=True)
    valido_desde = Column(Date, nullable=True)
    valido_ate = Column(Date, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    observacoes = Column(Text, nullable=True)
    aprovado_por = Column(String, nullable=True)
    aprovado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)


class LoteIntegracao(Base):
    __tablename__ = "lotes_integracao"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    origem = Column(String(50), nullable=False)  # CSV | AGHU_VIEW
    arquivo_origem = Column(String(500), nullable=True)
    hash_origem = Column(String(64), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="Em andamento")
    linhas_lidas = Column(Integer, nullable=False, default=0)
    linhas_inseridas = Column(Integer, nullable=False, default=0)
    linhas_atualizadas = Column(Integer, nullable=False, default=0)
    linhas_rejeitadas = Column(Integer, nullable=False, default=0)
    erro = Column(Text, nullable=True)
    iniciado_em = Column(DateTime, server_default=func.now(), nullable=False)
    concluido_em = Column(DateTime, nullable=True)


class SolicitacaoAghu(Base):
    __tablename__ = "solicitacoes_aghu"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo_solicitacao_aghu = Column(String(40), unique=True, nullable=False, index=True)
    codigo_paciente_aghu = Column(String(40), nullable=True, index=True)
    prontuario = Column(String(40), nullable=True, index=True)
    nome_paciente_origem = Column(String(255), nullable=True)
    data_nascimento_origem = Column(Date, nullable=True)
    data_solicitacao = Column(Date, nullable=True, index=True)
    convenio = Column(String(100), nullable=True)
    origem_atendimento = Column(String(100), nullable=True)
    unidade = Column(String(255), nullable=True)
    informacoes_clinicas = Column(Text, nullable=True)
    status_aghu = Column(String(80), nullable=True)
    cancelado_em = Column(DateTime, nullable=True)
    atualizado_no_aghu_em = Column(DateTime, nullable=True)
    id_ultimo_lote_integracao = Column(String, ForeignKey("lotes_integracao.id"), nullable=True)
    payload_origem = Column(JSON, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ItemSolicitacaoAghu(Base):
    __tablename__ = "itens_solicitacao_aghu"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_solicitacao_aghu = Column(String, ForeignKey("solicitacoes_aghu.id"), nullable=False, index=True)
    sequencial_item_aghu = Column(String(40), nullable=False)
    id_catalogo_exame_aghu = Column(String, ForeignKey("catalogo_exames_aghu.id"), nullable=False, index=True)
    descricao_material = Column(Text, nullable=True)
    status_aghu = Column(String(80), nullable=True)
    cancelado_em = Column(DateTime, nullable=True)
    payload_origem = Column(JSON, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_solicitacao_aghu", "sequencial_item_aghu", name="uq_item_aghu_solicitacao_sequencial"),
    )


class AmostraAghu(Base):
    __tablename__ = "amostras_aghu"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_solicitacao_aghu = Column(String, ForeignKey("solicitacoes_aghu.id"), nullable=False, index=True)
    numero_amostra_aghu = Column(String(40), nullable=False)
    codigo_barras_externo = Column(String(100), nullable=True, unique=True)
    recebida_em = Column(DateTime, nullable=True)
    payload_origem = Column(JSON, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_solicitacao_aghu", "numero_amostra_aghu", name="uq_amostra_aghu_solicitacao_numero"),
    )


class ItemAmostraAghu(Base):
    __tablename__ = "itens_amostras_aghu"

    id_item_solicitacao_aghu = Column(String, ForeignKey("itens_solicitacao_aghu.id"), primary_key=True)
    id_amostra_aghu = Column(String, ForeignKey("amostras_aghu.id"), primary_key=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
