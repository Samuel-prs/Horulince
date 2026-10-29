"""Visão carregada somente no processamento; revisão e testes não exigem GPU."""
from pathlib import Path
import os
import shutil
from collections import Counter

import cv2
import pytesseract
from pytesseract import Output

from .core import color_name, normalize_plate, valid_plate


def configure_tesseract(explicit=None):
    executable = explicit or os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if not executable:
        standard = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        executable = str(standard) if standard.is_file() else None
    if not executable:
        raise RuntimeError("Tesseract não encontrado. Use --tesseract ou TESSERACT_CMD.")
    pytesseract.pytesseract.tesseract_cmd = executable
    pytesseract.get_tesseract_version()


def vehicle_colors(crop):
    height, width = crop.shape[:2]
    center = crop[int(height * .4):int(height * .8), int(width * .25):int(width * .75)]
    if not center.size:
        return []
    hsv = cv2.cvtColor(cv2.resize(center, (32, 32)), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    counts = Counter(color_name(int(h), int(s), int(v)) for h, s, v in hsv)
    return [(color, count / len(hsv)) for color, count in counts.most_common(2)]


def plate_regions(vehicle, detector=None):
    """Localiza regiões de placa. Contornos são fallback, não detector treinado."""
    height, width = vehicle.shape[:2]
    if detector is not None:
        result = detector(vehicle, conf=.35, verbose=False)[0]
        regions = []
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            region = vehicle[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
            if region.size:
                regions.append(region)
        return regions[:4]
    # Não presumir que toda a metade inferior contém apenas uma placa.
    gray = cv2.cvtColor(vehicle, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        ratio = w / max(h, 1)
        fraction = (w * h) / (width * height)
        if w >= 35 and h >= 10 and 1.8 <= ratio <= 5.8 and .003 <= fraction <= .18 and y > height * .25:
            if any(abs(x - px) < 5 and abs(y - py) < 5 and abs(w - pw) < 10 for _, px, py, pw, _ in candidates):
                continue
            candidates.append((w * h, x, y, w, h))
    candidates.sort(reverse=True)
    return [vehicle[max(0, y-2):min(height, y+h+2), max(0, x-2):min(width, x+w+2)] for _, x, y, w, h in candidates[:4]]


def read_plate(vehicle, detector=None, minimum_confidence=55):
    """OCR por região/variante. Várias variantes nunca contam como vários quadros."""
    readings = []
    for region in plate_regions(vehicle, detector):
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        scale = max(1, 80 / gray.shape[0])
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        for image in (enhanced, binary):
            data = pytesseract.image_to_data(image, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", output_type=Output.DICT, timeout=3)
            tokens = [(normalize_plate(text), float(conf)) for text, conf in zip(data["text"], data["conf"]) if normalize_plate(text)]
            options = tokens[:]
            if len(tokens) > 1:
                options.append(("".join(t for t, _ in tokens), min(c for _, c in tokens)))
            readings.extend((text, confidence) for text, confidence in options if valid_plate(text) and confidence >= minimum_confidence)
    plates = {plate for plate, _ in readings}
    # Conflito entre regiões/variantes não se transforma em certeza.
    if len(plates) != 1:
        return None, 0.0
    return max(readings, key=lambda reading: reading[1])
