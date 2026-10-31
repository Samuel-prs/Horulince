"""Painel local integrado ao pipeline. Inicie com python -m horulince painel."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import secrets
import shutil
import sqlite3
import threading
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import uuid

from .core import COLORS, VEHICLES
from .evaluation import evaluate
from .pipeline import ROOT, load_targets
from .sources import validate_phone_url
from .storage import AlertStore, ReviewConflict
from .demonstration import DemoArchive, run_demo

WEB = Path(__file__).parent / "web"


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def number(value, name, minimum, maximum, integer=True):
    if isinstance(value, bool):
        raise ValueError(f"{name}: informe um número válido")
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name}: informe um número válido") from None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum or (integer and not parsed.is_integer()):
        raise ValueError(f"{name}: use um valor entre {minimum} e {maximum}")
    return int(parsed) if integer else parsed


class Jobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.frame = None
        self.capture_requested = threading.Event()
        self.state = {"status": "ocioso", "message": "Pronto para um novo teste", "progress": {}}

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def progress(self, progress):
        with self.lock:
            self.state["progress"].update(progress)
            if self.state["status"] != "parando":
                self.state["status"] = "executando"
                self.state["message"] = {"conectando": "Conectando à fonte de vídeo", "analisando": "Análise em andamento — confira os candidatos na central de alertas", "testando_conexao": "Recebendo imagem sem executar a IA", "demonstrando": "Demonstração em andamento; resultados disponíveis no acervo"}.get(progress.get("fase"), "Teste em andamento")

    def image(self, image):
        import cv2
        h, w = image.shape[:2]
        if w > 1280:
            image = cv2.resize(image, (1280, max(1, int(h * 1280 / w))))
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if ok:
            with self.lock:
                self.frame = encoded.tobytes()

    def start(self, action, *, mode, source_label):
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise ValueError("Já existe um teste em andamento. Aguarde ou pare a execução.")
            self.stop_event = threading.Event()
            self.frame = None
            self.capture_requested.clear()
            self.state = {"status": "iniciando", "mode": mode, "source": source_label, "started_at": timestamp(), "message": "Preparando a fonte e o processamento", "progress": {}}

            def work():
                try:
                    result = action(self)
                    with self.lock:
                        interrupted = self.stop_event.is_set() or result.get("estado_execucao") == "interrompida"
                        self.state.update(status="interrompida" if interrupted else "concluida", message="Teste interrompido pelo operador" if interrupted else "Teste concluído", result=result, finished_at=timestamp())
                except Exception as error:
                    with self.lock:
                        # Não incluir URLs/credenciais retornadas por backends de rede.
                        message = str(error)
                        if "://" in message:
                            message = "Falha na conexão de vídeo. Verifique a URL e as permissões de rede local."
                        self.state.update(status="erro", message=message[:500], finished_at=timestamp())

            self.thread = threading.Thread(target=work, daemon=True, name="horulince-analysis")
            self.thread.start()

    def stop(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                raise ValueError("Nenhum teste está em andamento")
            self.stop_event.set()
            self.state.update(status="parando", message="Parada solicitada; aguardando a operação atual liberar a câmera")


class Dashboard:
    def __init__(self, database):
        self.store = AlertStore(database)
        self.archive = DemoArchive(self.store)
        self.folder = self.store.path.parent / "painel"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.uploads = self.folder / "uploads"
        self.uploads.mkdir(exist_ok=True)
        self.evaluations = self.folder / "avaliacoes"
        self.evaluations.mkdir(exist_ok=True)
        self.jobs = Jobs()
        self.token = secrets.token_urlsafe(32)
        self.targets_file = self.folder / "alvos.json"

    def targets(self):
        if self.targets_file.is_file():
            return json.loads(self.targets_file.read_text(encoding="utf-8"))
        return [{"id": "alvo_teste_01", "tipo": "carro", "cor": "branco", "placa": ""}]

    def save_targets(self, data):
        # Validar e normalizar com as mesmas regras do CLI.
        if not isinstance(data, list):
            raise ValueError("Informe uma lista de alvos")
        targets = load_targets(SimpleNamespace(targets=data))
        self.targets_file.write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")
        return targets

    def videos(self):
        result = []
        for prefix, folder in (("video", ROOT / "videos"), ("upload", self.uploads)):
            for path in sorted(folder.glob("*")):
                if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".m4v", ".avi", ".webm"}:
                    result.append({"id": f"{prefix}:{path.name}", "name": path.name, "bytes": path.stat().st_size})
        return result

    def models(self):
        return sorted(path.name for path in (ROOT / "models").glob("*.pt") if path.is_file())

    def source(self, data):
        mode = data.get("source_type", "video")
        if mode == "iphone":
            return validate_phone_url(str(data.get("url", ""))), "iphone13"
        if mode == "webcam":
            return str(number(data.get("camera", 0), "Câmera", 0, 9)), "webcam_teste"
        if mode != "video":
            raise ValueError("Tipo de fonte inválido")
        identifier = data.get("video", "")
        available = {v["id"] for v in self.videos()}
        if identifier not in available:
            raise ValueError("Selecione um vídeo disponível ou envie um arquivo")
        prefix, filename = identifier.split(":", 1)
        return str((ROOT / "videos" if prefix == "video" else self.uploads) / filename), filename

    def start(self, data, test_only=False):
        source, label = self.source(data)
        origin = str(data.get("origin", "")).strip() or label
        if len(origin) > 100 or "://" in origin:
            raise ValueError("Use uma origem curta, sem URL ou credenciais")
        if test_only:
            duration = number(data.get("seconds", 10), "Duração", 1, 60)
            self.jobs.start(lambda job: self.test_source(source, duration, job), mode="conexao", source_label=origin)
        else:
            from .__main__ import parser
            from .pipeline import run
            args = parser().parse_args(["processar"])
            args.fonte, args.origem = source, origin
            args.a_cada = number(data.get("every", 1 if data.get("source_type") == "iphone" else 3), "Intervalo de quadros", 1, 60)
            args.ocr_a_cada = number(data.get("ocr_every", 2), "Intervalo de OCR", 1, 30)
            args.max_quadros = number(data.get("max_frames", 300), "Limite de quadros", 0, 1000000)
            args.imgsz = number(data.get("image_size", 480), "Resolução da inferência", 320, 1280)
            args.limiar = number(data.get("threshold", .7), "Compatibilidade", 0, 1, False)
            args.sem_ocr = bool(data.get("no_ocr", False))
            args.registrar_placas = bool(data.get("save_plates", True)) and not args.sem_ocr
            args.targets = self.targets()
            load_targets(args)
            if args.sem_ocr and any(t["placa"] for t in args.targets):
                raise ValueError("Há um alvo com placa. Habilite OCR ou remova a placa da lista de alvos.")
            model = str(data.get("model", "yolov8n.pt"))
            plate_model = str(data.get("plate_model", ""))
            available_models = self.models()
            if model not in available_models or (plate_model and plate_model not in available_models):
                raise ValueError("Selecione modelos existentes na pasta models do projeto")
            args.modelo = str(ROOT / "models" / model)
            args.modelo_placa = str(ROOT / "models" / plate_model) if plate_model else None
            args.banco = str(self.store.path)
            args.run_id = uuid.uuid4().hex
            args.relatorio = str(self.folder / f"execucao_{args.run_id}.json")
            self.jobs.start(lambda job: run(args, on_frame=job.image, on_progress=job.progress, stop_event=job.stop_event), mode="analise", source_label=origin)
        return self.jobs.snapshot()

    def start_demo(self, data):
        source, label = self.source(data)
        origin = str(data.get("origin", "")).strip() or label
        if len(origin) > 100 or "://" in origin:
            raise ValueError("Use uma origem curta, sem URL ou credenciais")
        mode = data.get("mode")
        if mode not in {"facial", "veiculos"}:
            raise ValueError("Selecione detecção facial ou extração de veículos")
        authorized = data.get("authorized") is True
        if mode == "facial" and not authorized:
            raise ValueError("Confirme a autorização para utilizar as imagens na demonstração facial")
        maximum = number(data.get("max_frames", 900), "Limite de quadros da demonstração", 1, 10000)
        every = number(data.get("every", 1), "Intervalo da demonstração", 1, 60)
        model = ROOT / "models" / "yolov8n.pt"
        if mode == "veiculos" and not model.is_file():
            raise ValueError("Modelo local de veículos não encontrado")
        self.jobs.start(lambda job: run_demo(self.archive, job, mode=mode, source=source, origin=origin,
                                            max_frames=maximum, every=every, authorized=authorized,
                                            model_path=str(model) if mode == "veiculos" else None),
                        mode="demo_" + mode, source_label=origin)
        return self.jobs.snapshot()

    def request_face_capture(self):
        with self.jobs.lock:
            if (not self.jobs.thread or not self.jobs.thread.is_alive() or
                    self.jobs.state.get("mode") != "demo_facial" or self.jobs.state["status"] != "executando"):
                raise ValueError("Inicie uma demonstração facial antes de capturar")
            self.jobs.capture_requested.set()
        return {"message": "Captura solicitada para o próximo quadro analisado"}

    @staticmethod
    def test_source(source, duration, job):
        from .sources import open_source
        capture = open_source(int(source) if source.isdigit() else source)
        frames = 0
        try:
            if not capture.isOpened():
                raise RuntimeError("Sem imagem. Confira a fonte, a transmissão no iPhone e as permissões de rede local.")
            started = time.monotonic()
            while time.monotonic() - started < duration and not job.stop_event.is_set():
                ok, image = capture.read()
                if not ok:
                    if frames and "://" not in source and not source.isdigit():
                        break
                    raise RuntimeError("A fonte não forneceu uma imagem atual")
                frames += 1
                job.image(image)
                job.progress({"quadros_lidos": frames, "resolucao": f"{image.shape[1]} × {image.shape[0]}", "fase": "testando_conexao"})
                # Arquivos locais têm reprodução moderada; câmeras já têm ritmo próprio.
                if "://" not in source and not source.isdigit():
                    job.stop_event.wait(.04)
            return {"quadros_lidos": frames, "resolucao": job.snapshot()["progress"].get("resolucao"), "nota": "Teste de recepção sem análise de IA; não cria alertas."}
        finally:
            capture.release()

    def state(self):
        alerts = self.store.list()
        runs = self.store.runs()
        for run in runs:
            path = self.evaluations / f"{run['id']}.json"
            run["evaluation"] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        return {"job": self.jobs.snapshot(), "targets": self.targets(), "videos": self.videos(), "models": self.models(), "alerts": list(reversed(alerts))[:200], "runs": runs[:100], "demo_runs": self.archive.runs(), "audit": list(reversed(self.store.audit()))[:300], "counts": {"alerts": len(alerts), "pending": sum(a["state"] == "pendente" for a in alerts), "reviewed": sum(a["state"] != "pendente" for a in alerts), "runs": len(runs)}, "capabilities": {"pessoas": "nao_implementado", "facial": "deteccao_e_captura_autorizada", "identidade_facial": "nao_implementado", "emocoes": "nao_suportado"}}

    def health(self):
        dependencies = {}
        for package in ("ultralytics", "opencv-python", "pytesseract", "numpy"):
            try:
                dependencies[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                dependencies[package] = None
        import os
        tesseract = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        return {"dependencies": dependencies, "model": (ROOT / "models/yolov8n.pt").is_file(), "tesseract": Path(tesseract).is_file(), "database": str(self.store.path), "scope": "Servidor restrito a este computador. O iPhone fornece vídeo; a IA roda no PC."}

    def evaluate(self, data):
        run_id = str(data.get("run", ""))
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError("Selecione uma execução registrada")
        summary = run["summary"]
        if summary.get("estado_execucao") == "erro":
            raise ValueError("A execução falhou. Corrija a fonte e execute um novo teste antes de avaliar.")
        reference = data.get("reference")
        alerts = [a for a in self.store.list() if a["run"] == run_id]
        result = evaluate(alerts, reference)
        if any(e["origem"] != summary["origem"] for e in reference):
            raise ValueError(f"A origem das anotações deve ser {summary['origem']}")
        result.update(execucao=run_id, avaliado_em=timestamp(), reference=reference)
        (self.evaluations / f"{run_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


class Server(ThreadingHTTPServer):
    daemon_threads = True


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Evita persistir nomes de arquivos e parâmetros de URLs nos logs.
            pass

        def respond(self, body, content_type="application/json; charset=utf-8", status=200):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.respond({"error": "Host inválido"}, status=403)
            route = urlsplit(self.path).path
            try:
                if route in ("/", "/index.html"):
                    page = (WEB / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", app.token)
                    return self.respond(page.encode(), "text/html; charset=utf-8")
                if route in ("/app.js", "/style.css"):
                    return self.respond((WEB / route[1:]).read_bytes(), "text/javascript; charset=utf-8" if route.endswith("js") else "text/css; charset=utf-8")
                if route in ("/assets/horulince-logo.png", "/assets/horulince-favicon.svg"):
                    return self.respond((WEB / route[1:]).read_bytes(), "image/png" if route.endswith("png") else "image/svg+xml")
                if route == "/api/state":
                    return self.respond(app.state())
                if route == "/api/health":
                    return self.respond(app.health())
                if route == "/api/audit":
                    return self.respond(app.store.audit())
                if route in ("/api/captures", "/api/captures-export"):
                    filters = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                    return self.respond(app.archive.query(filters, export=route.endswith("-export")))
                if route.startswith("/api/capture-image/"):
                    identifier = route.rsplit("/", 1)[-1]
                    path = app.archive.image_path(identifier)
                    if path:
                        return self.respond(path.read_bytes(), "image/jpeg")
                if route == "/api/frame.jpg":
                    with app.jobs.lock:
                        frame = app.jobs.frame
                    return self.respond(frame or b"", "image/jpeg", 200 if frame else 204)
                if route.startswith("/api/evidence/"):
                    identifier = route.rsplit("/", 1)[-1]
                    alert = next((a for a in app.store.list() if a["id"] == identifier), None)
                    if alert:
                        path = Path(alert["evidence"]).resolve()
                        if path.is_relative_to(app.store.evidence_dir.resolve()) and path.is_file():
                            return self.respond(path.read_bytes(), "image/jpeg")
                if route.startswith("/api/report/"):
                    identifier = route.rsplit("/", 1)[-1]
                    run = app.store.get_run(identifier)
                    if run:
                        report_file = app.evaluations / f"{identifier}.json"
                        return self.respond({"execution": run, "evaluation": json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else None})
                return self.respond({"error": "Recurso não encontrado"}, status=404)
            except (ValueError, OSError, sqlite3.Error) as error:
                return self.respond({"error": str(error)}, status=400)

        def do_POST(self):
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.valid_host() or self.headers.get("X-Horulince-Token") != app.token or (origin and origin not in allowed):
                return self.respond({"error": "Sessão inválida; recarregue o painel"}, status=403)
            route = urlsplit(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit = 250 * 1024 * 1024 if route == "/api/upload" else 2 * 1024 * 1024
                if not 0 < length <= limit:
                    raise ValueError("Arquivo/corpo vazio ou acima do limite permitido")
                if route == "/api/upload":
                    name = parse_qs(urlsplit(self.path).query).get("name", [""])[0]
                    suffix = Path(name).suffix.lower()
                    if suffix not in {".mp4", ".mov", ".m4v", ".avi", ".webm"}:
                        raise ValueError("Envie um vídeo MP4, MOV, M4V, AVI ou WebM")
                    destination = app.uploads / f"{uuid.uuid4().hex}{suffix}"
                    remaining = length
                    try:
                        with destination.open("wb") as output:
                            while remaining:
                                chunk = self.rfile.read(min(1024 * 1024, remaining))
                                if not chunk:
                                    raise ValueError("Envio de arquivo incompleto")
                                output.write(chunk)
                                remaining -= len(chunk)
                    except Exception:
                        destination.unlink(missing_ok=True)
                        raise
                    return self.respond({"id": f"upload:{destination.name}", "name": name})
                data = json.loads(self.rfile.read(length))
                if route == "/api/demo/start":
                    return self.respond(app.start_demo(data))
                if route == "/api/demo/capture":
                    return self.respond(app.request_face_capture())
                if route == "/api/targets":
                    return self.respond({"targets": app.save_targets(data.get("targets"))})
                if route in ("/api/start", "/api/test-source"):
                    return self.respond(app.start(data, test_only=route.endswith("test-source")))
                if route == "/api/stop":
                    app.jobs.stop()
                    return self.respond(app.jobs.snapshot())
                if route == "/api/review":
                    app.store.review(str(data.get("id", "")), data.get("state", ""), data.get("actor", ""), data.get("reason", ""),
                                     expected_state=data.get("expected_state"))
                    return self.respond({"ok": True})
                if route == "/api/evaluate":
                    return self.respond(app.evaluate(data))
                return self.respond({"error": "Ação não encontrada"}, status=404)
            except ReviewConflict as error:
                return self.respond({"error": str(error)}, status=409)
            except (ValueError, TypeError, AttributeError, OSError, sqlite3.Error) as error:
                return self.respond({"error": str(error)}, status=400)
    return Handler


def serve(port=8765, database=None, open_browser=False):
    port = number(port, "Porta", 1024, 65535)
    app = Dashboard(database or ROOT / "dados/horulince.sqlite3")
    server = Server(("127.0.0.1", port), handler_for(app))
    print(f"Painel Horulince: http://127.0.0.1:{port}\nEncerre com Ctrl+C.", flush=True)
    if open_browser:
        import webbrowser
        threading.Timer(.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    try:
        server.serve_forever()
    finally:
        app.jobs.stop_event.set()
        server.server_close()
