# Services — Regras de Domínio

Lógica de domínio que não pertence a um controller específico e é compartilhada por diferentes etapas do fluxo.

---

## `patologia.py` — Regras de leitura e agrupamento do extrato

Módulo puro (sem banco), por isso é o único com teste automatizado (`tests/test_patologia.py`).

Uma linha do extrato **não é** um exame operacional: ela é uma amostra ligada a um conjunto de amostras do mesmo paciente. Este módulo mantém essa regra fora dos controllers e do formato físico do banco.

- `ler_csv_patologia()` — lê e normaliza o CSV homologado
- `agrupar_casos()` — agrupa linhas em casos por proximidade; marca `exige_revisao` quando o agrupamento é ambíguo
- `tipo_por_codigo_lab()` — traduz o código do laboratório (139, 203, 205, 207, 209) para HP/IHQ/CCV/CG/CO

## `patologia_importer.py` — Carga no schema `pathlab`

Importador **idempotente**: rodar duas vezes o mesmo CSV não duplica nada. Consome `patologia.py` e grava Casos, Exames e Amostras, registrando o lote em `importacoes`/`linhas_importacao` para rastreabilidade.

Usado por `scripts/importar_patologia.py`, não pela API.

## `catalogos.py` — Dados de referência

`garantir_catalogos_iniciais()` roda no startup (`main.py`) e assegura que os tipos de exame existam antes de qualquer recebimento.

## `usuarios.py` — Identidade local

`sincronizar_usuario_autenticado()` faz upsert em `perfis_usuarios` a cada login. Não guarda senha — a autenticação continua no AD.

> A tabela só ganha linha quando a pessoa faz login pela primeira vez. Por isso o endpoint `/api/usuarios/candidatos` (destinatários de repasse) completa a lista com os usernames já vistos no fluxo; caso contrário nasceria vazia.

---

## Transições de status

Não existe mais um módulo de máquina de estados. As transições vivem no `controllers/fluxo_controller.py`, junto da operação que as provoca, e cada uma grava sua linha em `pathlab.movimentacoes` pelo helper `_mov()`.

A guarda que hoje importa de verdade é a de **posse do exame**:

- `assumir_exame()` usa `UPDATE ... WHERE responsavel_macroscopia IS NULL` — atômico sob READ COMMITTED, sem `SELECT` antes.
- `registrar_macroscopia()` exige que o exame esteja `EM_ANDAMENTO` e sob o usuário que chamou.

O commit é sempre do controller, ao fim de todas as operações.
