import csv
import re
from datetime import datetime
from pathlib import Path

import cv2

BASE = Path(__file__).parent
PASTA_ROSTOS = BASE / "dados" / "rostos"
REGISTRO = BASE / "dados" / "registro_rostos.csv"
PASTA_ROSTOS.mkdir(parents=True, exist_ok=True)

# Detector de rosto que já vem com o OpenCV
detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

nome = input("Nome da pessoa (cadastro de teste): ").strip()
nome_arquivo = re.sub(r"[^a-zA-Z0-9_-]", "_", nome) or "sem_nome"
if input("A pessoa autorizou o uso da imagem? (s/n): ").strip().lower() != "s":
    raise SystemExit("Sem autorização: nada foi capturado.")

camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # 0 = webcam padrão do Windows
if not camera.isOpened():
    raise SystemExit("Não consegui abrir a webcam. Feche outros apps que a usam.")

print("ESPAÇO = capturar | Q = sair")

while True:
    ok, quadro = camera.read()
    if not ok:
        break

    cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
    rostos = detector.detectMultiScale(
        cinza, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
    )

    exibicao = quadro.copy()  # o 'quadro' original fica limpo para salvar
    for (x, y, w, h) in rostos:
        cv2.rectangle(exibicao, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(exibicao, "ESPACO = capturar | Q = sair", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("Horulince - captura de rosto", exibicao)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla == ord(" "):
        if len(rostos) != 1:
            print(f"Precisa haver exatamente 1 rosto (detectados: {len(rostos)}).")
            continue
        agora = datetime.now()
        arquivo = PASTA_ROSTOS / f"{nome_arquivo}_{agora:%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(str(arquivo), quadro)

        novo = not REGISTRO.exists()
        with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            if novo:
                escritor.writerow(["nome", "arquivo", "data_hora", "autorizado"])
            escritor.writerow([nome, arquivo.name, agora.isoformat(timespec="seconds"), "sim"])
        print(f"Foto salva: {arquivo}")
    elif tecla == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()
