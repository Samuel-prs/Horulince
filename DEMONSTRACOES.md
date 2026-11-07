# Demonstrações do legado

Abra `iniciar_painel.cmd` e acesse **Demonstrações legadas**. Se o painel estava aberto antes da atualização, encerre o servidor com Ctrl+C, inicie novamente e recarregue o navegador.

## Testar pela interface

1. Escolha **Detecção e captura facial** ou **Extração de veículos e cores**.
2. Selecione webcam, iPhone/rede ou um vídeo disponível. Para enviar um vídeo, use o envio na Central de testes e retorne à demonstração.
3. Configure origem, limite de quadros (1 a 10.000) e intervalo de análise. Confirme a autorização de uso das imagens para a demonstração facial.
4. Inicie. O monitor mostra caixas, resultados do quadro, quantidade de quadros, FPS médio de processamento, tempo médio e imagens salvas. O navegador exibe o quadro mais recente; pode pular quadros se a inferência for mais rápida que a atualização da interface.
5. Na demonstração facial, pressione **Capturar rosto**. O próximo quadro analisado deve conter exatamente um rosto; caso contrário, a solicitação é recusada com mensagem no monitor. A captura salva o quadro original completo, como no legado, sem caixas desenhadas. Uma solicitação feita ao final do vídeo pode não alcançar outro quadro; nesse caso nenhuma captura será salva.
6. Na extração de veículos, recortes são salvos automaticamente a cada pelo menos 2 segundos da fonte, até 200 imagens por execução. Outros resultados continuam registrados como eventos sem imagem. A detecção considera veículos com largura mínima de 120 pixels, como no extrator legado.
7. Use **Parar** para encerrar antes do limite. O histórico preserva execuções concluídas, interrompidas e com erro tratado. Uma queda abrupta do processo pode deixar a execução marcada como `executando`; confira o horário e o servidor antes de interpretar esse estado histórico.

O legado `captura_rosto.py` utiliza Haar Cascade frontal do OpenCV; esta integração mantém sua detecção e captura. Não há reconhecimento de identidade, cadastro biométrico, correspondência de rostos, inferência de emoções, idade ou gênero. A detecção pode falhar ou produzir falsos positivos, especialmente com perfil, pouca luz ou rostos pequenos. Os resultados não identificam desaparecidos.

A extração demonstrativa usa YOLOv8n e cores por HSV. Não usa alvos nem faz OCR; para placas, correspondências e revisão, utilize a **Central de testes**, que também mostra os dados das detecções do quadro atual. As contagens entre quadros não representam veículos/pessoas únicos. FPS é a taxa média local de quadros processados desde o início, não a taxa de captura nem a latência ponta a ponta.

## Acervo de capturas

A aba **Acervo de capturas** reúne evidências e resultados dos candidatos do pipeline principal, detecções faciais por quadro (incluindo zero rostos), capturas faciais autorizadas, detecções/recortes de veículos e eventos de criação/revisão dos alertas.

Filtre por tipo, placa exata consolidada (ABC1234 ou ABC1D23), origem exata, identificador completo da execução, intervalo de datas UTC, trecho dos dados e presença de imagem. Os resultados têm paginação de 30 registros. **Consultar**, no histórico da demonstração, preenche o filtro de execução. Selecione um registro para ver imagem, dados completos em JSON e download individual. **Exportar consulta** exporta todos os metadados do filtro, inclusive os que não estão na página atual; as imagens são baixadas individualmente.

As consultas recuperam o que esta versão efetivamente gravou. Não importam automaticamente CSVs ou fotos antigas, não reconstroem detecções de execuções anteriores e não guardam cópia integral de cada vídeo/quadro. Evidências do pipeline principal continuam sendo gravadas somente para candidatos.

## Arquitetura e banco

`horulince/demonstration.py` adapta o legado sem importar scripts que abrem janelas ou solicitam entrada no terminal. Reutiliza as fontes e o gerenciador de tarefas; apenas uma operação pode ler a fonte por vez. Parada e captura são sinalizadas ao worker responsável pela câmera. Os scripts antigos permanecem em `legado/`.

O painel cria de forma aditiva `demo_runs` (configuração, origem e resumo) e `demo_events` (instante, tipo, resultados e caminho opcional da imagem), sem modificar tabelas de alertas. A FK dos eventos aponta para a execução criada antes da análise. As imagens ficam em `demonstracoes/imagens/`, ao lado do SQLite. Inclua essa pasta no backup, junto do banco e de `evidencias/`.

O DBA pode aplicar `banco/atualizar_demonstracoes_sqlite.sql` ao banco existente. O script completo `banco/criar_banco_sqlite.sql` também inclui as novas tabelas. O acervo consulta essas tabelas com alertas e auditoria, sem duplicar registros antigos. Ao restaurar em outra pasta, ajuste caminhos de imagens se necessário.

Resultados demonstrativos ficam separados da avaliação de precisão/recall dos alertas. Não é calculada métrica de acerto facial sem referência anotada. O processamento permanece local e o painel restrito a localhost.

## Validação

Os testes em `tests/test_demonstration.py` cobrem autorização, captura com um rosto, recusa com zero/múltiplos rostos, parada, erro de fonte, erro de gravação, consulta unificada, filtros, paginação e exportação. Os rostos dos testes são detectores simulados sobre quadros sintéticos; não medem a qualidade do Haar Cascade. A demonstração de veículos foi verificada separadamente com o modelo local e o vídeo de trânsito do projeto, em banco de validação separado.
