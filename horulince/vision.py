"""Visão carregada somente no processamento; revisão e testes não exigem GPU."""
from pathlib import Path
import os
import shutil
from collections import Counter
from dataclasses import dataclass
import time

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


@dataclass
class PlateRegion:
    image: object
    box: tuple
    method: str
    score: float


def _text_line(gray):
    """Retira molduras e faixa do país usando componentes, sem inventar caracteres."""
    if gray.size == 0:
        return gray
    h, w = gray.shape
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    letters = []
    for x, y, cw, ch, area in stats[1:count]:
        if (max(7, h * .28) <= ch <= h * .95 and 1 <= cw <= w * .23
                and .7 <= ch / max(cw, 1) <= 9 and area >= 3):
            letters.append((int(x), int(y), int(cw), int(ch)))
    best = []
    for _, y, _, ch in letters:
        line = [r for r in letters if abs((r[1]+r[3]/2) - (y+ch/2)) < h * .18 and .55 < r[3]/ch < 1.8]
        if len(line) > len(best):
            best = line
    if not 5 <= len(best) <= 10:
        return gray
    x1 = max(0, min(r[0] for r in best)-2)
    y1 = max(0, min(r[1] for r in best)-1)
    x2 = min(w, max(r[0]+r[2] for r in best)+2)
    y2 = min(h, max(r[1]+r[3] for r in best)+1)
    return gray[y1:y2, x1:x2]


def locate_plate_regions(vehicle, detector=None):
    """Prioriza retângulos claros com texto; tamanho não implica ser uma placa."""
    height, width = vehicle.shape[:2]
    if not height or not width:
        return []
    if detector is not None:
        result = detector(vehicle, conf=.35, verbose=False)[0]
        regions = []
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            region = vehicle[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
            if region.size:
                regions.append(PlateRegion(region, (max(0,x1),max(0,y1),min(width,x2),min(height,y2)), "modelo", float(box.conf.item())))
        return regions[:4]
    gray = cv2.cvtColor(vehicle, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(vehicle, cv2.COLOR_BGR2HSV)
    candidates = []

    def offer(x, y, w, h, score, method):
        ratio = w / max(h, 1)
        fraction = w*h/(width*height)
        if w < 40 or h < 13 or not 1.8 <= ratio <= 6.5 or not .001 <= fraction <= .12 or y < height * .25:
            return
        candidates.append((score, x, y, w, h, method))

    # Uma placa clara pode não formar um contorno Canny fechado. Reunir fundo
    # e espaços entre letras evita selecionar somente grades, faróis e para-choques.
    for threshold in (130, 160, 190, 215):
        mask = ((gray > threshold) & (hsv[:,:,1] < 110)).astype("uint8") * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5,3)))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x,y,w,h = cv2.boundingRect(contour)
            extent = cv2.contourArea(contour) / max(1,w*h)
            if extent < .45:
                continue
            patch = gray[y:y+h,x:x+w]
            dark = float((patch < 110).mean())
            if not .04 <= dark <= .6:
                continue
            # Dimensões e preenchimento são indícios de localização, não confiança OCR.
            score = 2 + extent - abs(w/max(h,1)-3.8)*.1
            offer(x,y,w,h,score,"fundo_claro")

    # Caracteres escuros sobre fundo claro continuam localizáveis quando a placa
    # se mistura à carroceria branca e seu contorno externo não fecha.
    for kernel in ((13,5),(17,7)):
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT,kernel))
        mask = cv2.threshold(blackhat,25,255,cv2.THRESH_BINARY)[1]
        mask = cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(17,3)))
        contours,_ = cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x,y,w,h = cv2.boundingRect(contour)
            patch = gray[y:y+h,x:x+w]
            if patch.size and float((patch>130).mean()) > .25:
                offer(x,y,w,h,4 + y/max(height,1) - abs(w/max(h,1)-3.8)*.1,"caracteres")

    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        patch = gray[y:y+h,x:x+w]
        if patch.size and float((patch > 130).mean()) > .25:
            offer(x,y,w,h,.5 + cv2.contourArea(contour)/max(1,w*h),"contornos")
    candidates.sort(reverse=True)
    selected = []
    for score,x,y,w,h,method in candidates:
        if any((max(0,min(x+w,px+pw)-max(x,px))*max(0,min(y+h,py+ph)-max(y,py)))/max(1,min(w*h,pw*ph)) > .65
               for _,px,py,pw,ph,_ in selected):
            continue
        selected.append((score,x,y,w,h,method))
        if len(selected) == 4:
            break
    return [PlateRegion(vehicle[max(0,y-2):min(height,y+h+2),max(0,x-2):min(width,x+w+2)],
                        (max(0,x-2),max(0,y-2),min(width,x+w+2),min(height,y+h+2)),method,score)
            for score,x,y,w,h,method in selected]


