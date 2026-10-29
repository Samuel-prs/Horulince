"""Adaptadores do legado: detecção/captura, sem identificação de pessoas.

Não importa os scripts interativos antigos nem altera as regras do pipeline.
"""
from datetime import datetime
import json
import math
from pathlib import Path
import time
import uuid

from .storage import now


SCHEMA = """CREATE TABLE IF NOT EXISTS demo_runs (
    id TEXT PRIMARY KEY, mode TEXT NOT NULL, source TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT, state TEXT NOT NULL,
    configuration TEXT NOT NULL, summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS demo_events (
    id TEXT PRIMARY KEY, run TEXT NOT NULL REFERENCES demo_runs(id),
    kind TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
    video_seconds REAL NOT NULL, image TEXT, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_demo_events_run ON demo_events(run);
CREATE INDEX IF NOT EXISTS idx_demo_events_created ON demo_events(created_at);
"""


class DemoArchive:
    def __init__(self, store):
        self.store = store
        self.images = store.path.parent / "demonstracoes" / "imagens"
        with store.connect() as db:
            db.executescript(SCHEMA)

    def begin(self, mode, source, configuration):
        identifier = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute("INSERT INTO demo_runs VALUES(?,?,?,?,NULL,?,?,?)",
                       (identifier, mode, source, now(), "executando", json.dumps(configuration, ensure_ascii=False), "{}"))
        return identifier

    def finish(self, identifier, summary):
        with self.store.connect() as db:
            db.execute("UPDATE demo_runs SET finished_at=?,state=?,summary=? WHERE id=?",
                       (now(), summary["estado_execucao"], json.dumps(summary, ensure_ascii=False), identifier))

    def event(self, run, kind, source, seconds, payload, image=None):
        identifier = uuid.uuid4().hex
        path = None
        try:
            if image is not None:
                import cv2
                self.images.mkdir(parents=True, exist_ok=True)
                path = self.images / f"{identifier}.jpg"
                if not cv2.imwrite(str(path), image):
                    raise OSError("Não foi possível salvar a captura da demonstração")
            with self.store.connect() as db:
                db.execute("INSERT INTO demo_events VALUES(?,?,?,?,?,?,?,?)",
                           (identifier, run, kind, source, now(), seconds, str(path) if path else None,
                            json.dumps(payload, ensure_ascii=False)))
        except Exception:
            if path:
                path.unlink(missing_ok=True)
            raise
        return identifier

    def runs(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM demo_runs ORDER BY started_at DESC LIMIT 100").fetchall()
        return [dict(r) | {"summary": json.loads(r["summary"]), "configuration": json.loads(r["configuration"])} for r in rows]

    def query(self, filters, *, export=False):
        """Consulta unificada e paginada; parâmetros nunca viram caminhos/SQL."""
        try:
            limit = int(filters.get("limit", 30))
            offset = int(filters.get("offset", 0))
        except (ValueError, TypeError):
            raise ValueError("Paginação inválida") from None
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("Paginação fora do limite")
        clauses, values = [], []
        for field in ("kind", "source", "run", "id"):
            if filters.get(field):
                clauses.append(f"{field} = ?")
                values.append(str(filters[field]))
        for key, op in (("since", ">="), ("until", "<=")):
            if filters.get(key):
                value = str(filters[key])
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("Data inválida: use AAAA-MM-DD") from None
                clauses.append(f"substr(created_at,1,10) {op} ?")
                values.append(value)
        if filters.get("q"):
            clauses.append("(payload LIKE ? OR source LIKE ? OR run LIKE ?)")
            values.extend(["%" + str(filters["q"])[:200] + "%"] * 3)
        if filters.get("images") == "1":
            clauses.append("image IS NOT NULL")
        combined = """SELECT 'demo:' || id AS id, run, kind, source, created_at,
                             video_seconds, image, payload, 'demonstracao' AS category
                      FROM demo_events
                      UNION ALL
                      SELECT 'alert:' || id, run, 'alerta_veiculo', source, created_at,
                             video_seconds, evidence, payload, state FROM alerts
                      UNION ALL
                      SELECT 'audit:' || audit.seq, alerts.run, 'revisao_alerta', alerts.source,
                             audit.at, alerts.video_seconds, NULL,
                             json_object('operador',audit.actor,'acao',audit.action,'justificativa',audit.reason),
                             'auditoria'
                      FROM audit JOIN alerts ON audit.alert_id=alerts.id"""
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = "SELECT * FROM (" + combined + ")" + where
        with self.store.connect() as db:
            total = db.execute("SELECT count(*) FROM (" + combined + ")" + where, values).fetchone()[0]
            ordered = sql + " ORDER BY created_at DESC, id DESC"
            rows = db.execute(ordered if export else ordered + " LIMIT ? OFFSET ?",
                              values if export else [*values, limit, offset]).fetchall()
            if export:
                total = len(rows)
        items = []
        for row in rows:
            item = dict(row)
            item["has_image"] = bool(item.pop("image"))
            item["payload"] = json.loads(item["payload"])
            items.append(item)
        return {"items": items, "total": total, "offset": 0 if export else offset, "limit": total if export else limit}

    def image_path(self, identifier):
        prefix, _, key = identifier.partition(":")
        with self.store.connect() as db:
            if prefix == "demo":
                row = db.execute("SELECT image FROM demo_events WHERE id=?", (key,)).fetchone()
                root = self.images.resolve()
            elif prefix == "alert":
                row = db.execute("SELECT evidence FROM alerts WHERE id=?", (key,)).fetchone()
                root = self.store.evidence_dir.resolve()
            else:
                return None
        if row and row[0]:
            path = Path(row[0]).resolve()
            if path.is_relative_to(root) and path.is_file():
                return path
        return None


def run_demo(archive, job, *, mode, source, origin, max_frames=300, every=1,
             authorized=False, model_path=None, detector=None, capture_factory=None):
    """Mantém a câmera no worker; captura manual usa apenas o quadro atual."""
    if mode not in {"facial", "veiculos"}:
        raise ValueError("Demonstração inválida")
    if mode == "facial" and authorized is not True:
        raise ValueError("Confirme a autorização de uso das imagens para a demonstração facial")
    import cv2
    from .sources import open_source, is_network
    from .core import VEHICLES
    from .vision import vehicle_colors

    run_id = archive.begin(mode, origin, {"authorized": authorized, "every": every, "max_frames": max_frames,
                                         "model": Path(model_path).name if model_path else "Haar Cascade OpenCV"})
    capture = None
    frame = processed = detected = saved = 0
    total_ms = 0.0
    failure = None
    last_saved = -math.inf
    live_source = int(source) if source.isdigit() else source
    live = isinstance(live_source, int) or is_network(live_source)
    started = time.monotonic()
    try:
        job.progress({"execucao": run_id, "fase": "conectando", "modo_demo": mode})
        if detector is None:
            if mode == "facial":
                detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                if detector.empty():
                    raise RuntimeError("Detector facial OpenCV indisponível")
            else:
                from ultralytics import YOLO
                if not model_path or not Path(model_path).is_file():
                    raise ValueError("Modelo local de veículos não encontrado")
                detector = YOLO(str(model_path))
        capture = (capture_factory or open_source)(live_source)
        if not capture.isOpened():
            raise RuntimeError("Não foi possível abrir a fonte da demonstração")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not 0 < fps < 1000:
            fps = 30.0
        while not max_frames or frame < max_frames:
            if job.stop_event.is_set():
                break
            tick = time.perf_counter()
            ok, image = capture.read()
            if job.stop_event.is_set():
                break
            if not ok:
                if live:
                    raise RuntimeError("A fonte deixou de fornecer imagens atuais")
                break
            frame += 1
            seconds = time.monotonic() - started if live else (frame - 1) / fps
            if frame % every:
                continue
            output = image.copy()
            results = []
            capture_note = None
            if mode == "facial":
                faces = detector.detectMultiScale(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), scaleFactor=1.1,
                                                   minNeighbors=5, minSize=(100, 100))
                for x, y, w, h in faces:
                    box = [int(x), int(y), int(x + w), int(y + h)]
                    results.append({"box": box, "resultado": "rosto_detectado", "identidade": "nao_analisada", "emocoes": "nao_suportadas"})
                    cv2.rectangle(output, (int(x), int(y)), (int(x+w), int(y+h)), (90, 200, 170), 2)
                if job.capture_requested.is_set():
                    job.capture_requested.clear()
                    if len(results) == 1 and saved < 200:
                        archive.event(run_id, "captura_facial", origin, seconds,
                                      {"quadro": frame, "authorized": True, "deteccoes": results}, image)
                        saved += 1
                        capture_note = "Captura autorizada salva no acervo"
                    else:
                        capture_note = "Captura recusada: é necessário exatamente 1 rosto e menos de 200 imagens salvas"
                archive.event(run_id, "deteccao_facial", origin, seconds, {"quadro": frame, "deteccoes": results, "rostos": len(results)})
            else:
                prediction = detector(image, classes=list(VEHICLES), conf=.4, imgsz=480, verbose=False)[0]
                height, width = image.shape[:2]
                save_cycle = seconds - last_saved >= 2
                for box in prediction.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    x1, y1, x2, y2 = max(0,x1), max(0,y1), min(width,x2), min(height,y2)
                    if x2-x1 < 120 or y2 <= y1:
                        continue
                    crop = image[y1:y2, x1:x2]
                    result = {"tipo": VEHICLES[int(box.cls.item())], "cores": vehicle_colors(crop),
                              "confianca_deteccao": float(box.conf.item()), "box": [x1,y1,x2,y2], "quadro": frame,
                              "nota": "Extração demonstrativa; não compara alvos nem realiza OCR"}
                    save_image = save_cycle and saved < 200
                    archive.event(run_id, "deteccao_veiculo", origin, seconds, result, crop if save_image else None)
                    saved += int(save_image)
                    results.append(result)
                    cv2.rectangle(output, (x1,y1), (x2,y2), (70,180,230), 2)
                    cv2.putText(output, result["tipo"], (x1,max(20,y1-5)), cv2.FONT_HERSHEY_SIMPLEX,.6,(70,180,230),2)
                if save_cycle and results:
                    last_saved = seconds
                # Mesmo quadros sem veículos deixam um evento consultável.
                if not results:
                    archive.event(run_id, "deteccao_veiculo", origin, seconds, {"quadro": frame, "deteccoes": [], "veiculos": 0})
            processed += 1
            detected += len(results)
            total_ms += (time.perf_counter() - tick) * 1000
            job.image(output)
            progress = {"execucao": run_id, "fase": "demonstrando", "modo_demo": mode, "quadros_lidos": frame,
                        "quadros_processados": processed, "instante_video": round(seconds,3), "deteccoes": results,
                        "rostos_no_quadro": len(results) if mode == "facial" else None,
                        "veiculos_no_quadro": len(results) if mode == "veiculos" else None,
                        "deteccoes_acumuladas": detected, "imagens_salvas": saved,
                        "processamento_medio_ms": round(total_ms/processed,2),
                        "fps_processamento": round(processed/max(time.monotonic()-started,.001),2)}
            if capture_note:
                progress["captura_status"] = capture_note
            job.progress(progress)
            if not live:
                job.stop_event.wait(max(0, frame/fps - (time.monotonic()-started)))
        if frame == 0 and not job.stop_event.is_set():
            raise RuntimeError("A fonte não forneceu nenhum quadro para análise")
    except Exception as error:
        failure = error
    finally:
        if capture is not None:
            capture.release()
        job.capture_requested.clear()
        summary = {"execucao": run_id, "origem": origin, "modo": mode, "quadros_lidos": frame,
                   "quadros_processados": processed, "deteccoes_acumuladas": detected, "imagens_salvas": saved,
                   "processamento_medio_ms": round(total_ms/processed,2) if processed else None,
                   "fps_processamento": round(processed/max(time.monotonic()-started,.001),2),
                   "estado_execucao": "erro" if failure else "interrompida" if job.stop_event.is_set() else "concluida",
                   "nota": "Contagens por quadro; não representam indivíduos ou veículos únicos."}
        archive.finish(run_id, summary)
    if failure:
        raise failure
    return summary
