# Exemplos da API criada por Gian

Esta pasta reúne os quatro arquivos recebidos de Gian e analisados pela equipe.
As cópias em [original/](original/) preservam o conteúdo enviado para facilitar
a leitura, a demonstração e a revisão do grupo.

## Arquivos para consultar

| Arquivo | Conteúdo |
| --- | --- |
| [mainAPI.py](original/mainAPI.py) | API FastAPI com cadastro fictício, detecções recebidas, passagens, alertas, revisão e auditoria. |
| [test_API.py](original/test_API.py) | 14 testes dos fluxos demonstrativos. |
| [requirements.txt](original/requirements.txt) | Dependências do exemplo. |
| [README.md original](original/README.md) | Explicação e exemplos enviados por Gian. |

## Executar no Windows

Na raiz do repositório, abra o PowerShell e execute:

```powershell
Set-Location exemplos/api-gian/original
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn mainAPI:app --host 127.0.0.1 --port 8000
```

A documentação interativa estará em [Swagger](http://127.0.0.1:8000/docs).
O nome do módulo para iniciar este exemplo é `mainAPI:app`, conforme o nome do
arquivo recebido. O comando `main:app` que aparece no README original precisa
desse ajuste.

Em outro terminal, dentro de `exemplos/api-gian/original`, execute os testes:

```powershell
.\.venv\Scripts\python.exe -m pytest test_API.py -q
```

## Roteiro de demonstração

1. Consulte `GET /vehicles` para ver o cadastro fictício.
2. No Swagger, abra `POST /detections`, escolha **Try it out** e envie:

   ```json
   {
     "placa_lida": "ABC1D23",
     "confianca_placa": 0.93,
     "modelo_detectado": "Uno",
     "confianca_modelo": 0.85,
     "cor_detectada": "preto",
     "origem": "demonstracao_grupo"
   }
   ```

3. Consulte `GET /traffic-records` e `GET /alerts` para localizar a passagem e o alerta.
4. Use o identificador retornado em `POST /alerts/{alerta_id}/review` para registrar
   uma revisão com operador e justificativa.
5. Consulte `GET /audit` para visualizar as ações registradas.

## Estágio deste exemplo

Este é um protótipo independente, com dados fictícios e armazenamento em memória.
Reiniciar o processo apaga seu histórico. A integração com o SQLite e o pipeline
do painel Horulince é uma próxima entrega.

A API recebe marca e modelo como textos enviados pelo cliente. A classificação
automática de marca/modelo ainda precisa de implementação própria. Os valores de
confiança são entradas demonstrativas. A rota de avaliação apresenta métricas
planejadas.

A revisão identificou pontos para corrigir antes da integração:

- requisições repetidas podem gerar passagens e alertas duplicados;
- datas precisam de padronização de fuso horário;
- operador e justificativa precisam rejeitar entradas formadas só por espaços;
- atributos sem confiança precisam ter resultado de comparação explícito;
- a limpeza do histórico precisa preservar vínculos entre passagens e alertas.

Os arquivos originais ficam disponíveis para que o grupo acompanhe essas
correções e planeje o uso do mesmo repositório SQLite do sistema atual.
