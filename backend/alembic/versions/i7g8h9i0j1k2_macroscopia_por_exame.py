"""Macroscopia por exame: posse do exame, clivagem única e índices de fila.

A operação é por exame — os frascos de um paciente andam juntos e a clivagem é
analisada por exame. Três mudanças:

1. ``exames`` ganha a posse na macroscopia (quem assumiu, quando, em que etapa).
2. ``macroscopias`` e ``cassetes`` deixam de apontar para a amostra e passam a
   apontar para o exame.
3. Índices para a fila paginada.

As tabelas ``macroscopias``, ``partes_macroscopia`` e ``cassetes`` estavam
vazias quando esta migration foi escrita, então a troca de FK não precisa de
backfill. As colunas novas em ``exames`` usam ``server_default`` e são
metadata-only no PostgreSQL 11+, sem rewrite das 19k linhas.
"""

from alembic import op
import sqlalchemy as sa


revision = "i7g8h9i0j1k2"
down_revision = "h6f7g8h9i0j1"
branch_labels = None
depends_on = None

SCHEMA = "pathlab_v2"


def upgrade() -> None:
    # --- 1. Posse do exame na macroscopia -------------------------------
    op.add_column(
        "exames",
        sa.Column(
            "etapa_macroscopia",
            sa.String(length=20),
            nullable=False,
            server_default="AGUARDANDO",
        ),
        schema=SCHEMA,
    )
    op.add_column("exames", sa.Column("responsavel_macroscopia", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("responsavel_macroscopia_nome", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("assumido_em", sa.DateTime(), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("macroscopia_concluida_em", sa.DateTime(), nullable=True), schema=SCHEMA)

    # --- 2. macroscopias: por exame, não por amostra --------------------
    op.add_column("macroscopias", sa.Column("id_exame", sa.String(), nullable=False), schema=SCHEMA)
    op.create_foreign_key(
        "fk_macroscopia_exame", "macroscopias", "exames",
        ["id_exame"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA,
    )
    op.create_unique_constraint("uq_macroscopia_exame", "macroscopias", ["id_exame"], schema=SCHEMA)
    # drop_column derruba junto a FK e a UNIQUE que dependiam da coluna.
    op.drop_column("macroscopias", "id_amostra", schema=SCHEMA)

    # --- 3. Corrige o status legado -------------------------------------
    # ``registrar_recebimento`` avançava o exame para "Em Macroscopia" já na
    # criação, então toda a base ficou nesse status sem ninguém ter assumido
    # nada. A guarda pelo NOT IN é no-op hoje (macroscopias vazia) mas mantém a
    # migration correta caso rode depois de já existirem clivagens. Precisa vir
    # depois do passo 2, que é quem cria macroscopias.id_exame.
    op.execute(
        f"""
        UPDATE {SCHEMA}.exames
           SET status = 'Aguardando Macroscopia'
         WHERE status = 'Em Macroscopia'
           AND id NOT IN (SELECT id_exame FROM {SCHEMA}.macroscopias)
        """
    )

    # --- 4. cassetes: por exame, não por amostra ------------------------
    op.add_column("cassetes", sa.Column("id_exame", sa.String(), nullable=False), schema=SCHEMA)
    op.create_foreign_key(
        "fk_cassete_exame", "cassetes", "exames",
        ["id_exame"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA,
    )
    op.drop_constraint("uq_v2_cassete_amostra_identificador", "cassetes", type_="unique", schema=SCHEMA)
    op.drop_column("cassetes", "id_amostra", schema=SCHEMA)
    op.create_unique_constraint(
        "uq_v2_cassete_exame_identificador", "cassetes", ["id_exame", "identificador"], schema=SCHEMA,
    )
    op.create_index("ix_cassetes_id_exame", "cassetes", ["id_exame"], schema=SCHEMA)

    # --- 5. Índices da fila ---------------------------------------------
    # O "id" no fim é o desempate: os casos vieram de importação em lote e
    # compartilham criado_em, então ORDER BY criado_em sozinho não é
    # determinístico e o OFFSET duplicaria/pularia linhas entre páginas.
    op.create_index(
        "ix_exames_fila_macro", "exames",
        ["etapa_macroscopia", "criado_em", "id"], schema=SCHEMA,
    )
    op.create_index(
        "ix_exames_responsavel_macro", "exames",
        ["responsavel_macroscopia", "etapa_macroscopia", "criado_em"],
        schema=SCHEMA,
        postgresql_where=sa.text("responsavel_macroscopia IS NOT NULL"),
    )
    op.create_index("ix_exames_criado_em", "exames", ["criado_em", "id"], schema=SCHEMA)


def downgrade() -> None:
    # O passo 2 do upgrade (reclassificação do status legado) não é revertido:
    # não há como distinguir os exames que já estavam corretos dos que foram
    # reclassificados.
    op.drop_index("ix_exames_criado_em", table_name="exames", schema=SCHEMA)
    op.drop_index("ix_exames_responsavel_macro", table_name="exames", schema=SCHEMA)
    op.drop_index("ix_exames_fila_macro", table_name="exames", schema=SCHEMA)

    op.drop_index("ix_cassetes_id_exame", table_name="cassetes", schema=SCHEMA)
    op.drop_constraint("uq_v2_cassete_exame_identificador", "cassetes", type_="unique", schema=SCHEMA)
    op.add_column("cassetes", sa.Column("id_amostra", sa.String(), nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "fk_cassete_amostra", "cassetes", "amostras",
        ["id_amostra"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_v2_cassete_amostra_identificador", "cassetes", ["id_amostra", "identificador"], schema=SCHEMA,
    )
    op.drop_column("cassetes", "id_exame", schema=SCHEMA)

    op.add_column("macroscopias", sa.Column("id_amostra", sa.String(), nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "fk_macroscopia_amostra", "macroscopias", "amostras",
        ["id_amostra"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA,
    )
    op.create_unique_constraint("uq_macroscopia_amostra", "macroscopias", ["id_amostra"], schema=SCHEMA)
    op.drop_constraint("uq_macroscopia_exame", "macroscopias", type_="unique", schema=SCHEMA)
    op.drop_column("macroscopias", "id_exame", schema=SCHEMA)

    for coluna in (
        "macroscopia_concluida_em", "assumido_em",
        "responsavel_macroscopia_nome", "responsavel_macroscopia", "etapa_macroscopia",
    ):
        op.drop_column("exames", coluna, schema=SCHEMA)
