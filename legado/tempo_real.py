import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

from veiculos import VEICULOS, cores_do_veiculo, pontuar, ler_placa, placas_parecidas

parser = argparse.ArgumentParser()
parser.add_argument("--fonte", default="0",
                    help="0 = webcam; 1 = outra câmera; ou URL (http://IP:8080/video, rtsp://...)")
parser.add_argument("--tipo", default="carro")
parser.add_argument("--cor", default="branco")
parser.add_argument("--placa", default="", help="placa procurada (opcional), ex: ABC1D23")
parser.add_argument("--limiar", type=float, default=0.6)
args = parser.parse_args()

alvo = {"tipo": args.tipo, "cor": args.cor}
placa_alvo = args.placa.upper().replace("-", "").strip()
fonte = int(args.fonte) if args.fonte.isdigit() else args.fonte

PROCESSA_A_CADA = 3          # detecta 1 de cada 3 quadros
OCR_A_CADA = 2               # lê placas a cada 2 ciclos de detecção
MAX_OCR_POR_CICLO = 2        # no máximo 2 veículos lidos por vez
LARGURA_MINIMA = 80
LARGURA_MINIMA_OCR = 120     # só tenta ler placa de veículos grandes/próximos
VALIDADE_PLACA = 2.5         # segundos que a placa lida continua na tela
PAUSA_ENTRE_SALVAMENTOS = 2.0

PASTA = Path("dados/tempo_real")
PASTA.mkdir(parents=True, exist_ok=True)
REGISTRO = PASTA / "registro_placas.csv"

if isinstance(fonte, int):
    camera = cv2.VideoCapture(fonte, cv2.CAP_DSHOW)
else:
    camera = cv2.VideoCapture(fonte)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
if not camera.isOpened():
    raise SystemExit(f"Não consegui abrir a fonte: {fonte}")

modelo = YOLO("yolov8n.pt")
print(f"Monitorando. Alvo: {alvo} | placa: {placa_alvo or '(qualquer)'} | Q para sair")

n = ciclo = 0
deteccoes = []
placas_recentes = []         # (cx, cy, placa, instante)
ultimo_salvo = 0.0
t_anterior = time.time()


def placa_recente(cx, cy, agora):
    for px, py, placa, t in reversed(placas_recentes):
        if agora - t < VALIDADE_PLACA and abs(px - cx) < 100 and abs(py - cy) < 100:
            return placa
    return None


while True:
    ok, quadro = camera.read()
    if not ok:
        print("Perdi a imagem da fonte (rede caiu ou câmera ocupada).")
        break
    n += 1

    if n % PROCESSA_A_CADA == 0:
        ciclo += 1
        fazer_ocr = ciclo % OCR_A_CADA == 0
        ocr_feitos = 0
        agora = time.time()
        placas_recentes[:] = [p for p in placas_recentes if agora - p[3] < VALIDADE_PLACA]
        deteccoes = []

        resultado = modelo(quadro, classes=list(VEICULOS), conf=0.4,
                           imgsz=480, verbose=False)[0]
        for caixa in resultado.boxes:
            x1, y1, x2, y2 = map(int, caixa.xyxy[0])
            largura = x2 - x1
            if largura < LARGURA_MINIMA:
                continue
            recorte = quadro[y1:y2, x1:x2]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            tipo = VEICULOS[int(caixa.cls)]
            cores = cores_do_veiculo(recorte)
            cor_nome = cores[0][0] if cores else "?"

            placa = None
            if fazer_ocr and largura >= LARGURA_MINIMA_OCR and ocr_feitos < MAX_OCR_POR_CICLO:
                ocr_feitos += 1
                placa = ler_placa(recorte)
                if placa:
                    placas_recentes.append((cx, cy, placa, agora))
            if placa is None:
                placa = placa_recente(cx, cy, agora)

            nota = pontuar(tipo, cores, alvo)
            placa_confere = bool(placa and placa_alvo and placas_parecidas(placa, placa_alvo))
            if placa_confere:
                nota = 1.0
            deteccoes.append((x1, y1, x2, y2, tipo, cor_nome, placa, nota, placa_confere))

            if nota >= args.limiar and agora - ultimo_salvo > PAUSA_ENTRE_SALVAMENTOS:
                ultimo_salvo = agora
                momento = datetime.now()
                arquivo = PASTA / f"{momento:%Y%m%d_%H%M%S}_nota{nota:.2f}.jpg"
                cv2.imwrite(str(arquivo), recorte)
                novo = not REGISTRO.exists()
                with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if novo:
                        w.writerow(["data_hora", "tipo", "cor", "placa", "nota", "arquivo"])
                    w.writerow([momento.isoformat(timespec="seconds"), tipo, cor_nome,
                                placa or "", f"{nota:.2f}", arquivo.name])
                print(f"CANDIDATO {momento:%H:%M:%S}: {tipo} {cor_nome} "
                      f"placa {placa or '-'} nota {nota:.2f}")

    for x1, y1, x2, y2, tipo, cor_nome, placa, nota, confere in deteccoes:
        if confere:
            cor_caixa, espessura = (0, 0, 255), 4       # vermelho: placa confere
        elif nota >= args.limiar:
            cor_caixa, espessura = (0, 255, 0), 3        # verde: candidato
        else:
            cor_caixa, espessura = (160, 160, 160), 1
        cv2.rectangle(quadro, (x1, y1), (x2, y2), cor_caixa, espessura)
        texto = f"{tipo} {cor_nome} {placa or ''} {nota:.2f}"
        cv2.putText(quadro, texto, (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_caixa, 2)

    agora = time.time()
    fps = 1 / max(agora - t_anterior, 1e-6)
    t_anterior = agora
    cv2.putText(quadro, f"FPS {fps:.0f} | alvo: {alvo['tipo']} {alvo['cor']} {placa_alvo}",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("Horulince - tempo real", quadro)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()
