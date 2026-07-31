"""Fila e posse genéricas por etapa + persistência do congelamento.

A posse existia só na macroscopia, em cinco colunas de ``exames``. Processamento
e Microscopia não tinham fila por exame nem dono, e o Congelamento não tinha
persistência nenhuma — a tela inteira era mock com um contador no navegador
gerando o código do HP correlato.

Esta migration:

1. Cria ``exame_etapas``: uma linha por (exame, etapa, ciclo), com a fila
   (``status``), a posse (``responsavel_username``) e a subetapa. O índice
   parcial ``uq_exame_etapas_ativa`` é o que garante no banco — não só no
   código — que existe no máximo uma etapa ativa por exame.
2. Migra a posse da macroscopia para lá e abre a etapa correspondente à posição
   atual de cada exame no fluxo, para nenhum exame ficar fora de toda fila.
3. Remove as cinco colunas de posse de ``exames``, que passariam a ser uma
   segunda fonte da verdade.
4. Cria ``laudos_microscopia``, ``congelamentos`` e ``congelamento_ciclos``.

``exames.status`` continua existindo e representando a posição geral do exame;
quem alimenta as filas passa a ser ``exame_etapas.status``.
"""

from alembic import op
import sqlalchemy as sa


revision = "l0j1k2l3m4n5"
down_revision = "k9i0j1k2l3m4"
branch_labels = None
depends_on = None

SCHEMA = "pathlab"


