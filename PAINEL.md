# Central de testes do Horulince

Para diagnosticar ou capturar placas, consulte [OCR.md](OCR.md). A Central mostra o estado das tentativas e o acervo distingue leituras aguardando consenso de placas consolidadas.

As abas **Demonstrações legadas** e **Acervo de capturas** integram detecção/captura facial autorizada, extração de veículos e consulta de imagens/eventos. Consulte [DEMONSTRACOES.md](DEMONSTRACOES.md) para instruções e limites. Reinicie o servidor do painel após atualizar o código.

Na pasta deste projeto, execute `iniciar_painel.cmd` com duplo clique ou use:

```powershell
Set-Location -LiteralPath "C:\caminho\Horulince"
.\.venv\Scripts\python.exe -m horulince painel
```

Abra **http://127.0.0.1:8765** no navegador e mantenha o terminal aberto.
O atalho abre esse endereço automaticamente no navegador padrão.
Se a porta estiver ocupada, use `--porta 8766`. Não é necessário ativar a venv.
O servidor é restrito ao próprio computador. O iPhone transmite vídeo para o PC;
o painel não precisa ser aberto no telefone.

## Roteiro de teste

1. Em **Estado do sistema**, confira as dependências, modelo e executável do Tesseract. O diagnóstico verifica disponibilidade; o funcionamento do OCR é verificado em uma análise real.
2. Em **Alvos de teste**, prepare a lista da próxima análise. A lista inicial procura um carro branco por características. Placas são opcionais e aceitam os padrões antigo e Mercosul. Não remova o último alvo; adicione um substituto primeiro. O botão de exemplo substitui a lista por registros fictícios com placas.
3. Na **Central de testes**, escolha um arquivo, envie um vídeo de até 250 MB, selecione webcam ou informe a URL RTSP/HTTP do iPhone. Para o celular, siga também `IPHONE.md`. “Testar imagem” verifica somente recepção; não gera alertas.
4. Ajuste o nome da origem e os parâmetros. Com placas nos alvos, mantenha OCR habilitado. Inicie a análise; o monitor mostra quadros realmente processados, veículos no quadro e tempo médio local. “Parar” solicita encerramento cooperativo; uma leitura de rede em andamento pode demorar até atingir seu timeout.
5. Em **Central de alertas**, selecione um candidato e confira o recorte, os campos de confiança e o caso. Informe operador, decisão e justificativa. A confirmação não realiza envio externo.
6. Em **Validação experimental**, selecione a execução e importe ou escreva a referência JSON com as passagens reais anotadas. Use a origem e os identificadores de alvos do experimento. “Montar estrutura” fornece somente um exemplo para editar; não inventa observações. Clique em “Calcular resultados” e exporte o relatório se desejar.
7. Em **Trilha de auditoria**, consulte os registros de criação e revisão. A exportação JSON inclui a trilha completa do banco.

## O que a avaliação mede

A referência deve cobrir os alvos e o intervalo efetivamente processados. Ao
interromper uma execução, anote apenas o trecho analisado. São medidos precisão e
revocação de eventos, TP, FP, FN e placa completa nos eventos pareados com placa
anotada. Uma ocorrência só é pareada uma vez; duplicatas contam como FP. Sem amostras,
os campos ficam “a medir”. Execuções com erro não ficam disponíveis para avaliação.
O tempo exibido no monitor mede processamento local, não a latência total do sistema.
Em parâmetros avançados, você também pode escolher modelos locais. Um detector de
placas especializado precisa ser fornecido e salvo em `models/`; a opção padrão
usa contornos experimentais.

## Dados e limites

O painel compartilha `dados/horulince.sqlite3` com a linha de comando. As configurações
de alvos, vídeos enviados e avaliações ficam em `dados/painel/`; evidências ficam em
`dados/evidencias/`. Não há envio a serviços externos. A tela mostra até 200 alertas,
100 execuções e 300 eventos de auditoria recentes; o banco mantém os registros anteriores.

A interface cobre veículos e demonstrações de detecção/captura facial autorizada.
A identificação de pessoas permanece indisponível: o detector de rostos não
realiza reconhecimento de identidade. Também não há autenticação de operadores, perfis,
retenção automática ou auditoria inviolável. O nome de operador é uma declaração
local, e não uma identidade autenticada.


## Revisões finais e consulta por placa

Alertas confirmados para análise ou descartados mantêm a decisão final e deixam de oferecer o formulário de revisão. Tentativas de sobrescrita retornam HTTP 409; mudanças de estado em outra sessão exigem atualizar e conferir novamente. O operador continua sendo uma declaração local, sem autenticação.

No Acervo de capturas, use Placa exata para consultar as leituras consolidadas armazenadas, combinando com origem, data e demais filtros. A consulta não depende de cadastro e não representa todas as passagens da fonte.
