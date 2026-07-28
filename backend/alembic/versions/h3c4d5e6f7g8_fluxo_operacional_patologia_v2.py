"""Porta o fluxo físico de patologia para pathlab_v2.

As entidades são criadas no schema novo; o legado continua somente como
rollback até os controllers passarem a usar estas tabelas.
"""

from alembic import op
import sqlalchemy as sa


revision = "h3c4d5e6f7g8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None

S = "pathlab_v2"


def upgrade() -> None:
    op.create_table(
        "movimentacoes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_exame", sa.String(), sa.ForeignKey(f"{S}.exames.id")),
        sa.Column("id_amostra", sa.String(), sa.ForeignKey(f"{S}.amostras.id")),
        sa.Column("etapa", sa.String(50), nullable=False),
        sa.Column("status_anterior", sa.String(50)),
        sa.Column("status_novo", sa.String(50), nullable=False),
        sa.Column("usuario_responsavel", sa.String(255)),
        sa.Column("observacoes", sa.Text()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=S,
    )
    op.create_table(
        "macroscopias",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_amostra", sa.String(), sa.ForeignKey(f"{S}.amostras.id"), nullable=False, unique=True),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("responsavel", sa.String(255)),
        sa.Column("numero_cassetes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=S,
    )
    op.create_table(
        "partes_macroscopia",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_macroscopia", sa.String(), sa.ForeignKey(f"{S}.macroscopias.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("letra_identificacao", sa.String(10), nullable=False),
        sa.Column("descricao_estrutura", sa.Text(), nullable=False),
        sa.Column("quantidade_fragmentos", sa.Integer(), nullable=False),
        sa.UniqueConstraint("id_macroscopia", "ordinal", name="uq_v2_parte_macro_ordinal"),
        schema=S,
    )
    op.create_table(
        "lotes_processamento",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("responsavel", sa.String(255)),
        sa.Column("status", sa.String(40), nullable=False, server_default="EM_ANDAMENTO"),
        sa.Column("observacoes", sa.Text()),
        sa.Column("iniciado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime()),
        schema=S,
    )
    op.create_table(
        "cassetes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_amostra", sa.String(), sa.ForeignKey(f"{S}.amostras.id"), nullable=False),
        sa.Column("id_parte_macroscopia", sa.String(), sa.ForeignKey(f"{S}.partes_macroscopia.id")),
        sa.Column("id_lote_processamento", sa.String(), sa.ForeignKey(f"{S}.lotes_processamento.id")),
        sa.Column("identificador", sa.String(30), nullable=False),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column("coloracao_padrao", sa.String(30), nullable=False, server_default="HE"),
        sa.Column("status", sa.String(40), nullable=False, server_default="AGUARDANDO_PROCESSAMENTO"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_amostra", "identificador", name="uq_v2_cassete_amostra_identificador"),
        schema=S,
    )
    op.create_table(
        "blocos_parafina",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_cassete", sa.String(), sa.ForeignKey(f"{S}.cassetes.id"), nullable=False),
        sa.Column("id_lote_processamento", sa.String(), sa.ForeignKey(f"{S}.lotes_processamento.id"), nullable=False),
        sa.Column("codigo_bloco", sa.String(80), nullable=False, unique=True),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="AGUARDANDO_CORTE"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=S,
    )
    op.create_table(
        "laminas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_bloco", sa.String(), sa.ForeignKey(f"{S}.blocos_parafina.id"), nullable=False),
        sa.Column("numero_lamina", sa.Integer(), nullable=False),
        sa.Column("codigo_lamina", sa.String(80), nullable=False, unique=True),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column("coloracao", sa.String(30), nullable=False, server_default="HE"),
        sa.Column("status", sa.String(40), nullable=False, server_default="AGUARDANDO_LEITURA"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_bloco", "numero_lamina", name="uq_v2_lamina_bloco_numero"),
        schema=S,
    )


def downgrade() -> None:
    for tabela in ("laminas", "blocos_parafina", "cassetes", "lotes_processamento", "partes_macroscopia", "macroscopias", "movimentacoes"):
        op.drop_table(tabela, schema=S)
