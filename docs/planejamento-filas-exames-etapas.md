# Planejamento — Filas de exames e exames assumidos por etapa

## Objetivo

Implantar em Processamento Técnico, Microscopia e Congelamento o mesmo conceito de fila e posse de exames existente em Macroscopia:

> Fila da etapa → Abrir exame → Assumir → Executar atividades → Concluir, repassar ou devolver à fila

A posse deve ser do exame inteiro, mesmo quando a etapa manipular itens filhos, como cassetes, blocos ou lâminas.

## Diagnóstico atual

| Etapa | Situação atual | Principal lacuna |
|---|---|---|
| Macroscopia | Fila paginada, “Meus exames”, posse, repasse e liberação | Servirá como referência |
| Processamento | Busca por cassete e execução parcial no backend | Não há fila por exame nem posse; o envio à Micro é parcialmente local |
| Microscopia | Busca por lâmina/exame e registro de decisões | Não há posse; precisa considerar residente e patologista |
| Congelamento | Tela baseada integralmente em mocks | Falta persistência, API, fila e posse |

### Pontos críticos

- O Processamento atualmente pode mover o exame para Microscopia ao concluir apenas um lote, sem garantir que todos os cassetes e blocos tenham sido concluídos.
- O botão “Enviar para Microscopia” atualiza principalmente o estado local do frontend.
- Congelamento usa códigos simulados `CO`, enquanto o backend trabalha com o tipo `CONG`; isso precisa ser padronizado.
- A posse atual é específica de Macroscopia no modelo de exame.

## 1. Fundação comum de filas e posse

Criar uma entidade genérica de etapa do exame, por exemplo `exame_etapas`, com:

- `id`;
- `id_exame`;
- `etapa`: `MACROSCOPIA`, `PROCESSAMENTO`, `MICROSCOPIA` ou `CONGELAMENTO`;
- `status`: `AGUARDANDO`, `EM_ANDAMENTO` ou `CONCLUIDA`;
- `subetapa`, quando necessário;
- `responsavel_username`;
- `responsavel_nome`;
- `assumido_em`;
- `concluido_em`;
- `ciclo`, para retornos da Microscopia ao Processamento;
- timestamps de criação e atualização.

### Regras

- Deve existir somente uma posse ativa por exame e etapa.
- “Assumir” deve ser uma atualização atômica.
- Se duas pessoas tentarem assumir simultaneamente, apenas uma deve obter sucesso e a outra deve receber HTTP `409`.
- Somente o dono atual ou um administrador pode repassar ou devolver o exame.
- Somente o dono atual pode executar as ações operacionais da etapa.
- Toda alteração de posse deve gerar uma movimentação para auditoria.
- Ao entrar ou retornar a uma etapa, o exame deve iniciar como `AGUARDANDO`, sem responsável.
- O status específico da etapa será a fonte da fila.
- O status global do exame continuará representando sua posição geral no fluxo.

A Macroscopia deverá ser migrada para essa estrutura, mantendo compatibilidade com os endpoints atuais durante a transição.

## 2. API comum

Manter URLs separadas por setor, mas reutilizar o mesmo serviço interno:

```text
GET  /api/{etapa}/fila
GET  /api/{etapa}/exames/{id_exame}
POST /api/{etapa}/exames/{id_exame}/assumir
POST /api/{etapa}/exames/{id_exame}/repassar
POST /api/{etapa}/exames/{id_exame}/liberar
```

### Filtros comuns

- `meus`;
- `aguardando`;
- `em_andamento`;
- `todos`;
- busca por código local, código AGHU ou paciente;
- paginação;
- contadores por aba.

### Informações específicas da fila

- **Processamento:** cassetes pendentes e processados, blocos e lâminas.
- **Microscopia:** quantidade de lâminas, subetapa e papel esperado.
- **Congelamento:** ciclos registrados e situação do resultado.

O endpoint de candidatos a repasse deverá receber a etapa e devolver apenas usuários compatíveis com o setor e o papel necessários.

