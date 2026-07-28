"""Cria a reconstrução canônica de patologia em paralelo ao legado.

Nenhuma tabela do schema public é removida nesta migration. O corte para v2 só
deve ocorrer após importar o CSV, revisar pendências e homologar os totais.
"""

from alembic import op
import sqlalchemy as sa


revision = "h1a2b3c4d5e6"
down_revision = "g9b0c1d2e3f4"
branch_labels = None
depends_on = None

SCHEMA = "pathlab_v2"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "tipos_exame",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("codigo", sa.String(8), nullable=False, unique=True),
        sa.Column("codigo_lab", sa.String(20), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("prefixo", sa.String(8), nullable=False, unique=True),
        sa.Column("sla_dias", sa.Integer()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema=SCHEMA,
    )
    op.bulk_insert(
        sa.table(
            "tipos_exame",
            sa.column("id"), sa.column("codigo"), sa.column("codigo_lab"),
            sa.column("nome"), sa.column("prefixo"), sa.column("sla_dias"),
            schema=SCHEMA,
        ),
        [
            {"id": "tipo-ccv", "codigo": "CCV", "codigo_lab": "139", "nome": "Citologia Cérvico-vaginal", "prefixo": "CCV", "sla_dias": 20},
            {"id": "tipo-cg", "codigo": "CG", "codigo_lab": "203", "nome": "Citologia Geral", "prefixo": "CG", "sla_dias": 20},
            {"id": "tipo-cong", "codigo": "CONG", "codigo_lab": "205", "nome": "Congelação", "prefixo": "CONG", "sla_dias": 1},
            {"id": "tipo-hp", "codigo": "HP", "codigo_lab": "207", "nome": "Histopatológico", "prefixo": "HP", "sla_dias": 20},
            {"id": "tipo-ihq", "codigo": "IHQ", "codigo_lab": "209", "nome": "Imuno-histoquímica", "prefixo": "IHQ", "sla_dias": 20},
        ],
        multiinsert=False,
    )

    op.create_table(
        "pacientes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chave_origem", sa.String(128), nullable=False, unique=True),
        sa.Column("prontuario", sa.String(40)),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("data_nascimento", sa.Date()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_v2_pacientes_prontuario", "pacientes", ["prontuario"], schema=SCHEMA)

    op.create_table(
        "importacoes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("arquivo_origem", sa.String(500), nullable=False),
        sa.Column("hash_arquivo", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="EM_ANDAMENTO"),
        sa.Column("linhas_lidas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linhas_rejeitadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("casos_prontos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("casos_revisao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("iniciado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime()),
        sa.Column("erro", sa.Text()),
        schema=SCHEMA,
    )

    op.create_table(
        "linhas_importacao",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_importacao", sa.String(), sa.ForeignKey(f"{SCHEMA}.importacoes.id"), nullable=False),
        sa.Column("ordem_origem", sa.Integer(), nullable=False),
        sa.Column("hash_origem", sa.String(64), nullable=False),
        sa.Column("codigo_solicitacao", sa.String(40), nullable=False),
        sa.Column("numero_amostra", sa.Integer(), nullable=False),
        sa.Column("codigo_lab", sa.String(20), nullable=False),
        sa.Column("tipo_exame", sa.String(8), nullable=False),
        sa.Column("chave_paciente_origem", sa.String(128), nullable=False),
        sa.Column("codigo_conjunto_amostras", sa.String(40)),
        sa.Column("situacao", sa.String(30), nullable=False, server_default="PENDENTE"),
        sa.Column("pendencias", sa.JSON(), nullable=False),
        sa.Column("payload_origem", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("hash_origem", name="uq_linha_importacao_hash_origem"),
        schema=SCHEMA,
    )
    op.create_index("ix_v2_linhas_importacao_importacao", "linhas_importacao", ["id_importacao"], schema=SCHEMA)

    op.create_table(
        "casos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chave_origem", sa.String(255), nullable=False, unique=True),
        sa.Column("id_paciente", sa.String(), sa.ForeignKey(f"{SCHEMA}.pacientes.id"), nullable=False),
        sa.Column("data_solicitacao", sa.Date()),
        sa.Column("situacao_importacao", sa.String(30), nullable=False, server_default="PRONTO"),
        sa.Column("pendencias", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_v2_casos_paciente", "casos", ["id_paciente"], schema=SCHEMA)

    op.create_table(
        "exames",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_caso", sa.String(), sa.ForeignKey(f"{SCHEMA}.casos.id"), nullable=False),
        sa.Column("id_tipo_exame", sa.String(), sa.ForeignKey(f"{SCHEMA}.tipos_exame.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="AGUARDANDO_RECEBIMENTO"),
        sa.Column("numero_local", sa.String(40), unique=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_caso", "id_tipo_exame", name="uq_exame_caso_tipo"),
        schema=SCHEMA,
    )

    op.create_table(
        "amostras",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_caso", sa.String(), sa.ForeignKey(f"{SCHEMA}.casos.id"), nullable=False),
        sa.Column("id_exame", sa.String(), sa.ForeignKey(f"{SCHEMA}.exames.id"), nullable=False),
        sa.Column("id_linha_importacao", sa.String(), sa.ForeignKey(f"{SCHEMA}.linhas_importacao.id"), nullable=False, unique=True),
        sa.Column("numero_amostra", sa.Integer(), nullable=False),
        sa.Column("codigo_solicitacao", sa.String(40), nullable=False),
        sa.Column("descricao_material", sa.Text()),
        sa.Column("status", sa.String(40), nullable=False, server_default="AGUARDANDO_RECEBIMENTO"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_caso", "numero_amostra", "id_linha_importacao", name="uq_amostra_caso_numero_origem"),
        schema=SCHEMA,
    )
    op.create_index("ix_v2_amostras_caso", "amostras", ["id_caso"], schema=SCHEMA)
    op.create_index("ix_v2_amostras_exame", "amostras", ["id_exame"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("amostras", schema=SCHEMA)
    op.drop_table("exames", schema=SCHEMA)
    op.drop_table("casos", schema=SCHEMA)
    op.drop_table("linhas_importacao", schema=SCHEMA)
    op.drop_table("importacoes", schema=SCHEMA)
    op.drop_table("pacientes", schema=SCHEMA)
    op.drop_table("tipos_exame", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
