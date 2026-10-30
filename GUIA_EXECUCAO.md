# Horulince — módulo experimental de veículos

## Painel funcional

Execute `iniciar_painel.cmd` ou `.\.venv\Scripts\python.exe -m horulince painel`
e abra `http://127.0.0.1:8765`. O [guia do painel](PAINEL.md) descreve o roteiro
de teste de vídeo/iPhone, alvos, análise, alertas, revisão, auditoria e avaliação.

Cópia de trabalho melhorada do projeto `horulince-ia`. Os scripts originais estão
em `legado/` para consulta; não foram alterados na pasta do Desktop. Nenhum dado de
cadastro de rostos foi copiado. A implementação atual cobre veículos, revisão local por painel/linha de comando,
demonstrações de detecção facial e um acervo pesquisável. A identificação de pessoas
continua indisponível.

Para usar a câmera do **iPhone 13**, consulte [o guia do iPhone](IPHONE.md).
O comando `python -m horulince iphone` recebe a transmissão do celular pela rede
local; a IA continua sendo executada no computador.

## Preparar e executar no PowerShell

Requer Python 3.12 ou superior e Tesseract instalado para OCR.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m horulince processar --max-quadros 120 --sem-ocr
```

`requirements.lock.txt` registra as versões usadas na validação deste projeto
(Python 3.12 / Windows). Para reproduzir esse ambiente, use esse arquivo no lugar
de `requirements.txt` ao instalar as dependências.

O vídeo de teste e o modelo YOLOv8n foram copiados para `videos/transito1.mp4` e
`models/yolov8n.pt`. São ignorados no Git; em outra máquina, forneça os arquivos
ou use `--fonte` e `--modelo`. O programa exige modelo local existente.

Buscar placa em um vídeo de teste:

```powershell
.\.venv\Scripts\python.exe -m horulince processar --fonte videos/transito1.mp4 --origem video_teste --placa ABC1D23 --tipo carro --cor branco --mostrar
```

Usar uma lista fictícia de alvos:

```powershell
.\.venv\Scripts\python.exe -m horulince processar --lista alvos.exemplo.json --origem video_teste
```

`--lista` substitui `--tipo`, `--cor` e `--placa`. Com placa informada, o sistema
exige consenso do OCR; apenas cor/tipo não geram alerta para esse alvo.
Sem placa informada, os alertas são de características e têm menor especificidade.

Para webcam autorizada use `--fonte 0 --origem camera_teste --mostrar`.
`tempo_real.py` preserva essa entrada; `buscar_alvo.py` usa o vídeo padrão.
Todos os caminhos padrão são relativos ao projeto, sem depender da pasta do terminal.
`--tesseract` ou a variável `TESSERACT_CMD` configuram o executável; no Windows,
também é verificado `C:\Program Files\Tesseract-OCR\tesseract.exe`.

## Alterações de confiabilidade

- Validação dos formatos antigo e Mercosul. Placas exatas e aproximadas têm rótulos diferentes; nenhuma recebe probabilidade de identificação de 100%.
- Rastreamento por sobreposição (IoU) com IDs por veículo. Associações ambíguas descartam o histórico de OCR; IDs expiram. Não é reidentificação robusta.
- Consenso exige pelo menos três leituras da mesma placa e 70% da janela de até oito tentativas. Cada quadro contribui no máximo uma vez. Falhas também ocupam a janela.
- O histórico do OCR expira após dois segundos de vídeo sem leitura; o rodízio atende até dois veículos por ciclo de OCR.
- Localização de regiões de placa por contornos e OCR com contraste/binarização. `--modelo-placa caminho.pt` permite um detector YOLO específico treinado para placas. O YOLOv8n fornecido detecta veículos, não placas. O fallback por contornos é experimental e não corrige perspectiva.
- Confiança da detecção, confiança média do OCR (escala nativa 0–100) e compatibilidade de características são campos distintos. Nenhum está calibrado como probabilidade de identidade.
- Evidência só é salva quando há candidato. Um alerta por alvo/track/execução. IDs novos após oclusão podem gerar duplicatas; isso é contado na avaliação.
- Câmera liberada mesmo em falhas. Verificação de abertura e de gravação; configuração de modelos e caminhos fora das funções de negócio.

## Alertas e revisão humana

```powershell
.\.venv\Scripts\python.exe -m horulince alertas --estado pendente
.\.venv\Scripts\python.exe -m horulince revisar ID_DO_ALERTA --estado revisao_solicitada --operador "Operador de teste" --justificativa "Necessário conferir a evidência"
.\.venv\Scripts\python.exe -m horulince auditoria --alerta ID_DO_ALERTA
```

Estados: `pendente`, `revisao_solicitada`, `confirmado_para_analise`, `descartado`.
A confirmação apenas registra uma decisão local; não envia informações a terceiros.
O comando de listagem mostra o caminho absoluto do recorte, origem, instante no vídeo,
execução e dados de correspondência. O SQLite fica em `dados/horulince.sqlite3`,
as evidências em `dados/evidencias/` e o resumo em `dados/ultima_execucao.json`.
`--banco` e `--relatorio` permitem caminhos separados para experimentos.
Informar `--origem` evita persistir URLs e credenciais da câmera.

A auditoria registra criação, operador declarado, estado e justificativa. É um
registro local editável por quem tem acesso ao banco: não há autenticação,
criptografia própria, controle de perfis, garantia contra adulteração ou política
automática de retenção. Não representa uma implantação operacional completa.

## Avaliação com referência anotada

Anote manualmente cada passagem do alvo: identificador único, alvo, origem, início e
fim em segundos. Opcionalmente informe a placa legível. O arquivo
`referencia.exemplo.json` é apenas um exemplo fictício, não uma anotação do vídeo.

```powershell
.\.venv\Scripts\python.exe -m horulince avaliar --execucao ID_DA_EXECUCAO --referencia minha_referencia.json
```

O ID aparece ao fim do processamento e no resumo JSON. Avalie somente uma execução
por vez; a referência deve cobrir exatamente a fonte, intervalo e alvos processados.
O banco guarda também os parâmetros e o resumo de execuções concluídas, inclusive
as que não geraram alertas; identificadores desconhecidos são rejeitados.
Uma passagem só pode corresponder a um alerta. São calculados TP, FP, FN, precisão e
revocação de eventos. A placa completa é avaliada separadamente, apenas nos eventos
pareados com placa anotada. Um evento pareado não comprova leitura correta da placa.
Sem amostras, as respectivas métricas permanecem `null`. Não é calculada taxa de
falsos positivos, pois faltam negativos anotados. O relatório de processamento mede
tempo local, sem representar latência total de rede, captura ou revisão humana.

## Testes

Os testes de regras, rastreamento, SQLite e avaliação usam somente a biblioteca padrão:

```powershell
python -m unittest discover -s tests -v
```

Os scripts `teste_*.py` originais em `legado/` são demonstrações, não testes de regressão.
Não execute a captura de rostos para testar o módulo de veículos.


## Demonstrações e acervo

O painel integra detecção/captura facial autorizada e extração de veículos do legado em um módulo separado. A aba Acervo de capturas consulta imagens, resultados e auditoria com filtros, histórico e exportação. Veja [DEMONSTRACOES.md](DEMONSTRACOES.md). Identificação de pessoas e emoções não são implementadas.