## 3. Componentes compartilhados do frontend

Generalizar os componentes atuais da Macroscopia:

- `FilaEtapa`: tabela, abas, paginação, busca e atualização;
- `PosseExameCard`: assumir, informar bloqueio, repassar e devolver;
- `WorkspaceExame`: cabeçalho comum com paciente, exame e histórico;
- `RepassModal`: receber a etapa e chamar o endpoint correspondente.

Cada view deverá manter apenas o formulário operacional específico da sua etapa.

## 4. Processamento Técnico

### 4.1 Tela da fila

Exibir exames que tenham cassetes ou complementos pendentes no Processamento.

Colunas sugeridas:

- código;
- paciente;
- tipo;
- cassetes processados/total;
- blocos;
- lâminas;
- situação;
- responsável.

### 4.2 Workspace do exame

Depois de assumir o exame, o usuário poderá:

- visualizar todos os cassetes do exame;
- ler o QR Code de um cassete dentro do exame já aberto;
- iniciar e concluir lotes;
- registrar inclusão;
- gerar blocos;
- gerar lâminas;
- imprimir etiquetas;
- acompanhar o progresso geral do exame;
- repassar ou devolver o exame.

### 4.3 Regras de conclusão

O exame somente poderá seguir para Microscopia quando:

- todos os cassetes obrigatórios estiverem processados;
- todos os blocos necessários tiverem sido gerados;
- todas as lâminas necessárias estiverem prontas;
- o dono confirmar explicitamente o envio.

Pedidos de complemento deverão criar um novo ciclo do Processamento, sem misturar o progresso original com o complemento.

## 5. Microscopia

### 5.1 Tela da fila

Agrupar os exames nas seguintes situações:

- aguardando laudo prévio;
- aguardando revisão do patologista;
- em andamento;
- meus exames;
- todos.

A fila deverá indicar claramente a subetapa e o papel esperado.

### 5.2 Posse e passagem entre papéis

1. O residente assume o exame para produzir o laudo prévio.
2. Ao encaminhar para revisão, a posse do residente é encerrada.
3. O exame retorna à fila como aguardando patologista.
4. O patologista assume o exame para revisar e decidir.
5. O repasse deve permitir somente usuários compatíveis com o papel da subetapa.

### 5.3 Saídas da etapa

- **Liberar:** conclui a Microscopia e encerra o exame.
- **Solicitar complemento/IHQ:** encerra a posse atual e reabre o Processamento como aguardando.
- **Solicitar revisão:** encerra a posse atual e abre um novo ciclo ou subetapa de revisão.

O responsável oficial deverá ser obtido do usuário autenticado. A operação não deve depender de um nome escolhido manualmente em um campo `select`.

## 6. Congelamento

Congelamento precisa de uma implementação de domínio antes da implantação da fila.

### 6.1 Persistência

Criar estruturas para armazenar:

- exame de congelamento;
- ciclos de análise;
- residente;
- patologista;
- quantidade de lâminas;
- diagnóstico;
- conduta;
- observação;
- data e hora;
- resultado final;
- vínculo com o HP correlato.

### 6.2 Fluxo

1. Exames do tipo `CONG` entram na fila de Congelamento.
2. O usuário assume o exame inteiro.
3. O usuário pode registrar vários ciclos enquanto aguarda novos fragmentos.
4. “Margem comprometida” mantém o exame em andamento.
5. “Margem livre” ou “resultado liberado” conclui a etapa.
6. A geração ou associação ao HP correlato deve ocorrer no backend, dentro de uma transação.
7. O contador local do navegador não deve gerar o código definitivo.

Deverá ser adotada uma única representação interna para o tipo, preferencialmente `CONG`. O rótulo ou prefixo exibido poderá ser definido separadamente.

## 7. Segurança e permissões

