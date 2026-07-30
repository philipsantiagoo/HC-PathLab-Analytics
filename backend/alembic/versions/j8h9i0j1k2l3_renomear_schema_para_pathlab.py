"""Renomeia o schema ``pathlab_v2`` para ``pathlab``.

O sufixo ``_v2`` marcava a coexistência com o schema ``public`` legado durante
a homologação. As tabelas legadas foram removidas em ``h6f7g8h9i0j1`` e não há
mais um "v1" do qual se diferenciar — o nome só confundia.

``ALTER SCHEMA ... RENAME`` é uma operação de catálogo: instantânea, atômica e
independente do volume de dados. As migrations anteriores continuam criando
``pathlab_v2`` (é o histórico real); esta renomeia no fim, então um banco novo
e o banco atual convergem para o mesmo estado.
"""

from alembic import op


revision = "j8h9i0j1k2l3"
down_revision = "i7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER SCHEMA pathlab_v2 RENAME TO pathlab")


def downgrade() -> None:
    op.execute("ALTER SCHEMA pathlab RENAME TO pathlab_v2")
