# Controllers — Lógica de Negócio

Os controllers ficam entre os routers (que recebem a requisição HTTP) e o banco. Contêm as regras de negócio e são o único lugar que abre e fecha transação: o `commit` acontece aqui, nunca em camadas abaixo.

Todos operam sobre o schema `pathlab` (`src/models/patologia.py`).

---

## Arquivos

### `fluxo_controller.py` — todo o fluxo operacional

Um módulo único para Triagem → Macroscopia → Processamento → Microscopia. Os routers o importam com apelidos por área (`exame_controller`, `macroscopia_controller`, ...), mas é o mesmo módulo.

**Recepção**
- `registrar_recebimento()` — valida paciente (CPF ou CNS) e tipo de exame, cria Caso + Exame + Amostra, gera o número local (`HP-0001/26.1`) e devolve a etiqueta. O exame entra em `Aguardando Macroscopia`.
- `listar_pendencias_recepcao()`, `encaminhar_para_macroscopia()`, `obter_etiqueta_frasco()`

**Macroscopia — a unidade é o EXAME, não o frasco**

Os frascos de um exame andam juntos: são apenas como o material chegou. A clivagem é uma só, do exame inteiro.

- `listar_fila_macroscopia()` — página da fila + contadores das quatro abas (`meus`, `aguardando`, `em_andamento`, `todos`). Contagem de frascos por subquery escalar correlacionada; com `JOIN + GROUP BY` o `LIMIT` seria aplicado depois de agregar todas as amostras.
- `obter_workspace_macroscopia()` — exame + frascos + posse + clivagem.
- `assumir_exame()` — `UPDATE ... WHERE responsavel_macroscopia IS NULL` numa ida só. Sob READ COMMITTED o segundo concorrente reavalia o `WHERE` contra a versão nova e recebe 409. **Nunca** fazer `SELECT` → checar → `UPDATE`: essa é a corrida.
- `repassar_exame()` — só o dono atual ou um admin. Grava o motivo em `movimentacoes`.
- `liberar_exame()` — devolve à fila; saída para quando o dono fica indisponível.
- `registrar_macroscopia()` — exige posse, cria **uma** macroscopia por exame (UNIQUE em `id_exame` protege contra duplo submit), gera as partes e cassetes e move **todas** as amostras do exame juntas.

**Processamento e Microscopia**
- `listar_pendencias_processamento()`, `iniciar_lote()`, `concluir_lote()`, `listar_blocos_pendentes()`, `buscar_bloco()`, `gerar_laminas()`, `listar_laminas()`
- `listar_pendencias_microscopia()`, `registrar_laudo()`

**Consultas**
- `listar_dashboard_paginado()` / `listar_dashboard()` (esta última mantida por compatibilidade), `resumo_dashboard()`, `listar_exames()`, `obter_exame()`, `obter_detalhe()`, `listar_historico()`, `listar_usuarios_candidatos()`

### `paciente_controller.py`

Delega ao provedor de dados (PostgreSQL/AGHU ou CSV). Sem lógica de negócio própria.

---

## Convenções

**Paginação.** Toda listagem grande usa o envelope de `schemas/paginacao.py`. O `ORDER BY` precisa **sempre** de `, id` como desempate: os casos vieram de importação em lote e compartilham `criado_em`, então ordenar só por data não é determinístico e o `OFFSET` duplica e pula linhas entre páginas.

**Etapa da macroscopia.** `exames.etapa_macroscopia` (`AGUARDANDO` / `EM_ANDAMENTO` / `CONCLUIDA`) é a fonte da verdade da fila — não derive de `exames.status`, que é escrito por vários caminhos do fluxo.

**Assinatura.** `session` primeiro, depois os dados da operação, depois `usuario`/`ip` para auditoria.

```python
@router.post("")
async def registrar(dados: ExameCreate, session: AsyncSession = Depends(...)):
    return await triagem_controller.registrar_recebimento(session, dados, usuario, ip)
```
