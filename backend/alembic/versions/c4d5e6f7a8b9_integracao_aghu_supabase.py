"""Estrutura de integração AGHU, catálogo de tipos, RBAC e contadores.

Esta migration é compatível com SQLite para desenvolvimento e PostgreSQL/
Supabase para produção. Não importa CSV nem cria exames operacionais.
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tipos_exame",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("codigo", sa.String(8), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("prefixo", sa.String(8), nullable=False, unique=True),
        sa.Column("sla_dias", sa.Integer(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(sa.table("tipos_exame", sa.column("id"), sa.column("codigo"), sa.column("nome"), sa.column("prefixo"), sa.column("sla_dias"), sa.column("ativo")), [
        {"id": "tipo-hp", "codigo": "HP", "nome": "Histopatológico", "prefixo": "HP", "sla_dias": 20, "ativo": True},
        {"id": "tipo-cg", "codigo": "CG", "nome": "Citologia Geral", "prefixo": "CG", "sla_dias": 20, "ativo": True},
        {"id": "tipo-ccv", "codigo": "CCV", "nome": "Citologia Cérvico-vaginal", "prefixo": "CV", "sla_dias": 20, "ativo": True},
        {"id": "tipo-ih", "codigo": "IH", "nome": "Imuno-histoquímica", "prefixo": "IH", "sla_dias": 20, "ativo": True},
        {"id": "tipo-co", "codigo": "CO", "nome": "Congelação", "prefixo": "CO", "sla_dias": 1, "ativo": True},
    ])

    op.create_table(
        "perfis_usuarios",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject_externo", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("nome_exibicao", sa.String(255)), sa.Column("email", sa.String(255)),
        sa.Column("departamento", sa.String(255)),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ultimo_login_em", sa.DateTime()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "papeis",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("codigo", sa.String(50), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.bulk_insert(sa.table("papeis", sa.column("id"), sa.column("codigo"), sa.column("nome"), sa.column("ativo")), [
        {"id": "role-admin", "codigo": "ADMIN", "nome": "Administrador", "ativo": True},
        {"id": "role-recepcao", "codigo": "RECEPCIONISTA", "nome": "Recepcionista", "ativo": True},
        {"id": "role-macro", "codigo": "MACROSCOPISTA", "nome": "Macroscopista", "ativo": True},
        {"id": "role-tecnico", "codigo": "TECNICO", "nome": "Técnico de Laboratório", "ativo": True},
        {"id": "role-residente", "codigo": "RESIDENTE", "nome": "Residente", "ativo": True},
        {"id": "role-patologista", "codigo": "PATOLOGISTA", "nome": "Médico Patologista", "ativo": True},
    ])
    op.create_table(
        "papeis_usuarios",
        sa.Column("id_usuario", sa.String(), sa.ForeignKey("perfis_usuarios.id"), primary_key=True),
        sa.Column("id_papel", sa.String(), sa.ForeignKey("papeis.id"), primary_key=True),
        sa.Column("unidade", sa.String(255), primary_key=True, nullable=False, server_default=""),
        sa.Column("valido_desde", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("valido_ate", sa.DateTime()),
    )

    op.create_table(
        "lotes_integracao",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("origem", sa.String(50), nullable=False),
        sa.Column("arquivo_origem", sa.String(500)), sa.Column("hash_origem", sa.String(64)),
        sa.Column("status", sa.String(30), nullable=False, server_default="Em andamento"),
        sa.Column("linhas_lidas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linhas_inseridas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linhas_atualizadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linhas_rejeitadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erro", sa.Text()), sa.Column("iniciado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime()),
    )
    op.create_index("ix_lotes_integracao_hash_origem", "lotes_integracao", ["hash_origem"])
    op.create_table(
        "catalogo_exames_aghu",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("codigo_laboratorio", sa.String(30), nullable=False),
        sa.Column("sigla_aghu", sa.String(30), nullable=False), sa.Column("nome_aghu", sa.String(255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("primeira_vez_visto_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ultima_vez_visto_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("codigo_laboratorio", "sigla_aghu", name="uq_catalogo_aghu_lab_sigla"),
    )
    op.create_table(
        "mapeamentos_tipo_exame_aghu",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_catalogo_exame_aghu", sa.String(), sa.ForeignKey("catalogo_exames_aghu.id"), nullable=False),
        sa.Column("id_tipo_exame", sa.String(), sa.ForeignKey("tipos_exame.id"), nullable=False),
        sa.Column("valido_desde", sa.Date()), sa.Column("valido_ate", sa.Date()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("observacoes", sa.Text()), sa.Column("aprovado_por", sa.String()),
        sa.Column("aprovado_em", sa.DateTime()), sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mapeamento_catalogo", "mapeamentos_tipo_exame_aghu", ["id_catalogo_exame_aghu"])

    op.create_table(
        "solicitacoes_aghu",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("codigo_solicitacao_aghu", sa.String(40), nullable=False, unique=True),
        sa.Column("codigo_paciente_aghu", sa.String(40)), sa.Column("prontuario", sa.String(40)),
        sa.Column("nome_paciente_origem", sa.String(255)), sa.Column("data_nascimento_origem", sa.Date()),
        sa.Column("data_solicitacao", sa.Date()), sa.Column("convenio", sa.String(100)),
        sa.Column("origem_atendimento", sa.String(100)), sa.Column("unidade", sa.String(255)),
        sa.Column("informacoes_clinicas", sa.Text()), sa.Column("status_aghu", sa.String(80)),
        sa.Column("cancelado_em", sa.DateTime()), sa.Column("atualizado_no_aghu_em", sa.DateTime()),
        sa.Column("id_ultimo_lote_integracao", sa.String(), sa.ForeignKey("lotes_integracao.id")),
        sa.Column("payload_origem", sa.JSON()), sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_solicitacoes_aghu_prontuario", "solicitacoes_aghu", ["prontuario"])
    op.create_table(
        "itens_solicitacao_aghu",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_solicitacao_aghu", sa.String(), sa.ForeignKey("solicitacoes_aghu.id"), nullable=False),
        sa.Column("sequencial_item_aghu", sa.String(40), nullable=False),
        sa.Column("id_catalogo_exame_aghu", sa.String(), sa.ForeignKey("catalogo_exames_aghu.id"), nullable=False),
        sa.Column("descricao_material", sa.Text()), sa.Column("status_aghu", sa.String(80)), sa.Column("cancelado_em", sa.DateTime()),
        sa.Column("payload_origem", sa.JSON()), sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_solicitacao_aghu", "sequencial_item_aghu", name="uq_item_aghu_solicitacao_sequencial"),
    )
    op.create_table(
        "amostras_aghu",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("id_solicitacao_aghu", sa.String(), sa.ForeignKey("solicitacoes_aghu.id"), nullable=False),
        sa.Column("numero_amostra_aghu", sa.String(40), nullable=False), sa.Column("codigo_barras_externo", sa.String(100), unique=True),
        sa.Column("recebida_em", sa.DateTime()), sa.Column("payload_origem", sa.JSON()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_solicitacao_aghu", "numero_amostra_aghu", name="uq_amostra_aghu_solicitacao_numero"),
    )
    op.create_table(
        "itens_amostras_aghu",
        sa.Column("id_item_solicitacao_aghu", sa.String(), sa.ForeignKey("itens_solicitacao_aghu.id"), primary_key=True),
        sa.Column("id_amostra_aghu", sa.String(), sa.ForeignKey("amostras_aghu.id"), primary_key=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "contadores_numeracao_exames",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("id_tipo_exame", sa.String(), sa.ForeignKey("tipos_exame.id"), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False), sa.Column("semestre", sa.Integer(), nullable=False),
        sa.Column("ultimo_sequencial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_tipo_exame", "ano", "semestre", name="uq_contador_tipo_ano_semestre"),
    )

    with op.batch_alter_table("pacientes_local") as batch:
        batch.add_column(sa.Column("codigo_paciente_aghu", sa.String(), nullable=True))
        batch.add_column(sa.Column("prontuario", sa.String(), nullable=True))
        batch.create_unique_constraint("uq_paciente_codigo_aghu", ["codigo_paciente_aghu"])
        batch.create_index("ix_paciente_prontuario", ["prontuario"])
    with op.batch_alter_table("exames") as batch:
        batch.add_column(sa.Column("id_tipo_exame", sa.String(), sa.ForeignKey("tipos_exame.id"), nullable=True))
        batch.add_column(sa.Column("id_item_solicitacao_aghu", sa.String(), sa.ForeignKey("itens_solicitacao_aghu.id"), nullable=True))
        batch.add_column(sa.Column("id_exame_pai", sa.String(), sa.ForeignKey("exames.id"), nullable=True))
        batch.add_column(sa.Column("id_criado_por", sa.String(), sa.ForeignKey("perfis_usuarios.id"), nullable=True))
        batch.create_unique_constraint("uq_exame_item_aghu", ["id_item_solicitacao_aghu"])
        batch.create_unique_constraint("uq_exame_tipo_ano_semestre_sequencial", ["tipo_exame", "ano", "semestre", "sequencial"])
    with op.batch_alter_table("frascos") as batch:
        batch.add_column(sa.Column("id_amostra_aghu", sa.String(), sa.ForeignKey("amostras_aghu.id"), nullable=True))
        batch.add_column(sa.Column("ordinal", sa.Integer(), nullable=False, server_default="1"))
        batch.create_unique_constraint("uq_frasco_amostra_aghu", ["id_amostra_aghu"])
    with op.batch_alter_table("historico_movimentacao") as batch:
        batch.add_column(sa.Column("id_usuario_responsavel", sa.String(), sa.ForeignKey("perfis_usuarios.id"), nullable=True))

    op.execute("UPDATE exames SET tipo_exame = 'IH' WHERE tipo_exame = 'IHQ'")
    op.execute("UPDATE exames SET tipo_exame = 'HP' WHERE tipo_exame IN ('HPDerm', 'RevInt')")
    op.execute("UPDATE exames SET tipo_exame = 'CO' WHERE tipo_exame = 'Congela'")
    op.execute("UPDATE exames SET id_tipo_exame = (SELECT id FROM tipos_exame WHERE codigo = exames.tipo_exame)")


def downgrade() -> None:
    with op.batch_alter_table("historico_movimentacao") as batch:
        batch.drop_column("id_usuario_responsavel")
    with op.batch_alter_table("frascos") as batch:
        batch.drop_constraint("uq_frasco_amostra_aghu", type_="unique")
        batch.drop_column("ordinal")
        batch.drop_column("id_amostra_aghu")
    with op.batch_alter_table("exames") as batch:
        batch.drop_constraint("uq_exame_tipo_ano_semestre_sequencial", type_="unique")
        batch.drop_constraint("uq_exame_item_aghu", type_="unique")
        batch.drop_column("id_criado_por")
        batch.drop_column("id_exame_pai")
        batch.drop_column("id_item_solicitacao_aghu")
        batch.drop_column("id_tipo_exame")
    with op.batch_alter_table("pacientes_local") as batch:
        batch.drop_index("ix_paciente_prontuario")
        batch.drop_constraint("uq_paciente_codigo_aghu", type_="unique")
        batch.drop_column("prontuario")
        batch.drop_column("codigo_paciente_aghu")

    for tabela in ("contadores_numeracao_exames", "itens_amostras_aghu", "amostras_aghu", "itens_solicitacao_aghu", "solicitacoes_aghu", "mapeamentos_tipo_exame_aghu", "catalogo_exames_aghu", "lotes_integracao", "papeis_usuarios", "papeis", "perfis_usuarios", "tipos_exame"):
        op.drop_table(tabela)
