import cv2
from ultralytics import YOLO

CAMINHO_VIDEO = "videos/transito1.mp4"
VEICULOS = [2, 3, 5, 7]  # carro, moto, ônibus, caminhão (códigos do YOLO)

modelo = YOLO("yolov8n.pt")
video = cv2.VideoCapture(CAMINHO_VIDEO)

largura = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
altura = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = video.get(cv2.CAP_PROP_FPS) or 30

saida = cv2.VideoWriter("saida_video.mp4",
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps, (largura, altura))

while True:
    ok, quadro = video.read()
    if not ok:
        break

    resultado = modelo(quadro, classes=VEICULOS, conf=0.4, verbose=False)[0]
    desenhado = resultado.plot()  # quadro com as caixas desenhadas

    saida.write(desenhado)
    cv2.imshow("Horulince - deteccao", desenhado)
    if cv2.waitKey(1) & 0xFF == ord("q"):  # aperte q para sair
        break

video.release()
saida.release()
cv2.destroyAllWindows()
print("Pronto! Resultado salvo em saida_video.mp4")
