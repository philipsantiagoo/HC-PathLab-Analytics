"""Remove as tabelas patológicas legadas já arquivadas e substituídas por v2."""

from alembic import op


revision = "h6f7g8h9i0j1"
down_revision = "h5e6f7g8h9i0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ordem inversa das FKs. O backup de dados está em legacy_public_20260725.
    for tabela in (
        "historico_movimentacao",
        "laminas",
        "blocos_parafina",
        "cassetes",
        "partes_macroscopia",
        "macroscopias",
        "frascos",
        "lotes_processamento",
        "exames",
        "pacientes_local",
    ):
        op.drop_table(tabela, schema="public", if_exists=True)


def downgrade() -> None:
    raise NotImplementedError(
        "A restauração do legado deve partir do schema legacy_public_20260725."
    )
