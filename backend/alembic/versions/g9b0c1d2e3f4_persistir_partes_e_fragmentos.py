"""Persiste partes da peça e vincula seus fragmentos.

Revision ID: g9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from alembic import op
import sqlalchemy as sa


revision = "g9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O startup usa Base.metadata.create_all(). Em bancos já existentes isso
    # pode criar a tabela nova, mas não adiciona colunas a tabelas antigas.
    # A migration precisa, portanto, aceitar esse estado intermediário.
    inspector = sa.inspect(op.get_bind())
    if "partes_macroscopia" not in inspector.get_table_names():
        op.create_table(
            "partes_macroscopia",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("id_macroscopia", sa.String(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("letra_identificacao", sa.String(), nullable=False),
            sa.Column("descricao_estrutura", sa.Text(), nullable=False),
            sa.Column("quantidade_fragmentos", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["id_macroscopia"], ["macroscopias.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "id_macroscopia", "ordinal", name="uq_parte_macroscopia_ordinal"
            ),
            sa.UniqueConstraint(
                "id_macroscopia",
                "letra_identificacao",
                name="uq_parte_macroscopia_letra",
            ),
        )
        op.create_index(
            op.f("ix_partes_macroscopia_id_macroscopia"),
            "partes_macroscopia",
            ["id_macroscopia"],
            unique=False,
        )

    colunas_cassetes = {
        coluna["name"] for coluna in inspector.get_columns("cassetes")
    }
    if "id_parte_macroscopia" not in colunas_cassetes:
        with op.batch_alter_table("cassetes") as batch:
            batch.add_column(
                sa.Column("id_parte_macroscopia", sa.String(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_cassete_parte_macroscopia",
                "partes_macroscopia",
                ["id_parte_macroscopia"],
                ["id"],
            )
            batch.create_index(
                "ix_cassetes_id_parte_macroscopia",
                ["id_parte_macroscopia"],
                unique=False,
            )


def downgrade() -> None:
    with op.batch_alter_table("cassetes") as batch:
        batch.drop_index("ix_cassetes_id_parte_macroscopia")
        batch.drop_constraint("fk_cassete_parte_macroscopia", type_="foreignkey")
        batch.drop_column("id_parte_macroscopia")
    op.drop_index(
        op.f("ix_partes_macroscopia_id_macroscopia"),
        table_name="partes_macroscopia",
    )
    op.drop_table("partes_macroscopia")
