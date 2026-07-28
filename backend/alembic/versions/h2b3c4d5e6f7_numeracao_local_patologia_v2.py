"""Adiciona componentes auditáveis do código local no schema v2."""

from alembic import op
import sqlalchemy as sa


revision = "h2b3c4d5e6f7"
down_revision = "h1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exames", schema="pathlab_v2") as batch:
        batch.add_column(sa.Column("sequencial", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ano", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("semestre", sa.Integer(), nullable=True))
        batch.create_unique_constraint(
            "uq_exame_tipo_ano_semestre_sequencial",
            ["id_tipo_exame", "ano", "semestre", "sequencial"],
        )


def downgrade() -> None:
    with op.batch_alter_table("exames", schema="pathlab_v2") as batch:
        batch.drop_constraint("uq_exame_tipo_ano_semestre_sequencial", type_="unique")
        batch.drop_column("semestre")
        batch.drop_column("ano")
        batch.drop_column("sequencial")
