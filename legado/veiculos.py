from collections import Counter
import re
import pytesseract

import cv2

VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}
COMPATIVEIS = [{"branco", "cinza/prata"}]


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
    alt, larg = recorte.shape[:2]
    miolo = recorte[int(alt * 0.4):int(alt * 0.8), int(larg * 0.25):int(larg * 0.75)]
    if miolo.size == 0:
        return []
    miolo = cv2.resize(miolo, (32, 32))
    hsv = cv2.cvtColor(miolo, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    votos = Counter(nome_cor(int(h), int(s), int(v)) for h, s, v in hsv)
    total = sum(votos.values())
    return [(cor, n / total) for cor, n in votos.most_common(2)]


def pontuar(tipo, cores, alvo):
    ponto_tipo = 1.0 if tipo == alvo["tipo"] else 0.0
    ponto_cor = 0.0
    for pos, (cor, _) in enumerate(cores):
        if cor == alvo["cor"]:
            ponto_cor = max(ponto_cor, 1.0 if pos == 0 else 0.6)
        elif any({cor, alvo["cor"]} <= g for g in COMPATIVEIS):
            ponto_cor = max(ponto_cor, 0.5 if pos == 0 else 0.3)
    return 0.4 * ponto_tipo + 0.6 * ponto_cor
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
PADRAO_PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


def ler_placa(recorte_veiculo):
    """Tenta ler a placa na metade de baixo do veículo. Devolve texto ou None."""
    alt = recorte_veiculo.shape[0]
    regiao = recorte_veiculo[alt // 2:, :]
    cinza = cv2.cvtColor(regiao, cv2.COLOR_BGR2GRAY)
    cinza = cv2.resize(cinza, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = "--psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    texto = pytesseract.image_to_string(binaria, config=config)
    for pedaco in texto.split():
        limpo = re.sub(r"[^A-Z0-9]", "", pedaco.upper())
        if PADRAO_PLACA.match(limpo):
            return limpo
    return None


def placas_parecidas(a, b):
    """Iguais, ou diferentes em no máximo 1 caractere (tolera erro do OCR)."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1