def upgrade() -> None:
    # --- 1. Tabela genérica de etapa ------------------------------------
    op.create_table(
        "exame_etapas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_exame", sa.String(), nullable=False),
        sa.Column("etapa", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="AGUARDANDO"),
        sa.Column("subetapa", sa.String(length=30), nullable=True),
        sa.Column("responsavel_username", sa.String(length=255), nullable=True),
        sa.Column("responsavel_nome", sa.String(length=255), nullable=True),
        sa.Column("assumido_em", sa.DateTime(), nullable=True),
        sa.Column("concluido_em", sa.DateTime(), nullable=True),
        sa.Column("ciclo", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["id_exame"], [f"{SCHEMA}.exames.id"], name="fk_etapa_exame"),
        sa.UniqueConstraint("id_exame", "etapa", "ciclo", name="uq_etapa_exame_ciclo"),
        schema=SCHEMA,
    )
    op.create_index("ix_exame_etapas_id_exame", "exame_etapas", ["id_exame"], schema=SCHEMA)
    # O ", id" é o desempate obrigatório: os exames vieram de importação em lote
    # e compartilham criado_em, então ORDER BY criado_em sozinho não é
    # determinístico e o OFFSET duplicaria e pularia linhas entre páginas.
    op.create_index("ix_exame_etapas_fila", "exame_etapas", ["etapa", "status", "criado_em", "id"], schema=SCHEMA)
    op.create_index(
        "ix_exame_etapas_responsavel", "exame_etapas",
        ["responsavel_username", "etapa", "status"], schema=SCHEMA,
        postgresql_where=sa.text("responsavel_username IS NOT NULL"),
    )
    op.create_index(
        "uq_exame_etapas_ativa", "exame_etapas", ["id_exame", "etapa"], unique=True,
        schema=SCHEMA, postgresql_where=sa.text("status <> 'CONCLUIDA'"),
    )

    # --- 2. Migra a posse da macroscopia --------------------------------
    # ``etapa_macroscopia`` já usa exatamente o mesmo vocabulário de status, e
    # ``criado_em`` recebe a data de entrada do exame para a fila não nascer com
    # todos os itens com a mesma idade.
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.exame_etapas (
            id, id_exame, etapa, status, responsavel_username, responsavel_nome,
            assumido_em, concluido_em, ciclo, criado_em, atualizado_em
        )
        SELECT gen_random_uuid()::text,
               e.id,
               'MACROSCOPIA',
               e.etapa_macroscopia,
               e.responsavel_macroscopia,
               e.responsavel_macroscopia_nome,
               e.assumido_em,
               e.macroscopia_concluida_em,
               1,
               COALESCE(e.data_recebimento, e.criado_em),
               now()
          FROM {SCHEMA}.exames e
         WHERE e.id_tipo_exame <> (SELECT id FROM {SCHEMA}.tipos_exame WHERE codigo = 'CONG')
        """
    )

    # Exames de congelação nunca passam pela macroscopia: entram direto na fila
    # do próprio setor. Sem isto eles ficariam invisíveis em todas as telas.
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.exame_etapas (
            id, id_exame, etapa, status, ciclo, criado_em, atualizado_em
        )
        SELECT gen_random_uuid()::text, e.id, 'CONGELAMENTO', 'AGUARDANDO', 1,
               COALESCE(e.data_recebimento, e.criado_em), now()
          FROM {SCHEMA}.exames e
         WHERE e.id_tipo_exame = (SELECT id FROM {SCHEMA}.tipos_exame WHERE codigo = 'CONG')
        """
    )

    # O status global precisa acompanhar: as congelações importadas ficaram em
    # "Aguardando Macroscopia" porque era o único destino que a triagem
    # conhecia, e elas nunca passam por lá.
    op.execute(
        f"""
        UPDATE {SCHEMA}.exames e
           SET status = 'Em Congelamento'
          FROM {SCHEMA}.tipos_exame t
         WHERE e.id_tipo_exame = t.id
           AND t.codigo = 'CONG'
           AND e.status IN ('Na Recepção', 'Aguardando Macroscopia', 'Em Macroscopia')
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA}.amostras a
           SET status = 'Em Congelamento'
          FROM {SCHEMA}.exames e
         WHERE a.id_exame = e.id
           AND e.status = 'Em Congelamento'
           AND a.status IN ('Na Recepção', 'Aguardando Macroscopia', 'Em Macroscopia')
        """
    )

    # Exames que já passaram da macroscopia precisam da etapa seguinte aberta,
    # senão somem das filas. O status global é a única pista de onde eles estão.
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.exame_etapas (
            id, id_exame, etapa, status, subetapa, ciclo, criado_em, atualizado_em
        )
        SELECT gen_random_uuid()::text, e.id, 'PROCESSAMENTO', 'AGUARDANDO', NULL, 1,
               COALESCE(e.data_recebimento, e.criado_em), now()
          FROM {SCHEMA}.exames e
         WHERE e.status = 'Em Processamento'
        """
    )
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.exame_etapas (
            id, id_exame, etapa, status, subetapa, ciclo, criado_em, atualizado_em
        )
        SELECT gen_random_uuid()::text, e.id, 'MICROSCOPIA', 'AGUARDANDO', 'LAUDO_PREVIO', 1,
               COALESCE(e.data_recebimento, e.criado_em), now()
          FROM {SCHEMA}.exames e
         WHERE e.status IN ('Em Microscopia', 'Revisão Pendente')
        """
    )

    # Um exame que já chegou ao processamento tem, por definição, a macroscopia
    # concluída — mesmo que a coluna antiga não registrasse isso.
    op.execute(
        f"""
        UPDATE {SCHEMA}.exame_etapas et
           SET status = 'CONCLUIDA',
               concluido_em = COALESCE(et.concluido_em, now())
          FROM {SCHEMA}.exames e
         WHERE et.id_exame = e.id
           AND et.etapa = 'MACROSCOPIA'
           AND et.status <> 'CONCLUIDA'
           AND e.status IN ('Em Processamento', 'Em Microscopia', 'Revisão Pendente', 'Liberado')
        """
    )

    # --- 3. exames perde as colunas de posse ----------------------------
    op.drop_index("ix_exames_fila_macro", table_name="exames", schema=SCHEMA)
    op.drop_index("ix_exames_responsavel_macro", table_name="exames", schema=SCHEMA)
    for coluna in (
        "macroscopia_concluida_em", "assumido_em",
        "responsavel_macroscopia_nome", "responsavel_macroscopia", "etapa_macroscopia",
    ):
        op.drop_column("exames", coluna, schema=SCHEMA)

    # --- 4. Laudo da microscopia ----------------------------------------
    # O texto do laudo prévio só existia em ``movimentacoes.observacoes``, então
    # o patologista abria a tela sem ver o que o residente tinha escrito.
    op.create_table(
        "laudos_microscopia",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_exame", sa.String(), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("laudo_previo", sa.Text(), nullable=True),
        sa.Column("residente", sa.String(length=255), nullable=True),
        sa.Column("laudo_previo_em", sa.DateTime(), nullable=True),
        sa.Column("conclusao", sa.Text(), nullable=True),
        sa.Column("patologista", sa.String(length=255), nullable=True),
        sa.Column("liberado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["id_exame"], [f"{SCHEMA}.exames.id"], name="fk_laudo_micro_exame"),
        sa.UniqueConstraint("id_exame", "ciclo", name="uq_laudo_micro_exame_ciclo"),
        schema=SCHEMA,
    )
    op.create_index("ix_laudos_microscopia_id_exame", "laudos_microscopia", ["id_exame"], schema=SCHEMA)

    # --- 5. Congelamento -------------------------------------------------
    op.create_table(
        "congelamentos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_exame", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="EM_ANALISE"),
        sa.Column("resultado_final", sa.Text(), nullable=True),
        sa.Column("id_exame_hp", sa.String(), nullable=True),
        sa.Column("numero_hp_correlato", sa.String(length=40), nullable=True),
        sa.Column("liberado_em", sa.DateTime(), nullable=True),
        sa.Column("liberado_por", sa.String(length=255), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["id_exame"], [f"{SCHEMA}.exames.id"], name="fk_congelamento_exame"),
        sa.ForeignKeyConstraint(["id_exame_hp"], [f"{SCHEMA}.exames.id"], name="fk_congelamento_exame_hp"),
        sa.UniqueConstraint("id_exame", name="uq_congelamento_exame"),
        schema=SCHEMA,
    )
    op.create_table(
        "congelamento_ciclos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_congelamento", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("residente", sa.String(length=255), nullable=True),
        sa.Column("patologista", sa.String(length=255), nullable=True),
        sa.Column("quantidade_laminas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("diagnostico", sa.Text(), nullable=False),
        sa.Column("conduta", sa.String(length=20), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("registrado_por", sa.String(length=255), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["id_congelamento"], [f"{SCHEMA}.congelamentos.id"], name="fk_ciclo_congelamento"
        ),
        sa.UniqueConstraint("id_congelamento", "ordinal", name="uq_ciclo_congelamento_ordinal"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_congelamento_ciclos_id_congelamento", "congelamento_ciclos", ["id_congelamento"], schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_congelamento_ciclos_id_congelamento", table_name="congelamento_ciclos", schema=SCHEMA)
    op.drop_table("congelamento_ciclos", schema=SCHEMA)
    op.drop_table("congelamentos", schema=SCHEMA)
    op.drop_index("ix_laudos_microscopia_id_exame", table_name="laudos_microscopia", schema=SCHEMA)
    op.drop_table("laudos_microscopia", schema=SCHEMA)

    # Devolve as colunas de posse e restaura o que dá: o estado da macroscopia
    # veio de exame_etapas, então a volta é fiel. As etapas de Processamento,
    # Microscopia e Congelamento não têm para onde voltar — elas não existiam.
    op.add_column(
        "exames",
        sa.Column("etapa_macroscopia", sa.String(length=20), nullable=False, server_default="AGUARDANDO"),
        schema=SCHEMA,
    )
    op.add_column("exames", sa.Column("responsavel_macroscopia", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("responsavel_macroscopia_nome", sa.String(length=255), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("assumido_em", sa.DateTime(), nullable=True), schema=SCHEMA)
    op.add_column("exames", sa.Column("macroscopia_concluida_em", sa.DateTime(), nullable=True), schema=SCHEMA)
    op.execute(
        f"""
        UPDATE {SCHEMA}.exames e
           SET etapa_macroscopia = et.status,
               responsavel_macroscopia = et.responsavel_username,
               responsavel_macroscopia_nome = et.responsavel_nome,
               assumido_em = et.assumido_em,
               macroscopia_concluida_em = et.concluido_em
          FROM {SCHEMA}.exame_etapas et
         WHERE et.id_exame = e.id AND et.etapa = 'MACROSCOPIA' AND et.ciclo = 1
        """
    )
    op.create_index(
        "ix_exames_fila_macro", "exames", ["etapa_macroscopia", "criado_em", "id"], schema=SCHEMA,
    )
    op.create_index(
        "ix_exames_responsavel_macro", "exames",
        ["responsavel_macroscopia", "etapa_macroscopia", "criado_em"], schema=SCHEMA,
        postgresql_where=sa.text("responsavel_macroscopia IS NOT NULL"),
    )

    op.drop_index("uq_exame_etapas_ativa", table_name="exame_etapas", schema=SCHEMA)
    op.drop_index("ix_exame_etapas_responsavel", table_name="exame_etapas", schema=SCHEMA)
    op.drop_index("ix_exame_etapas_fila", table_name="exame_etapas", schema=SCHEMA)
    op.drop_index("ix_exame_etapas_id_exame", table_name="exame_etapas", schema=SCHEMA)
    op.drop_table("exame_etapas", schema=SCHEMA)