def plate_regions(vehicle, detector=None):
    """Compatibilidade com a interface anterior."""
    return [region.image for region in locate_plate_regions(vehicle, detector)]


def read_plate(vehicle, detector=None, minimum_confidence=55, diagnostics=None):
    """OCR por região/variante. Várias variantes nunca contam como vários quadros."""
    tick = time.perf_counter()
    timed_out = False
    def recognize(image, psm):
        nonlocal timed_out
        try:
            return pytesseract.image_to_data(image,config=f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",output_type=Output.DICT,timeout=3)
        except RuntimeError as error:
            if "timeout" not in str(error).lower():
                raise
            timed_out = True
            return {"text":[]}
    readings = []
    uncertain = []
    regions = locate_plate_regions(vehicle, detector)
    if diagnostics is not None:
        diagnostics.update(status="sem_regiao" if not regions else "sem_leitura_valida", regioes=len(regions))
    prepared = []
    for region in regions:
        gray = _text_line(cv2.cvtColor(region.image, cv2.COLOR_BGR2GRAY))
        scale = min(max(1, 64 / gray.shape[0]),960/gray.shape[1])
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        prepared.append((gray,binary))
    # Duas chamadas para todas as regiões, em linhas separadas. Evita iniciar
    # até oito processos Tesseract para cada veículo e não soma votos por variante.
    import numpy as np
    for variant in range(2) if prepared else ():
        if timed_out:
            break
        width = max(images[variant].shape[1] for images in prepared) + 24
        row_height = max(images[variant].shape[0] for images in prepared) + 32
        batch = np.full((len(prepared)*row_height,width),255,dtype="uint8")
        for index,images in enumerate(prepared):
            image = images[variant]
            batch[index*row_height+12:index*row_height+12+image.shape[0],12:12+image.shape[1]] = image
        data = recognize(batch,6)
        lines = {}
        for i,text in enumerate(data["text"]):
            text = normalize_plate(text)
            if not text:
                continue
            center = float(data["top"][i]) + float(data["height"][i])/2
            number = int(center // row_height)
            if not 0 <= number < len(regions):
                continue
            key = (number,data["block_num"][i],data["par_num"][i],data["line_num"][i])
            lines.setdefault(key,[]).append((int(data["left"][i]),text,float(data["conf"][i])))
        for (number,*_),line in lines.items():
            tokens = [(text,confidence) for _,text,confidence in sorted(line)]
            options = tokens[:]
            if len(tokens) > 1:
                options.append(("".join(t for t, _ in tokens), min(c for _, c in tokens)))
            uncertain.extend((text, confidence, number) for text, confidence in options if valid_plate(text))
            readings.extend((text, confidence, number) for text, confidence in options if valid_plate(text) and confidence >= minimum_confidence)
    if not readings and not timed_out:
        # O modo de bloco pode ignorar uma linha curta junto de regiões ruidosas.
        # Tentar as duas melhores regiões como linhas isoladas, sem baixar limiar.
        for number, images in enumerate(prepared[:2]):
            if timed_out:
                break
            image = cv2.copyMakeBorder(images[0],12,12,12,12,cv2.BORDER_CONSTANT,value=255)
            data = recognize(image,7)
            tokens = [(normalize_plate(t),float(c)) for t,c in zip(data["text"],data["conf"]) if normalize_plate(t)]
            options = tokens[:]
            if len(tokens)>1:
                options.append(("".join(t for t,_ in tokens),min(c for _,c in tokens)))
            uncertain.extend((t,c,number) for t,c in options if valid_plate(t))
            readings.extend((t,c,number) for t,c in options if valid_plate(t) and c>=minimum_confidence)
    plates = {plate for plate, _, _ in readings}
    if timed_out:
        if diagnostics is not None:
            diagnostics.update(status="timeout",duracao_ms=round((time.perf_counter()-tick)*1000,2))
        return None, 0.0
    # Conflito entre regiões/variantes não se transforma em certeza.
    if len(plates) != 1:
        if diagnostics is not None:
            diagnostics.update(status="conflito" if len(plates)>1 else "baixa_confianca" if uncertain else diagnostics["status"],
                               duracao_ms=round((time.perf_counter()-tick)*1000,2))
            if uncertain:
                text, confidence, _ = max(uncertain,key=lambda reading: reading[1])
                diagnostics.update(candidata=text,confianca=confidence)
        return None, 0.0
    text, confidence, index = max(readings, key=lambda reading: reading[1])
    if diagnostics is not None:
        diagnostics.update(status="leitura_valida",candidata=text,confianca=confidence,
                           regiao=list(regions[index].box),metodo=regions[index].method,
                           duracao_ms=round((time.perf_counter()-tick)*1000,2))
    return text, confidence
