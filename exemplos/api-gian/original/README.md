# Horulince API – MVP (protótipo acadêmico)

API em Python (FastAPI) para o MVP do *Horulince*, com escopo de **veículos**:

- leitura e validação de **placa** (padrão antigo e Mercosul);
- identificação do **modelo** do veículo e conferência com o cadastro (detecta possível placa clonada);
- **registros de trânsito** (histórico de passagens);
- **alertas** com **validação humana obrigatória** e trilha de **auditoria**.

> Todos os dados são **fictícios**. Não há consulta a DETRAN/polícia. A busca de pessoas desaparecidas ficou fora do MVP.

## Como se encaixa com a visão computacional

A detecção (YOLO + OpenCV + Tesseract) roda **fora** da API e envia o resultado para `POST /detections`:
placa lida, modelo/marca/cor detectados e as confianças. A API valida, registra a passagem, compara com
o cadastro e decide se há alerta.

## Executar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Documentação automática: `/docs` (Swagger), `/redoc`, `/openapi.json`.

Testes: `pytest -q`

## Rotas

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status da API |
| GET | `/dashboard` | Resumo operacional fictício |
| POST | `/detections` | Recebe placa + modelo detectados, registra passagem e avalia alerta |
| GET | `/vehicles` | Cadastro fictício (filtros `com_restricao`, `marca`, `modelo`) |
| GET | `/vehicles/models` | Catálogo de marcas/modelos reconhecíveis |
| GET | `/vehicles/{placa}` | Cadastro + histórico de passagens da placa |
| GET | `/traffic-records` | Registros de trânsito (filtros `placa`, `origem`, `modelo`, `com_divergencia`, `desde`, `ate`) |
| GET | `/traffic-records/{id}` | Detalha um registro |
| POST | `/traffic-records/purge` | Expurga registros além do prazo de retenção (preserva os ligados a alertas abertos) |
| GET | `/alerts` | Lista alertas (filtro `estado`) |
| GET | `/alerts/{id}` | Detalha alerta |
| POST | `/alerts/{id}/review` | Confirmar para análise / descartar / solicitar revisão (operador + justificativa) |
| GET | `/audit` | Trilha de auditoria |
| GET | `/evaluation/metrics` | Métricas planejadas, valor "a medir" |

## Resultados de `POST /detections`

| `resultado` | Significado | Alerta? |
|---|---|---|
| `formato_invalido` | Não é placa antiga nem Mercosul | não (descartado) |
| `baixa_confianca` | Confiança da placa < 0,60 | não (descartado) |
| `sem_cadastro` | Placa válida, fora do cadastro | não (passagem registrada) |
| `cadastro_ok` | Placa e características conferem | não (passagem registrada) |
| `divergencia_modelo` | Modelo/marca/cor diferem do cadastro (possível clone) | sim |
| `restricao` | Veículo com restrição de roubo/furto | sim |
| `restricao_com_divergencia` | Os dois acima | sim |

O modelo detectado só entra na conferência se a confiança for ≥ 0,50.

## Exemplo

```bash
curl -X POST http://127.0.0.1:8000/detections \
  -H "Content-Type: application/json" \
  -d '{"placa_lida":"DEF5678","confianca_placa":0.93,"marca_detectada":"Volkswagen","modelo_detectado":"Gol","confianca_modelo":0.85,"origem":"video_teste_01"}'
```

## Atenção: retenção de dados

O artigo prevê descartar imediatamente os dados sem correspondência (RNF03). Registros de trânsito
guardam todas as passagens, o que muda esse comportamento. Por isso há prazo de retenção
(`RETENCAO_DIAS`, 30 por padrão, **valor provisório a definir com análise jurídica**) e a rota de expurgo.
Recomenda-se citar essa decisão no artigo.

## Próximos passos

- Persistência real (PostgreSQL/SQLAlchemy) e expurgo agendado.
- Autenticação/perfis (RNF02): OAuth2/JWT com papéis (operador, auditor, admin).
- Conectar o pipeline de visão computacional e medir acerto de placa e de modelo.
