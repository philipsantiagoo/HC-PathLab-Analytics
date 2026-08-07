"""Aumenta as colunas de coloração de cassetes e lâminas.

As colunas nasceram com 30 caracteres pensando no código curto ("HE", "PAS"),
mas o que trafega é o rótulo completo do seletor da clivagem — por exemplo
``HE (Hematoxilina-Eosina) - Rotina`` (33) e ``Outra (especificar na
observação)`` (33). O registro da macroscopia estourava a coluna e devolvia
500. O contrato da API (``FragmentoMacroscopiaCreate.coloracao``) já limita em
100, então é esse o tamanho adotado aqui.
"""

from alembic import op
import sqlalchemy as sa


revision = "n2l3m4n5o6p7"
down_revision = "m1k2l3m4n5o6"
branch_labels = None
depends_on = None

SCHEMA = "pathlab"

COLUNAS = (("cassetes", "coloracao_padrao"), ("laminas", "coloracao"))


def upgrade() -> None:
    for tabela, coluna in COLUNAS:
        op.alter_column(
            tabela,
            coluna,
            schema=SCHEMA,
            existing_type=sa.String(length=30),
            type_=sa.String(length=100),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Trunca antes de encolher: sem isso, qualquer registro criado com o rótulo
    # completo impede o downgrade.
    for tabela, coluna in COLUNAS:
        op.execute(
            f"UPDATE {SCHEMA}.{tabela} SET {coluna} = left({coluna}, 30) "
            f"WHERE length({coluna}) > 30"
        )
        op.alter_column(
            tabela,
            coluna,
            schema=SCHEMA,
            existing_type=sa.String(length=100),
            type_=sa.String(length=30),
            existing_nullable=False,
        )
