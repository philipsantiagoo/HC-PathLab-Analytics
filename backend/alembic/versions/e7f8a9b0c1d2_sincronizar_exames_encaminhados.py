"""Sincroniza a etapa de exames encaminhados para macroscopia.

Revision ID: e7f8a9b0c1d2
Revises: c4d5e6f7a8b9
"""

from alembic import op


revision = "e7f8a9b0c1d2"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE frascos
        SET status = 'Aguardando Macroscopia'
        WHERE status = 'Na Recepção'
          AND codigo_interno IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE exames
        SET status = 'Em Macroscopia'
        WHERE status = 'Na Recepção'
          AND EXISTS (
              SELECT 1
              FROM frascos
              WHERE frascos.id_exame = exames.id
                AND frascos.codigo_interno IS NOT NULL
                AND frascos.status IN ('Aguardando Macroscopia', 'Em Macroscopia')
          )
        """
    )


def downgrade() -> None:
    # O estado anterior não pode ser reconstruído sem sobrescrever transições
    # legítimas; esta migração corrige somente registros inconsistentes.
    pass
