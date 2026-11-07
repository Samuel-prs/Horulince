# Revisão da API enviada por Gian

Data: 31/10/2026. Arquivos analisados: `mainAPI.py`, `README.md`, `requirements.txt` e `test_API.py`. Os originais foram preservados. Os testes usaram cópias em `output/revisao_gian/original/`, ambiente virtual separado e dados fictícios em memória. O banco operacional não foi usado.

## Conclusão

A contribuição é útil como base de integração: contratos Pydantic, OpenAPI, motivos de alerta, histórico e revisão humana com auditoria. Ainda não deve substituir o back-end atual. A persistência é em memória, os contratos de confiança diferem do OCR atual e parte das mensagens presume uma classificação de marca/modelo que o detector não realiza.

Não foi criado um segundo serviço em produção nem substituído SQLite por outro banco. FastAPI e suas dependências foram instalados somente no ambiente isolado de revisão.

## Problemas confirmados com execução

| Prioridade | Local no arquivo enviado | Comportamento reproduzido | Correção proposta |
|---|---|---|---|
| Alta | `mainAPI.py:212`, `registrar_deteccao` | Duas requisições iguais geram dois registros e dois alertas. Dicionários são o armazenamento. | Reutilizar o repositório SQLite, transações e chave idempotente. Definir se o evento representa leitura, track ou passagem. |
| Alta | `mainAPI.py:253` | `confianca_modelo=None` é considerada confiável: informar Gol para a placa fictícia de um Corolla gera divergência sem confiança. | Ausência deve significar não avaliado. Só comparar atributos com confiança válida e vocabulário definido. |
| Alta | `mainAPI.py:86`, `listar_registros` | Uma data sem fuso é aceita; compará-la com filtro UTC retorna HTTP 500. | Exigir fuso na entrada, converter para UTC e validar intervalo. Aplicar ao histórico e ao expurgo. |
| Alta | `mainAPI.py:460` | O expurgo remove o registro de um alerta finalizado, mas mantém o alerta apontando para um `registro_id` que retorna 404. | Preservar o vínculo necessário ou guardar snapshot suficiente, com limpeza transacional e auditada. |
| Alta | `mainAPI.py:151` | Operador com dois espaços e justificativa com cinco espaços são aceitos para finalizar um alerta. | Remover espaços antes de validar e rejeitar vazio/nulo. Limitar tamanho. Operador informado não substitui autenticação. |
| Média | `registrar_deteccao` | Sem marca, modelo ou cor, a resposta `cadastro_ok` afirma que as características conferem. | Separar placa cadastrada de características verificadas. Atributos ausentes devem ser `nao_avaliados`. |

As sondas e seus resultados estão em `output/revisao_gian/verificar_casos_adicionais.py` e `resultados_adicionais.json`. O expurgo foi executado somente sobre dicionários fictícios da cópia de avaliação.

## Outros achados da leitura

