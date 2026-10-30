import re
import cv2
import pytesseract
from ultralytics import YOLO

# Ajuste se instalou em outra pasta
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CAMINHO_VIDEO = "videos/transito1.mp4"
VEICULOS = [2, 3, 5, 7]
# Placa antiga (ABC1234) e Mercosul (ABC1D23)
PADRAO = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
LARGURA_MINIMA = 70   # ignora veículos pequenos/distantes
OCR_A_CADA = 5         # roda OCR a cada 5 quadros (mais rápido)

modelo = YOLO("yolov8n.pt")
video = cv2.VideoCapture(CAMINHO_VIDEO)
largura = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
altura = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = video.get(cv2.CAP_PROP_FPS) or 30
saida = cv2.VideoWriter("saida_placas.mp4",
                        cv2.VideoWriter_fourcc(*"mp4v"), fps, (largura, altura))


def ler_placa(recorte):
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    cinza = cv2.resize(cinza, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = "--psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    texto = pytesseract.image_to_string(binaria, config=config)
    for pedaco in texto.split():
        limpo = re.sub(r"[^A-Z0-9]", "", pedaco.upper())
        if PADRAO.match(limpo):
            return limpo
    return None


n = 0
while True:
    ok, quadro = video.read()
    if not ok:
        break
    n += 1

    resultado = modelo(quadro, classes=VEICULOS, conf=0.4, verbose=False)[0]
    desenhado = resultado.plot()

    if n % OCR_A_CADA == 0:
        for caixa in resultado.boxes:
            x1, y1, x2, y2 = map(int, caixa.xyxy[0])
            if x2 - x1 < LARGURA_MINIMA:
                continue
            metade_baixa = quadro[y1 + (y2 - y1) // 2: y2, x1:x2]  # placa fica embaixo
            placa = ler_placa(metade_baixa)
            if placa:
                print(f"Quadro {n}: placa {placa}")
                cv2.putText(desenhado, placa, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    saida.write(desenhado)
    cv2.imshow("Horulince - placas", desenhado)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

video.release()
saida.release()
cv2.destroyAllWindows()
print("Pronto! Resultado salvo em saida_placas.mp4")
