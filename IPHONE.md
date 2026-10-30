# Usar o iPhone 13 como câmera do Horulince

O iPhone captura e transmite as imagens pela rede local. O computador Windows
executa a detecção de veículos, o OCR e o registro dos candidatos. Este modo não
executa a IA no iPhone e não inclui identificação de pessoas.

## 1. Preparar o iPhone

1. Conecte o iPhone e o computador à mesma rede Wi-Fi, com comunicação entre os dispositivos. Redes de visitantes podem bloquear essa comunicação.
2. Instale um aplicativo que **transmita** a câmera em RTSP. Uma opção é [RTSP & RTMP Cam — OctoStream](https://apps.apple.com/br/app/rtsp-rtmp-cam-octostream/id6474928937), cuja descrição oficial informa transmissão RTSP local e vídeo H.264. Confirme os requisitos atuais de iOS na App Store.
3. Autorize câmera e rede local quando o app solicitar. O Horulince só precisa de vídeo; áudio pode ficar desligado.
4. Selecione o modo de servidor/câmera RTSP, use a câmera traseira e inicie a transmissão. Comece com 720p e orientação horizontal; ajuste conforme a legibilidade da placa e a velocidade do computador.
5. Mantenha o aplicativo em primeiro plano e o iPhone desbloqueado durante o teste. Copie a **URL completa da transmissão** exibida no app. Não é o endereço de uma página de visualização.

Exemplo ilustrativo: `rtsp://192.168.1.20:8554/live`. O endereço real, a porta e o
caminho vêm do aplicativo; não use esse exemplo sem substituir pelos valores reais.

## 2. Testar a conexão no computador

Abra um terminal nesta pasta do projeto e execute:

```powershell
.\.venv\Scripts\python.exe -m horulince testar-camera --mostrar
```

Cole a URL quando solicitado. O teste mostra a imagem por cerca de dez segundos,
sem carregar a IA e sem salvar fotografias. Q encerra antes. Ao terminar, informa
resolução, quadros recebidos e reconexões. Também é possível passar
`--fonte "URL_DO_APP"` e `--segundos 20`.

## 3. Iniciar a varredura

Teste inicial por tipo e cor:

```powershell
.\.venv\Scripts\python.exe -m horulince iphone --tipo carro --cor branco --sem-ocr
```

Busca de placa de teste:

```powershell
.\.venv\Scripts\python.exe -m horulince iphone --placa ABC1D23 --tipo carro --cor branco
```

O programa pede o endereço, abre a visualização no computador e mostra candidatos
para revisão. Q encerra. As mesmas opções de `processar` funcionam no modo `iphone`,
incluindo `--lista alvos.exemplo.json`, `--banco` e `--modelo-placa`.
O script `iniciar_iphone.ps1` também oferece atalhos:

```powershell
.\iniciar_iphone.ps1 -Testar
.\iniciar_iphone.ps1 -Placa ABC1D23 -Tipo carro -Cor branco
```

Se o Windows impedir scripts PowerShell, use diretamente os comandos Python acima.

## Funcionamento e limites

- O receptor mantém apenas o quadro mais recente disponível, reduzindo o acúmulo de atraso quando o OCR demora. Isso não garante tempo real nem impede buffers internos do transmissor/decoder.
- Há timeout de abertura/leitura e até três novas tentativas após falhas consecutivas. Falta persistente de imagem encerra a análise com erro; execute novamente após corrigir a conexão.
- Depois de uma reconexão ou pausa prolongada, o histórico de rastreamento é limpo. Leituras de placas não são transferidas entre sessões.
- O modo iPhone analisa cada quadro que o consumidor consegue obter (`--a-cada 1`). Ele pode descartar muitos quadros entre inferências; não é uma gravação completa do vídeo.
- Placas precisam estar legíveis, com boa iluminação e pouco movimento. A câmera deve ficar estável. O localizador de placas por contornos continua experimental; usar um celular não resolve essa limitação.
- Use este fluxo em rede local. Não é necessário expor portas no roteador. O endereço da câmera não é guardado como origem: o padrão do modo é `iphone13`.

## Se não aparecer imagem

Confira se o aplicativo está transmitindo no modo RTSP, se a URL foi copiada inteira,
se as permissões de câmera/rede local estão ativas e se os dispositivos estão na
mesma rede acessível. Um navegador pode não abrir RTSP; isso não prova que o fluxo
falhou. O aplicativo deve ser servidor de câmera, e não apenas visualizador de outras
câmeras. Se a rede isola clientes, teste outra rede local que permita a comunicação.

O teste físico com seu iPhone depende de iniciar essa transmissão e informar a URL.
Até esse teste, compatibilidade e qualidade no aparelho ainda não estão confirmadas.

Fontes consultadas em 23/10/2026: [descrição oficial do OctoStream na App Store](https://apps.apple.com/br/app/rtsp-rtmp-cam-octostream/id6474928937) e [documentação de timeouts do OpenCV](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html).
