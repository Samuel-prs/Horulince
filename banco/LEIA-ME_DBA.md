# Banco de dados do Horulince

O arquivo `criar_banco_sqlite.sql` cria a estrutura utilizada pela versão atual do sistema, com índices auxiliares. Destino confirmado: **SQLite**. As tabelas principais correspondem a `horulince/storage.py` e a extensão de demonstrações a `horulince/demonstration.py`; o script não inclui dados e não altera o código da aplicação.

Para um banco existente, `atualizar_demonstracoes_sqlite.sql` adiciona somente `demo_runs` e `demo_events`, sem apagar registros anteriores. O painel também cria essa extensão automaticamente ao iniciar. Veja `DEMONSTRACOES.md` na raiz do projeto para uso e limites.

## Criação

No DB Browser for SQLite ou ferramenta equivalente:

1. Crie um banco novo chamado `horulince.sqlite3`.
2. Abra o arquivo `criar_banco_sqlite.sql` na opção de executar SQL.
3. Execute o script completo. O script gerencia a própria transação; execute fora de outra transação aberta.
4. Confira os resultados: `integrity_check` deve retornar `ok`; `foreign_key_check` não deve retornar linhas.

Se o executável `sqlite3` estiver instalado, também é possível criar pelo PowerShell, na raiz do projeto:

```powershell
New-Item -ItemType Directory -Force -Path .\dados | Out-Null
sqlite3 .\dados\horulince_novo.sqlite3 ".read banco/criar_banco_sqlite.sql"
```

O nome `horulince_novo.sqlite3` evita substituir o banco que já contém testes. Não substitua o banco existente para fazer a criação. `IF NOT EXISTS` permite reexecutar o script, mas não valida nem migra tabelas que já tenham outra estrutura.

Para testar o painel usando esse novo arquivo, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m horulince painel --banco .\dados\horulince_novo.sqlite3 --abrir
```

O caminho padrão do sistema é `dados/horulince.sqlite3`. SQLite utiliza um arquivo local e não exige servidor, porta, usuário ou senha. A aplicação precisa de permissão de escrita no arquivo e na pasta que o contém. Cada conexão deve habilitar `PRAGMA foreign_keys = ON`; a aplicação já faz isso.

## Dicionário de dados

| Tabela | Coluna | Tipo | Finalidade |
|---|---|---|---|
| runs | id | TEXT, PK | Identificador da execução. |
| runs | summary | TEXT, obrigatório | JSON com origem, contagens, tempo médio e estado da execução. |
| runs | configuration | TEXT, obrigatório | JSON com alvos e parâmetros usados naquela execução. |
| alerts | id | TEXT, PK | Identificador do candidato. |
| alerts | run | TEXT, obrigatório | Identificador da execução que produziu o candidato. |
| alerts | track | INTEGER, obrigatório | Identificador de acompanhamento do veículo, local à execução. |
| alerts | target | TEXT, obrigatório | Identificador do alvo de teste. |
| alerts | source | TEXT, obrigatório | Identificador da fonte de vídeo. |
| alerts | video_seconds | REAL, obrigatório | Instante observado na fonte, em segundos. |
| alerts | created_at | TEXT, obrigatório | Data/hora de gravação em ISO 8601, UTC. |
| alerts | state | TEXT, obrigatório | Estado da revisão; padrão `pendente`. |
| alerts | evidence | TEXT, obrigatório | Caminho do arquivo JPEG de evidência; não contém a imagem. |
| alerts | payload | TEXT, obrigatório | JSON com correspondência, leitura de placa e dados da detecção. |
| audit | seq | INTEGER, PK AUTOINCREMENT | Sequência dos eventos de auditoria. |
| audit | alert_id | TEXT, obrigatório, FK | Referência a `alerts.id`. |
| audit | at | TEXT, obrigatório | Data/hora do evento em ISO 8601, UTC. |
| audit | actor | TEXT, obrigatório | Operador informado ou `sistema`. |
| audit | action | TEXT, obrigatório | `criado` ou estado registrado na revisão. |
| audit | reason | TEXT, obrigatório | Justificativa da ação. |

Estados aceitos pela aplicação: `pendente`, `confirmado_para_analise`, `descartado` e `revisao_solicitada`. Confirmar para análise não confirma a identidade de uma pessoa ou a situação legal de um veículo. Essas regras são validadas pelo código; o esquema atual não possui CHECK para os estados nem para o conteúdo JSON.

O conjunto `(run, track, target)` é único em `alerts`. A FK `audit.alert_id` impede eventos sem alerta correspondente quando as FKs estão habilitadas. Não há exclusão em cascata.

Não existe FK entre `alerts.run` e `runs.id`: alertas são salvos durante o processamento; o resumo da execução é salvo no encerramento. Uma interrupção abrupta do processo pode deixar candidatos sem resumo. Não adicionar essa FK sem antes adaptar esse fluxo no código. As tabelas também mantêm o `rowid` do SQLite: a aplicação o utiliza para ordenar execuções.

## Arquivos externos e operação

O OCR usa a extensão `plate_reads`, criada por `atualizar_ocr_sqlite.sql` e pelo script completo. Colunas: `id` (PK), `run`, `track`, `source`, `video_seconds`, `created_at`, `plate`, `evidence` e `payload` (JSON). A combinação `(run,track,plate)` é única. O estado no payload distingue `pendente_consenso` de `consolidada`; as imagens ficam em `placas/`, ao lado do banco. A execução é resumida somente ao encerrar, portanto `run` não tem FK neste fluxo. Veja `OCR.md` para finalidade, limites e procedimento de teste.

As demonstrações usam duas tabelas adicionais: `demo_runs` guarda `id`, `mode`, `source`, `started_at`, `finished_at`, `state`, `configuration` (JSON) e `summary` (JSON); `demo_events` guarda `id`, `run` (FK para `demo_runs.id`), `kind`, `source`, `created_at`, `video_seconds`, `image` (caminho opcional) e `payload` (JSON). A execução é criada antes dos seus eventos. Não há exclusão em cascata. Imagens demonstrativas ficam em `demonstracoes/imagens/`, ao lado do banco, e precisam acompanhar o backup.

- As imagens ficam em `evidencias/`, ao lado do banco. Ao migrar, preserve os arquivos e ajuste os caminhos em `alerts.evidence` se a localização mudar. O painel só entrega evidências dentro dessa pasta.
- Alvos editáveis do painel ficam em `painel/alvos.json`, ao lado do banco. A configuração de cada execução guarda uma cópia dos alvos em `runs.configuration`.
- Vídeos enviados e avaliações ficam em `painel/uploads/` e `painel/avaliacoes/`, ao lado do banco. Vídeos originais também podem estar em `videos/` na raiz do projeto.
- A auditoria é local e editável por quem tem acesso ao arquivo; não há autenticação de operadores ou garantia de imutabilidade nesta versão.
- Para backup consistente, pare o painel e qualquer processamento antes de copiar o banco e os arquivos relacionados, ou utilize a API de backup do SQLite para o banco e coordene a cópia das evidências.

O script cria o esquema; não migra dados existentes e não cria cadastros de pessoas ou reconhecimento facial, funcionalidades ausentes na implementação atual.
