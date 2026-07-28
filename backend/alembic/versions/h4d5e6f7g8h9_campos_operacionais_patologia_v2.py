"""Completa os campos necessários às rotas operacionais v2."""

from alembic import op
import sqlalchemy as sa


revision = "h4d5e6f7g8h9"
down_revision = "h3c4d5e6f7g8"
branch_labels = None
depends_on = None

S = "pathlab_v2"


def upgrade() -> None:
    with op.batch_alter_table("pacientes", schema=S) as batch:
        batch.add_column(sa.Column("cpf", sa.String(20)))
        batch.add_column(sa.Column("cns", sa.String(30)))
        batch.add_column(sa.Column("origem", sa.String(100)))
        batch.add_column(sa.Column("criado_por", sa.String(255)))
    with op.batch_alter_table("exames", schema=S) as batch:
        batch.add_column(sa.Column("numero_exame_aghu", sa.String(50)))
        batch.add_column(sa.Column("tipo_peca", sa.String(255)))
        batch.add_column(sa.Column("topografia", sa.String(255)))
        batch.add_column(sa.Column("data_recebimento", sa.DateTime()))
        batch.add_column(sa.Column("data_conclusao", sa.DateTime()))
        batch.add_column(sa.Column("criado_por", sa.String(255)))
    with op.batch_alter_table("amostras", schema=S) as batch:
        batch.add_column(sa.Column("codigo_interno", sa.String(80)))
        batch.add_column(sa.Column("qr_code", sa.String(255)))
        batch.add_column(sa.Column("descricao_macroscopia", sa.Text()))
        batch.add_column(sa.Column("numero_cassetes_gerados", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("criado_por", sa.String(255)))
        batch.create_unique_constraint("uq_v2_amostra_codigo_interno", ["codigo_interno"])
        batch.create_unique_constraint("uq_v2_amostra_qr_code", ["qr_code"])


def downgrade() -> None:
    with op.batch_alter_table("amostras", schema=S) as batch:
        batch.drop_constraint("uq_v2_amostra_qr_code", type_="unique")
        batch.drop_constraint("uq_v2_amostra_codigo_interno", type_="unique")
        batch.drop_column("criado_por")
        batch.drop_column("numero_cassetes_gerados")
        batch.drop_column("descricao_macroscopia")
        batch.drop_column("qr_code")
        batch.drop_column("codigo_interno")
    with op.batch_alter_table("exames", schema=S) as batch:
        for column in ("criado_por", "data_conclusao", "data_recebimento", "topografia", "tipo_peca", "numero_exame_aghu"):
            batch.drop_column(column)
    with op.batch_alter_table("pacientes", schema=S) as batch:
        for column in ("criado_por", "origem", "cns", "cpf"):
            batch.drop_column(column)
