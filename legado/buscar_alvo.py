from collections import Counter
from pathlib import Path

import cv2
from ultralytics import YOLO

# ---- Descrição do veículo procurado (edite aqui) ----
ALVO = {"tipo": "carro", "cor": "branco"}
LIMIAR = 0.6               # pontuação mínima para virar candidato
COMPATIVEIS = [{"branco", "cinza/prata"}]   # cores que se confundem

CAMINHO_VIDEO = "videos/transito1.mp4"
VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}
LARGURA_MINIMA = 100
A_CADA = 5

PASTA = Path("dados/candidatos")
PASTA.mkdir(parents=True, exist_ok=True)


def nome_cor(h, s, v):
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


def cores_do_veiculo(recorte):
    """Devolve as 2 cores mais prováveis: [(cor, fração), ...]"""
    alt, larg = recorte.shape[:2]
    miolo = recorte[int(alt * 0.4):int(alt * 0.8), int(larg * 0.25):int(larg * 0.75)]
    if miolo.size == 0:
        return []
    miolo = cv2.resize(miolo, (32, 32))
    hsv = cv2.cvtColor(miolo, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    votos = Counter(nome_cor(int(h), int(s), int(v)) for h, s, v in hsv)
    total = sum(votos.values())
    return [(cor, n / total) for cor, n in votos.most_common(2)]


def pontuar(tipo, cores):
    ponto_tipo = 1.0 if tipo == ALVO["tipo"] else 0.0
    ponto_cor = 0.0
    for pos, (cor, _) in enumerate(cores):
        if cor == ALVO["cor"]:
            ponto_cor = max(ponto_cor, 1.0 if pos == 0 else 0.6)
        elif any({cor, ALVO["cor"]} <= g for g in COMPATIVEIS):
            ponto_cor = max(ponto_cor, 0.5 if pos == 0 else 0.3)
    return 0.4 * ponto_tipo + 0.6 * ponto_cor


modelo = YOLO("yolov8n.pt")
video = cv2.VideoCapture(CAMINHO_VIDEO)
fps = video.get(cv2.CAP_PROP_FPS) or 30
n = 0
candidatos = []

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
        cores = cores_do_veiculo(recorte)
        nota = pontuar(tipo, cores)
        if nota >= LIMIAR:
            segundos = n / fps
            arquivo = PASTA / f"nota{nota:.2f}_q{n:05d}_{i}.jpg"
            cv2.imwrite(str(arquivo), recorte)
            candidatos.append((nota, segundos, tipo, cores[0][0], arquivo.name))

video.release()

candidatos.sort(reverse=True)
print(f"\nAlvo: {ALVO}")
print(f"{len(candidatos)} candidatos (nota >= {LIMIAR}). Melhores:")
for nota, seg, tipo, cor, nome in candidatos[:10]:
    print(f"  nota {nota:.2f} | {seg:6.1f}s | {tipo} {cor} | {nome}")
