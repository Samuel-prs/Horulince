"""Regras sem dependências de visão; notas heurísticas não são probabilidades."""
from collections import Counter, deque
from dataclasses import dataclass, field
import re

PLATE = re.compile(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}")
VEHICLES = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}
COLORS = {"preto", "branco", "cinza/prata", "vermelho", "laranja", "amarelo", "verde", "azul", "roxo/rosa"}


def normalize_plate(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def valid_plate(value):
    return PLATE.fullmatch(value) is not None


def plate_relation(observed, target):
    a, b = normalize_plate(observed), normalize_plate(target)
    if not valid_plate(a) or not valid_plate(b):
        return "invalida"
    differences = sum(x != y for x, y in zip(a, b))
    return "exata" if differences == 0 else "aproximada" if differences == 1 else "diferente"


def color_name(h, s, v):
    if v < 50:
        return "preto"
    if s < 40:
        return "branco" if v > 190 else "cinza/prata"
    for limit, color in [(10, "vermelho"), (22, "laranja"), (35, "amarelo"), (85, "verde"), (130, "azul"), (170, "roxo/rosa")]:
        if h < limit:
            return color
    return "vermelho"


def attribute_score(kind, colors, target):
    """Compatibilidade de regras, não confiança estatística."""
    kind_score = float(kind == target.get("tipo"))
    color_score = 0.0
    for position, (color, _) in enumerate(colors):
        if color == target.get("cor"):
            color_score = max(color_score, 1.0 if position == 0 else 0.6)
        elif {color, target.get("cor")} <= {"branco", "cinza/prata"}:
            color_score = max(color_score, 0.5 if position == 0 else 0.3)
    return round(0.4 * kind_score + 0.6 * color_score, 4)


@dataclass
class PlateVotes:
    minimum: int = 3
    window: int = 8
    ratio: float = 0.7
    readings: deque = field(default_factory=deque)

    def add(self, plate, confidence):
        reading = plate if plate and valid_plate(plate) else None
        # Sem leitura anterior não há hipótese para confirmar ou expirar.
        # Falhas antes de a placa ficar visível não penalizam a primeira hipótese.
        if not any(p for p, _ in self.readings):
            self.readings.clear()
        if reading is None and not self.readings:
            return
        # None também ocupa um lugar na janela: leituras antigas perdem validade.
        self.readings.append((reading, confidence))
        while len(self.readings) > self.window:
            self.readings.popleft()

    def consensus(self):
        counts = Counter(p for p, _ in self.readings if p)
        if not counts:
            return None
        ordered = counts.most_common()
        plate, count = ordered[0]
        if len(ordered) > 1 and ordered[1][1] == count:
            return None
        if count < self.minimum or count / len(self.readings) < self.ratio:
            return None
        confidence = sum(c for p, c in self.readings if p == plate) / count
        return {"placa": plate, "leituras": count, "tentativas": len(self.readings), "confianca_ocr_media": round(confidence, 2)}


def iou(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = width * height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    box: tuple
    kind: str
    last_frame: int
    votes: PlateVotes = field(default_factory=PlateVotes)
    hits: int = 1
    last_ocr_frame: int = -1
    last_ocr_seconds: float = -1
    ocr_diagnostics: dict = field(default_factory=dict)


class Tracker:
    """IoU conservador: associa só pares únicos, sem reaproveitar IDs expirados.

    Não resolve reidentificação ou oclusões prolongadas. Ambiguidade cria novo ID
    e descarta o histórico de OCR para evitar misturar placas.
    """

    def __init__(self, max_age=15, threshold=0.3):
        self.max_age = max_age
        self.threshold = threshold
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, frame):
        self.tracks = {k: t for k, t in self.tracks.items() if frame - t.last_frame <= self.max_age}
        candidates = {}
        reverse = Counter()
        for i, detection in enumerate(detections):
            choices = [t.id for t in self.tracks.values() if t.kind == detection["tipo"] and iou(t.box, detection["box"]) >= self.threshold]
            candidates[i] = choices
            reverse.update(choices)
        result = []
        reused = set()
        for i, detection in enumerate(detections):
            choices = candidates[i]
            if len(choices) == 1 and reverse[choices[0]] == 1:
                track = self.tracks[choices[0]]
                track.box = detection["box"]
                track.last_frame = frame
                track.hits += 1
                reused.add(track.id)
            else:
                track = Track(self.next_id, detection["box"], detection["tipo"], frame)
                self.next_id += 1
                self.tracks[track.id] = track
            result.append(track)
        # Remover históricos envolvidos em associação ambígua.
        ambiguous = {tid for choices in candidates.values() for tid in choices if tid not in reused}
        for tid in ambiguous:
            self.tracks.pop(tid, None)
        return result


def candidate(kind, colors, consensus, target, threshold=0.7):
    score = attribute_score(kind, colors, target)
    wanted = target.get("placa", "")
    if wanted:
        if not consensus:
            return None
        relation = plate_relation(consensus["placa"], wanted)
        if relation not in {"exata", "aproximada"}:
            return None
        return {"correspondencia": relation, "compatibilidade_caracteristicas": score, "placa": consensus["placa"], "consolidacao": consensus}
    if kind != target.get("tipo") or score < threshold:
        return None
    return {"correspondencia": "caracteristicas", "compatibilidade_caracteristicas": score, "placa": consensus["placa"] if consensus else None, "consolidacao": consensus}
