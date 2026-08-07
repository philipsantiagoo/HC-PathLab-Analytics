"""Aumenta o tamanho do QR Code dos cassetes.

O payload do QR Code inclui tipo, UUID, número da solicitação e timestamp,
portanto não cabe no limite legado de 30 caracteres.
"""

from alembic import op
import sqlalchemy as sa


revision = "m1k2l3m4n5o6"
down_revision = "l0j1k2l3m4n5"
branch_labels = None
depends_on = None

SCHEMA = "pathlab"


def upgrade() -> None:
    op.alter_column(
        "cassetes",
        "qr_code",
        schema=SCHEMA,
        existing_type=sa.String(length=30),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "cassetes",
        "qr_code",
        schema=SCHEMA,
        existing_type=sa.String(length=255),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
