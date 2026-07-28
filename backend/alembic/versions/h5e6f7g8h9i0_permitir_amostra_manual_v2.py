"""Permite receber amostras manuais sem uma linha CSV de origem."""

from alembic import op
import sqlalchemy as sa


revision = "h5e6f7g8h9i0"
down_revision = "h4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "amostras",
        "id_linha_importacao",
        existing_type=sa.String(),
        nullable=True,
        schema="pathlab_v2",
    )


def downgrade() -> None:
    op.alter_column(
        "amostras",
        "id_linha_importacao",
        existing_type=sa.String(),
        nullable=False,
        schema="pathlab_v2",
    )
