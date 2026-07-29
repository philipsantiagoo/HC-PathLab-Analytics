"""Persiste a identificação individual dos cassetes na macroscopia.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cassetes") as batch:
        batch.add_column(sa.Column("descricao_estrutura", sa.Text(), nullable=True))
        batch.add_column(sa.Column("observacoes_macroscopia", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cassetes") as batch:
        batch.drop_column("observacoes_macroscopia")
        batch.drop_column("descricao_estrutura")
