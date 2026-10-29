# Validação local — 23/10/2026

- Ambiente: Windows, Python 3.12.14, dependências em `requirements.lock.txt`, Tesseract 5.5.3.
- 18 testes automatizados aprovados: formatos e aproximação de placas, consenso e conflitos, associação/expiração de tracks, deduplicação, falha de gravação, revisão/auditoria, avaliação um-a-um e execução sem alertas.
- Compilação dos módulos e verificação de dependências (`pip check`) aprovadas.
- Vídeo original `transito1.mp4`: execução final com OCR habilitado, limitada aos primeiros 120 quadros, processando um a cada três. Foram processados 40 quadros e salvos dois candidatos por características, com evidências e registro de execução conferidos.
- Tempo médio de processamento local nessa execução: 663,46 ms por quadro processado. Não representa latência total de captura/rede/revisão nem desempenho de produção.
- Execução separada com placa-alvo fictícia `ABC1D23`: 60 quadros lidos, 20 processados, nenhum alerta. Isso apenas verifica que o caminho com placa-alvo executa; não permite inferir revocação.
- Placa sintética `ABC1D23` em imagem de texto: Tesseract retornou a sequência esperada, com confiança nativa 89. A região foi fornecida diretamente nesse teste, sem avaliar o localizador de placas. Não é uma taxa de acerto em cenas reais.
- Uma decisão de revisão foi registrada em banco separado de integração e apareceu na auditoria.

Não foram anotadas as ocorrências reais do vídeo; precisão e revocação continuam
sem medição. O recorte de placa por contornos, o rastreamento em cruzamentos/oclusões,
as condições noturnas e a qualidade por distância precisam de avaliação própria.
O código permite fornecer um detector de placas treinado, mas esse modelo não foi
fornecido nem treinado nesta etapa. A revisão atual é por terminal; não há telas,
autenticação ou módulo de identificação de pessoas implementados.

## Integração com iPhone — 23/10/2026

- Adicionados os comandos `iphone` e `testar-camera`, receptor de rede com fila de um quadro, timeouts e reconexão limitada. A análise continua no computador.
- 25 testes aprovados com `HORULINCE_TEST_STREAM=1`, incluindo o teste opcional de recepção real de MJPEG via OpenCV/FFmpeg em servidor HTTP limitado a `127.0.0.1`. Os testes de falha/reconexão usam fontes simuladas.
- Regressão com o arquivo de vídeo: 30 quadros lidos e 10 processados, sem erro.
- O teste por MJPEG valida o caminho de recepção de rede; não valida RTSP de um aplicativo específico nem o hardware do iPhone 13. Falta iniciar a transmissão no aparelho e testar seu endereço real.
- O guia `IPHONE.md` informa preparação do app transmissor, conexão na rede local, teste de imagem e comandos de análise.

## Painel funcional — 25/10/2026

- Servidor HTTP restrito ao computador, interface responsiva e APIs integradas ao pipeline e ao SQLite existentes. Não foram adicionadas dependências Python para a interface.
- 35 testes automatizados aprovados, incluindo APIs, revisão/auditoria, avaliação persistida, validação de fontes/alvos, exclusão mútua das análises e recepção real de MJPEG em loopback.
- JavaScript validado com `node --check`; módulos Python compilados sem erro.
- No navegador, uma análise real dos primeiros 120 quadros do vídeo processou 40 quadros e gerou dois candidatos por características. Os recortes foram exibidos e uma solicitação de revisão foi registrada por `operador_teste_painel`, com justificativa explícita de teste da interface.
- A interface rejeitou uma referência JSON malformada sem criar resultados. As métricas do vídeo permanecem sem medição porque não foi anotada a referência real.
- A parada solicitada pela interface encerrou uma segunda execução e preservou o resultado parcial como `interrompida`, sem manter a câmera ocupada.
- O diagnóstico exibiu dependências, YOLOv8n e Tesseract disponíveis. Integração com o iPhone físico continua dependente de iniciar e informar uma transmissão acessível.
