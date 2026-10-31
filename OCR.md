# Diagnóstico e captura de placas

Na **Central de testes**, mantenha a leitura de placas (OCR) habilitada e use **Iniciar análise**. A opção **Testar imagem** apenas recebe vídeo; a demonstração de extração de veículos também não realiza OCR.

Habilite **Registrar leituras de placas no acervo** para guardar recortes e resultados mesmo quando a placa não corresponde a um alvo. A opção vem habilitada no painel; pode ser desligada quando a finalidade for guardar somente evidências de candidatos. O CLI exige `--registrar-placas` para essa gravação adicional.

No **Acervo de capturas**, filtre por:

- **Placas lidas (aguardando consenso):** texto em formato brasileiro e escore OCR de pelo menos 55/100, ainda sem a confirmação temporal exigida para um alerta por placa.
- **Placas consolidadas (OCR):** pelo menos três leituras consistentes, em tentativas de quadros diferentes do mesmo track, com predominância mínima de 70% na janela.

O registro de uma leitura não significa restrição do veículo, identificação definitiva ou correspondência com um caso. Leituras abaixo do limiar, inválidas ou conflitantes aparecem no diagnóstico do monitor, sem serem armazenadas como placas válidas. Alertas por placa continuam exigindo consenso; uma leitura pendente não é usada para contornar essa regra.

## O que foi corrigido

O localizador anterior selecionava os quatro maiores contornos e podia priorizar faróis, grades e para-choques em vez da placa. O fallback agora combina fundo claro e agrupamento de caracteres, incluindo placas que se misturam à carroceria branca, com deduplicação de regiões e limites de tamanho. Não é um detector treinado e pode falhar em placas pequenas, borradas, oblíquas ou fora dos formatos brasileiros suportados.

O OCR remove molduras/faixa superior quando os componentes permitem, amplia a linha de texto e usa duas variantes. Processa regiões em lote e, se necessário, tenta as duas melhores como linhas isoladas. Variantes do mesmo quadro nunca contam como observações temporais independentes. Não há substituição de caracteres para forçar uma placa conhecida.

Antes da primeira hipótese de placa, quadros sem leitura não penalizam seu início. Após uma hipótese existir, falhas e conflitos continuam ocupando a janela e expirando leituras anteriores. Nenhum limiar de confiança foi reduzido: o escore mínimo permanece 55/100. Esse escore nativo não é probabilidade de identificação.

O monitor informa se o OCR está desligado, aguardando vez, sem região, sem leitura válida, abaixo do limiar, conflitante ou aguardando consenso. Um timeout é mostrado e não interrompe toda a análise. Tentativas, leituras válidas, registros salvos e placas consolidadas são contados separadamente.

## Armazenamento

A tabela `plate_reads` guarda id, execução, track, origem, instante do vídeo, data de criação, placa, caminho da imagem e payload JSON. A chave `(run, track, plate)` evita registros repetidos. Quando surge consenso para a mesma leitura, o estado é promovido sem duplicar o registro. O recorte original é preservado; o payload informa o quadro posterior de confirmação.

Imagens ficam em `placas/`, ao lado do banco. Inclua essa pasta nos backups. A interface só fornece imagens registradas dentro dessa pasta. O resumo da execução é salvo ao encerrar; por isso `plate_reads.run`, assim como `alerts.run`, não tem FK para `runs.id` neste fluxo.

O esquema é criado automaticamente pelo sistema. O DBA pode usar `banco/atualizar_ocr_sqlite.sql`; o script completo de criação também inclui a tabela. Bancos, imagens e vídeo de teste continuam fora do Git.

## Validação com o vídeo atual

O diagnóstico inicial de seis quadros do vídeo substituído não retornou placa em nenhuma das 27 detecções de veículos amostradas. A seleção de regiões foi inspecionada visualmente e incluía grade/faróis.

Com a correção, uma execução dos primeiros 240 quadros, analisando um a cada três e tentando OCR em cada ciclo, processou 80 quadros e terminou sem erro: 159 tentativas de OCR, 11 leituras válidas, 3 registros de placa salvos e 1 consolidado. Esses registros não representam veículos únicos. O teste usou banco separado, em `output/diagnostico_ocr/final.sqlite3`.

Essa é uma verificação funcional de captura e persistência, não uma medição de precisão ou revocação sobre todas as placas do vídeo. Ainda há quadros sem leitura, e o tempo médio local foi de aproximadamente 1,37 segundo por quadro processado nesse experimento; não equivale a desempenho de produção ou latência total de rede.

Após atualizar, encerre o servidor antigo e abra novamente `iniciar_painel.cmd`. Para reproduzir pelo terminal, use um banco de teste separado:

```powershell
.\.venv\Scripts\python.exe -m horulince processar --fonte videos/transito1.mp4 --origem teste_ocr --max-quadros 240 --a-cada 3 --ocr-a-cada 1 --registrar-placas --banco output/teste_ocr/teste.sqlite3 --relatorio output/teste_ocr/execucao.json
```


A regressão após essas alterações executou 58 testes: 57 aprovados e 1 teste opcional de transmissão não executado. Foram cobertos localização em carroceria branca, fragmentos por região, conflitos, limiar de confiança, timeout, consenso temporal, persistência e imagens no acervo.
