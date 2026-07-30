"""Modelo canônico da reconstrução de patologia.

As tabelas ficam no schema ``pathlab``. O schema ``public`` guarda apenas
identidade/RBAC, catálogos AGHU e os dados de integração.
"""

import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String,
    Text, UniqueConstraint, text,
)
from sqlalchemy.sql import func

from ..resources.database import Base


SCHEMA_PATOLOGIA = "pathlab"


class TipoExamePatologia(Base):
    __tablename__ = "tipos_exame"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo = Column(String(8), nullable=False, unique=True)
    codigo_lab = Column(String(20), nullable=False, unique=True)
    nome = Column(String(100), nullable=False)
    prefixo = Column(String(8), nullable=False, unique=True)
    sla_dias = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)


class PacientePatologia(Base):
    __tablename__ = "pacientes"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chave_origem = Column(String(128), nullable=False, unique=True)
    prontuario = Column(String(40), nullable=True, index=True)
    nome = Column(String(255), nullable=False)
    data_nascimento = Column(Date, nullable=True)
    cpf = Column(String(20), nullable=True)
    cns = Column(String(30), nullable=True)
    origem = Column(String(100), nullable=True)
    criado_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ImportacaoPatologia(Base):
    __tablename__ = "importacoes"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    arquivo_origem = Column(String(500), nullable=False)
    hash_arquivo = Column(String(64), nullable=False, unique=True)
    status = Column(String(30), nullable=False, default="EM_ANDAMENTO")
    linhas_lidas = Column(Integer, nullable=False, default=0)
    linhas_rejeitadas = Column(Integer, nullable=False, default=0)
    casos_prontos = Column(Integer, nullable=False, default=0)
    casos_revisao = Column(Integer, nullable=False, default=0)
    iniciado_em = Column(DateTime, nullable=False, server_default=func.now())
    concluido_em = Column(DateTime, nullable=True)
    erro = Column(Text, nullable=True)


