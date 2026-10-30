from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

CAMINHO_VIDEO = "videos/transito1.mp4"
VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}
LARGURA_MINIMA = 120
A_CADA = 10  # analisa 1 quadro a cada 10

PASTA = Path("dados/recortes")
PASTA.mkdir(parents=True, exist_ok=True)


def nome_cor(h, s, v):
    """H em 0-179 (padrão do OpenCV), S e V em 0-255."""
    if v < 50:
        return "preto"
    if s < 40:
        return "branco" if v > 190 else "cinza/prata"
    if h < 10 or h >= 170:
        return "vermelho"
    if h < 22:
        return "laranja"
    if h < 35:
        return "amarelo"
    if h < 85:
        return "verde"
    if h < 130:
        return "azul"
    return "roxo/rosa"


def cor_do_veiculo(recorte):
    alt, larg = recorte.shape[:2]
    # região central do corpo, evitando vidros, rodas e fundo
    miolo = recorte[int(alt * 0.4):int(alt * 0.8), int(larg * 0.25):int(larg * 0.75)]
    if miolo.size == 0:
        return "?"
    miolo = cv2.resize(miolo, (32, 32))
    hsv = cv2.cvtColor(miolo, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    votos = Counter(nome_cor(int(h), int(s), int(v)) for h, s, v in hsv)
    return votos.most_common(1)[0][0]


modelo = YOLO("yolov8n.pt")
video = cv2.VideoCapture(CAMINHO_VIDEO)
n = 0
salvos = 0

while True:
    ok, quadro = video.read()
    if not ok:
        break
    n += 1
    if n % A_CADA:
        continue

    resultado = modelo(quadro, classes=list(VEICULOS), conf=0.4, verbose=False)[0]
    for i, caixa in enumerate(resultado.boxes):
        x1, y1, x2, y2 = map(int, caixa.xyxy[0])
        if x2 - x1 < LARGURA_MINIMA:
            continue
        recorte = quadro[y1:y2, x1:x2]
        tipo = VEICULOS[int(caixa.cls)]
        cor = cor_do_veiculo(recorte)
        arquivo = PASTA / f"q{n:05d}_{i}_{tipo}_{cor.replace('/', '-')}.jpg"
        cv2.imwrite(str(arquivo), recorte)
        salvos += 1
        print(f"Quadro {n}: {tipo}, cor {cor}")

video.release()
print(f"Pronto! {salvos} recortes salvos em {PASTA}")