- Processamento deve exigir perfil de técnico.
- Laudo prévio deve exigir perfil de residente ou regra equivalente definida pelo HC.
- Revisão e liberação devem exigir perfil de patologista.
- Congelamento deve aceitar apenas os perfis definidos para o setor.
- Administradores poderão intervir em posse e repasse conforme regra explícita.
- O backend deverá validar posse e perfil em todas as operações; esconder botões no frontend não será considerado controle de acesso.
- O modo permissivo de autenticação deverá ser desativado antes da entrada em produção.

## 8. Auditoria

Registrar em `movimentacoes`:

- entrada na etapa;
- exame assumido;
- repasse, incluindo responsável anterior, novo responsável e motivo;
- devolução à fila;
- conclusão da etapa;
- retorno para etapa anterior;
- mudança de subetapa;
- ações relevantes sobre cassetes, blocos, lâminas e ciclos de congelamento.

## 9. Testes

### 9.1 Backend

- filtros, busca, paginação e contadores das filas;
- duas tentativas simultâneas de assumir o mesmo exame;
- permissões para assumir, repassar, devolver e executar;
- bloqueio de alteração por usuário sem posse;
- conclusão do Processamento somente com todos os itens prontos;
- retorno de complemento para Processamento;
- passagem de residente para patologista;
- persistência dos ciclos de Congelamento;
- geração transacional do HP correlato;
- auditoria das movimentações.

### 9.2 Frontend

- troca de abas e paginação;
- abertura de exame pela fila e por leitura de código;
- estado livre, meu e assumido por outra pessoa;
- bloqueio dos formulários sem posse;
- atualização da fila depois de assumir, repassar, devolver ou concluir;
- apresentação das subetapas da Microscopia;
- preservação do estado persistido após recarregar a página;
- build e validação de tipos.

## 10. Critérios de aceite

- [ ] O exame aparece somente na fila correspondente à sua etapa atual.
- [ ] “Meus exames” mostra apenas posses do usuário autenticado.
- [ ] Duas tentativas simultâneas de assumir não produzem dois donos.
- [ ] Usuário sem posse consegue consultar, mas não alterar.
- [ ] O repasse exige motivo e gera auditoria.
- [ ] Devolver à fila remove a posse.
- [ ] O administrador pode intervir conforme a regra definida.
- [ ] O Processamento não envia um exame incompleto para Microscopia.
- [ ] Um complemento reabre corretamente o Processamento.
- [ ] A passagem residente → patologista encerra a posse anterior.
- [ ] Congelamento e seus ciclos sobrevivem ao recarregamento da página.
- [ ] Os contadores continuam corretos com paginação e pesquisa.
- [ ] Migrations, testes de integração e build do frontend são executados com sucesso.

## 11. Ordem recomendada de implementação

1. Criar o modelo genérico de etapa e a migration.
2. Migrar a posse atual da Macroscopia.
3. Criar o serviço e os endpoints compartilhados de fila e posse.
4. Criar os componentes compartilhados do frontend.
5. Implantar a fila e a posse no Processamento.
6. Corrigir as regras de conclusão e envio do Processamento.
7. Implantar a fila, posse e passagem de papéis na Microscopia.
8. Criar a persistência e as APIs de Congelamento.
9. Implantar a fila e a posse de Congelamento.
10. Executar testes de concorrência, permissões e regressão.
11. Homologar cada etapa com os respectivos usuários do laboratório.

## 12. Divisão sugerida em entregas

### Entrega 1 — Infraestrutura comum

- modelo e migration;
- serviço de posse;
- endpoints comuns;
- auditoria;
- componentes compartilhados.

### Entrega 2 — Processamento

- fila por exame;
- posse;
- workspace;
- correção da conclusão;
- envio persistido para Microscopia.

### Entrega 3 — Microscopia

- fila por exame;
- posse;
- subetapas;
- passagem residente/patologista;
- retorno de complemento.

### Entrega 4 — Congelamento

- persistência;
- APIs;
- fila;
- posse;
- ciclos;
- resultado final;
- vínculo com HP.

### Entrega 5 — Qualidade e homologação

- testes automatizados;
- concorrência;
- permissões;
- regressão;
- homologação operacional.