- **Persistência:** reiniciar o processo perde registros/auditoria; múltiplos workers teriam estados independentes. Um lock em memória não substitui transações de banco.
- **Marca/modelo:** a API recebe esses textos do cliente. O catálogo de Uno/Gol/Civic é uma lista, não um classificador. Nosso YOLOv8n detecta carro/moto/ônibus/caminhão; não preencher marca/modelo com nomes inventados.
- **Confianças:** a API recebe 0–1; o Tesseract atual usa escore nativo 0–100. Definir conversão, procedência e campos separados. Nenhum dos valores equivale a probabilidade calibrada de identificação. `mainAPI.py:338` multiplica por 0,7 diante de divergências; preservar o escore de OCR e os motivos em separado, sem penalidade arbitrária.
- **Consenso temporal:** uma requisição com confiança de placa acima de 0,60 já pode criar alerta na API. O adaptador não deve perder o consenso entre quadros e a associação conservadora por track do pipeline atual.
- **Cores:** `cinza` e `prata` no cadastro não coincidem diretamente com `cinza/prata` no painel. Marca/cor também não têm confiança própria nessa API. Normalizar e definir quais atributos podem gerar divergências.
- **Acesso:** consultas, revisão e expurgo não têm autenticação/perfis. Antes de disponibilizar para outros computadores, implementar controle de acesso. O painel atual também não autentica operadores e permanece local.
- **Retenção:** registrar toda passagem, inclusive sem correspondência, amplia a coleta atual. Os 30 dias são uma configuração provisória do protótipo enviado. Não foi adotado armazenamento geral de passagens ou expurgo automático.
- **Histórico:** `/vehicles/{placa}` retorna 404 para placa sem cadastro mesmo quando há passagens em `/traffic-records`. O histórico deve poder existir sem ficha cadastral.
- **Testes:** cliente e dicionários são compartilhados. Usar fixtures com repositório temporário e incluir duplicidade, datas, campos em branco, reinício, concorrência e limpeza.
- **Dependências:** estão sem versões. Registrar ambiente reproduzível; a instalação isolada passou nos testes, mas emitiu aviso de depreciação na combinação FastAPI/Starlette/TestClient/httpx. As dependências do painel não foram alteradas.
- **Inicialização:** para o arquivo enviado, o comando é `uvicorn mainAPI:app --host 127.0.0.1 --port 8000`. O README usa `main:app`, que exigiria renomear o arquivo.
- **Métricas:** `/evaluation/metrics` é um plano com valores “a medir”. Preservar as avaliações reais do nosso módulo ao integrar, sem substituí-las pela lista estática.

## Aplicado ao sistema atual

1. Alertas confirmados para análise ou descartados não podem ter a decisão sobrescrita. A interface mantém os dados visíveis e remove o formulário nesses estados. Uma reabertura exigirá fluxo próprio futuro, com justificativa/auditoria.
2. UPDATE condicional e auditoria ficam na mesma transação SQLite. Entre duas decisões finais concorrentes, apenas uma é salva; a outra recebe HTTP 409 e não gera auditoria falsa de sucesso.
3. A interface envia o estado exibido. Se mudou de pendente para revisão solicitada, uma ação da tela antiga recebe conflito e os dados são atualizados. Isso detecta mudança de estado; não é versionamento completo de edições que mantenham o mesmo estado.
4. Operador/justificativa são textos reais, sem converter `null` para o nome `None`, com remoção de espaços e limites de 100/2000 caracteres.
5. O acervo ganhou **Placa exata**, com normalização de letras/hífen/espaços, validação dos dois formatos e SQL parametrizado sobre `payload.placa`. Funciona sem cadastro e com filtros/exportação. Não considera uma placa apenas mencionada em justificativa. Recupera somente resultados armazenados; não é histórico completo de trânsito.

Não é necessária migração de banco nem dependência nova do painel. A API enviada não foi conectada automaticamente ao pipeline.

## Próximas entregas para Gian

1. Separar `create_app(repository)` das regras e remover persistência em dicionários. Reutilizar o SQLite e testar com banco temporário.
2. Alinhar contrato: UUIDs textuais, `revisao_solicitada` em lugar de `em_revisao`, confiança por atributo, datas UTC e resultados não avaliados.
3. Criar adaptador da saída real do pipeline, preservando consenso e idempotência. Vincular evidência por identificador; não aceitar caminho arbitrário de arquivo do cliente.
4. Corrigir os seis casos reproduzidos antes de conectar o painel, mantendo uma única fonte de verdade para alertas e auditoria.
5. Tratar autenticação/perfis e política de retenção como entregas explícitas do grupo.

## Verificação

- API original: **14 testes aprovados**; os seis problemas adicionais não são cobertos pelos testes enviados.
- Sistema integrado: **47 testes aprovados e 1 teste opcional de transmissão não executado** nesta rodada, incluindo concorrência, conflito por estado, campos nulos e filtro exato de placa.
- Sintaxe JavaScript verificada com `node --check`; diferenças revisadas com `git diff --check`.
- Os arquivos de Downloads foram preservados. Ambientes isolados e resultados brutos de validação ficam em output/, excluídos do versionamento.
