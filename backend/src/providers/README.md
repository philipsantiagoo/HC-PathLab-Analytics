# Providers — Acesso a Dados

Camada responsável por toda comunicação com bancos de dados. Os controllers nunca acessam o banco diretamente — eles sempre passam por um provider ou repository.

Há dois tipos de acesso a dados neste projeto, com padrões distintos:

---

## Dados externos — AGHU (PostgreSQL, somente leitura)

O AGHU é o sistema do hospital. O acesso é **somente leitura** e feito por SQL direto, sem ORM, pois não temos controle sobre o schema desse banco.

### Interface

**`interfaces/paciente_provider_interface.py`** define o contrato:

```python
async def listar_pacientes() -> List[Dict]
async def obter_paciente_por_codigo(codigo: int) -> Dict
```

### Implementações

**`paciente_postgres_provider.py`** — busca pacientes no banco AGHU via SQL. As queries ficam em arquivos `.sql` na pasta `sql/paciente/` e são carregadas em tempo de execução pelo `sql_helper`.

**`paciente_csv_provider.py`** — alternativa para desenvolvimento sem acesso à rede do HC. Lê um arquivo CSV com os dados. Ativado quando `PACIENTE_PROVIDER_TYPE=CSV` no `.env`.

A troca entre os dois provedores é feita sem alterar nenhum código — apenas a variável de ambiente `PACIENTE_PROVIDER_TYPE`.

---

## Dados próprios — App DB (PostgreSQL, schema `pathlab`)

As entidades do sistema (exames, amostras, cassetes, blocos, lâminas) são acessadas
diretamente pelo `fluxo_controller`, via SQLAlchemy ORM e a sessão do banco da aplicação.

A camada de repositories por entidade foi removida: existia para o schema `public`
legado, cujas tabelas foram descartadas na migration `h6f7g8h9i0j1`. Manter uma
indireção por entidade não pagava o custo num fluxo em que quase toda consulta
cruza exame + amostra + paciente + tipo na mesma query.

Os providers de paciente (`paciente_csv_provider`, `paciente_postgres_provider`)
permanecem, porque ali a indireção tem motivo real: a fonte de dados troca por
variável de ambiente.

---

## Como o controller recebe a sessão

A sessão do banco é injetada via FastAPI `Depends` no router e repassada ao controller. Isso garante que toda a operação de negócio aconteça dentro da mesma transação.

```python
# Router → Controller (mesma sessão)
session: AsyncSession = Depends(get_app_db_session)
```

O commit é sempre feito no controller, ao fim de todas as operações.

---

## Queries SQL externas

As queries para o AGHU ficam em `sql/paciente/`:

| Arquivo | Finalidade |
|---|---|
| `listar_pacientes.sql` | Lista pacientes da tabela `agh.aip_pacientes` |
| `obter_paciente.sql` | Busca um paciente por código |