class LinhaImportacaoPatologia(Base):
    __tablename__ = "linhas_importacao"
    __table_args__ = (
        UniqueConstraint("hash_origem", name="uq_linha_importacao_hash_origem"),
        {"schema": SCHEMA_PATOLOGIA},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_importacao = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.importacoes.id"), nullable=False, index=True)
    ordem_origem = Column(Integer, nullable=False)
    hash_origem = Column(String(64), nullable=False)
    codigo_solicitacao = Column(String(40), nullable=False)
    numero_amostra = Column(Integer, nullable=False)
    codigo_lab = Column(String(20), nullable=False)
    tipo_exame = Column(String(8), nullable=False)
    chave_paciente_origem = Column(String(128), nullable=False)
    codigo_conjunto_amostras = Column(String(40), nullable=True)
    situacao = Column(String(30), nullable=False, default="PENDENTE")
    pendencias = Column(JSON, nullable=False, default=list)
    payload_origem = Column(JSON, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class CasoPatologia(Base):
    __tablename__ = "casos"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chave_origem = Column(String(255), nullable=False, unique=True)
    id_paciente = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.pacientes.id"), nullable=False, index=True)
    data_solicitacao = Column(Date, nullable=True, index=True)
    situacao_importacao = Column(String(30), nullable=False, default="PRONTO")
    pendencias = Column(JSON, nullable=False, default=list)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class ExamePatologia(Base):
    __tablename__ = "exames"
    __table_args__ = (
        UniqueConstraint("id_caso", "id_tipo_exame", name="uq_exame_caso_tipo"),
        # Fila da macroscopia: filtro por etapa + ordenação estável.
        Index("ix_exames_fila_macro", "etapa_macroscopia", "criado_em", "id"),
        Index(
            "ix_exames_responsavel_macro",
            "responsavel_macroscopia",
            "etapa_macroscopia",
            "criado_em",
            postgresql_where=text("responsavel_macroscopia IS NOT NULL"),
        ),
        Index("ix_exames_criado_em", "criado_em", "id"),
        {"schema": SCHEMA_PATOLOGIA},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_caso = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.casos.id"), nullable=False, index=True)
    id_tipo_exame = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.tipos_exame.id"), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="AGUARDANDO_RECEBIMENTO")
    numero_local = Column(String(40), nullable=True, unique=True)
    sequencial = Column(Integer, nullable=True)
    ano = Column(Integer, nullable=True)
    semestre = Column(Integer, nullable=True)
    numero_exame_aghu = Column(String(50), nullable=True)
    tipo_peca = Column(String(255), nullable=True)
    topografia = Column(String(255), nullable=True)
    data_recebimento = Column(DateTime, nullable=True)
    data_conclusao = Column(DateTime, nullable=True)
    criado_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    # --- Posse na macroscopia -------------------------------------------
    # Coluna dedicada em vez de derivar de ``status``: o status é escrito por
    # vários caminhos do fluxo e uma escrita errada tiraria o exame da fila
    # silenciosamente. Além disso ``CONCLUIDA`` precisa sobreviver ao avanço
    # do exame para "Em Processamento".
    etapa_macroscopia = Column(
        String(20), nullable=False, server_default="AGUARDANDO", default="AGUARDANDO"
    )
    # Username do JWT de quem detém o exame. ``macroscopias.responsavel`` é
    # outra coisa: quem finalizou a clivagem.
    responsavel_macroscopia = Column(String(255), nullable=True)
    # Nome de exibição desnormalizado: ``perfis_usuarios`` só é populada no
    # login, então um JOIN devolveria NULL para quase todo mundo.
    responsavel_macroscopia_nome = Column(String(255), nullable=True)
    assumido_em = Column(DateTime, nullable=True)
    macroscopia_concluida_em = Column(DateTime, nullable=True)


class AmostraPatologia(Base):
    __tablename__ = "amostras"
    __table_args__ = (
        UniqueConstraint("id_caso", "numero_amostra", "id_linha_importacao", name="uq_amostra_caso_numero_origem"),
        {"schema": SCHEMA_PATOLOGIA},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_caso = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.casos.id"), nullable=False, index=True)
    id_exame = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.exames.id"), nullable=False, index=True)
    id_linha_importacao = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.linhas_importacao.id"), nullable=True, unique=True)
    numero_amostra = Column(Integer, nullable=False)
    codigo_solicitacao = Column(String(40), nullable=False, index=True)
    descricao_material = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="AGUARDANDO_RECEBIMENTO")
    codigo_interno = Column(String(80), nullable=True, unique=True)
    qr_code = Column(String(255), nullable=True, unique=True)
    descricao_macroscopia = Column(Text, nullable=True)
    numero_cassetes_gerados = Column(Integer, nullable=False, default=0)
    criado_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class MovimentacaoPatologia(Base):
    __tablename__ = "movimentacoes"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_exame = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.exames.id"), nullable=True)
    id_amostra = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.amostras.id"), nullable=True)
    etapa = Column(String(50), nullable=False)
    status_anterior = Column(String(50), nullable=True)
    status_novo = Column(String(50), nullable=False)
    usuario_responsavel = Column(String(255), nullable=True)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class MacroscopiaPatologia(Base):
    """Uma clivagem por exame.

    O exame é a peça; os frascos são apenas como o material chegou. A UNIQUE em
    ``id_exame`` é a última defesa contra duplo submit da tela de clivagem.
    """

    __tablename__ = "macroscopias"
    __table_args__ = (
        UniqueConstraint("id_exame", name="uq_macroscopia_exame"),
        {"schema": SCHEMA_PATOLOGIA},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_exame = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.exames.id"), nullable=False)
    descricao = Column(Text, nullable=False)
    # Quem finalizou a clivagem. Não confundir com
    # ``ExamePatologia.responsavel_macroscopia``, que é quem detém o exame.
    responsavel = Column(String(255), nullable=True)
    numero_cassetes = Column(Integer, nullable=False, default=0)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class ParteMacroscopiaPatologia(Base):
    __tablename__ = "partes_macroscopia"
    __table_args__ = (UniqueConstraint("id_macroscopia", "ordinal", name="uq_parte_macro_ordinal"), {"schema": SCHEMA_PATOLOGIA})

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_macroscopia = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.macroscopias.id"), nullable=False)
    ordinal = Column(Integer, nullable=False)
    letra_identificacao = Column(String(10), nullable=False)
    descricao_estrutura = Column(Text, nullable=False)
    quantidade_fragmentos = Column(Integer, nullable=False)


class LoteProcessamentoPatologia(Base):
    __tablename__ = "lotes_processamento"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    responsavel = Column(String(255), nullable=True)
    status = Column(String(40), nullable=False, default="Em Andamento")
    observacoes = Column(Text, nullable=True)
    iniciado_em = Column(DateTime, nullable=False, server_default=func.now())
    concluido_em = Column(DateTime, nullable=True)


class CassetePatologia(Base):
    __tablename__ = "cassetes"
    __table_args__ = (UniqueConstraint("id_exame", "identificador", name="uq_cassete_exame_identificador"), {"schema": SCHEMA_PATOLOGIA})

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_exame = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.exames.id"), nullable=False, index=True)
    id_parte_macroscopia = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.partes_macroscopia.id"), nullable=True)
    id_lote_processamento = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.lotes_processamento.id"), nullable=True)
    identificador = Column(String(30), nullable=False)
    qr_code = Column(String(255), nullable=False, unique=True)
    coloracao_padrao = Column(String(30), nullable=False, default="HE")
    status = Column(String(40), nullable=False, default="Aguardando Processamento")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class BlocoParafinaPatologia(Base):
    __tablename__ = "blocos_parafina"
    __table_args__ = {"schema": SCHEMA_PATOLOGIA}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_cassete = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.cassetes.id"), nullable=False)
    id_lote_processamento = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.lotes_processamento.id"), nullable=False)
    codigo_bloco = Column(String(80), nullable=False, unique=True)
    qr_code = Column(String(255), nullable=False, unique=True)
    status = Column(String(40), nullable=False, default="Aguardando Corte")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class LaminaPatologia(Base):
    __tablename__ = "laminas"
    __table_args__ = (UniqueConstraint("id_bloco", "numero_lamina", name="uq_lamina_bloco_numero"), {"schema": SCHEMA_PATOLOGIA})

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_bloco = Column(String, ForeignKey(f"{SCHEMA_PATOLOGIA}.blocos_parafina.id"), nullable=False)
    numero_lamina = Column(Integer, nullable=False)
    codigo_lamina = Column(String(80), nullable=False, unique=True)
    qr_code = Column(String(255), nullable=False, unique=True)
    coloracao = Column(String(30), nullable=False, default="HE")
    status = Column(String(40), nullable=False, default="Aguardando Leitura")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
