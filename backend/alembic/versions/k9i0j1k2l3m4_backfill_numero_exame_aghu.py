"""Preenche ``exames.numero_exame_aghu`` a partir das amostras.

O número da solicitação AGHU sempre esteve no banco: o importador grava
``amostras.codigo_solicitacao`` com o código vindo do CSV, e todos os 28.565
valores existem em ``public.solicitacoes_aghu``. O que faltava era copiá-lo
para o exame — ``numero_exame_aghu`` nunca era preenchido, então a coluna
"Código AGHU" do dashboard exibia "—" em toda linha e o filtro por AGHU nunca
retornava nada.

Não criamos tabela nova: a relação exame → solicitação AGHU já é expressa por
``amostras.codigo_solicitacao``, e ``public.solicitacoes_aghu`` já guarda os
dados da solicitação. Esta coluna é uma desnormalização para exibição e busca,
mesma ideia de ``responsavel_macroscopia_nome``.

60 exames (de 19.108) agrupam duas solicitações AGHU distintas — o agrupamento
por proximidade do importador juntou solicitações consecutivas do mesmo
paciente. Para esses gravamos os dois códigos separados por vírgula: o máximo
observado são 2 códigos / 16 caracteres, e o filtro usa ILIKE com substring,
então buscar por qualquer um dos dois continua encontrando o exame.
"""

from alembic import op


revision = "k9i0j1k2l3m4"
down_revision = "j8h9i0j1k2l3"
branch_labels = None
depends_on = None

SCHEMA = "pathlab"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE {SCHEMA}.exames e
           SET numero_exame_aghu = codigos.lista
          FROM (
                SELECT id_exame,
                       string_agg(DISTINCT codigo_solicitacao, ', ' ORDER BY codigo_solicitacao) AS lista
                  FROM {SCHEMA}.amostras
                 WHERE codigo_solicitacao IS NOT NULL
              GROUP BY id_exame
               ) AS codigos
         WHERE e.id = codigos.id_exame
           AND e.numero_exame_aghu IS NULL
        """
    )


def downgrade() -> None:
    # Só limpa o que este backfill escreveu: os valores vieram das amostras,
    # então um exame cujo código não bate com as suas amostras foi preenchido
    # por outro caminho e deve ser preservado.
    op.execute(
        f"""
        UPDATE {SCHEMA}.exames e
           SET numero_exame_aghu = NULL
          FROM (
                SELECT id_exame,
                       string_agg(DISTINCT codigo_solicitacao, ', ' ORDER BY codigo_solicitacao) AS lista
                  FROM {SCHEMA}.amostras
                 WHERE codigo_solicitacao IS NOT NULL
              GROUP BY id_exame
               ) AS codigos
         WHERE e.id = codigos.id_exame
           AND e.numero_exame_aghu = codigos.lista
        """
    )
