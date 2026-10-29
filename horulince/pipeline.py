from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

from .core import COLORS, VEHICLES, Tracker, candidate, normalize_plate, valid_plate
from .storage import AlertStore
from .sources import is_network, open_source

ROOT = Path(__file__).resolve().parent.parent


def load_targets(args):
    targets = getattr(args, "targets", None)
    if targets is None:
        targets = json.loads(Path(args.lista).read_text(encoding="utf-8")) if args.lista else [{"id": "alvo_cli", "tipo": args.tipo, "cor": args.cor, "placa": args.placa}]
    if not isinstance(targets, list) or not targets:
        raise ValueError("A lista deve conter ao menos um alvo")
    identifiers = set()
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get("id"), str) or not target["id"].strip() or target["id"] in identifiers:
            raise ValueError("Cada alvo precisa de um id textual único")
        identifiers.add(target["id"])
        if not isinstance(target.get("placa", ""), str):
            raise ValueError("Placa deve ser texto")
        target["placa"] = normalize_plate(target.get("placa", ""))
        if target["placa"] and not valid_plate(target["placa"]):
            raise ValueError(f"Placa inválida no alvo {target['id']}")
        if target.get("tipo") not in VEHICLES.values() or target.get("cor") not in COLORS:
            raise ValueError(f"Tipo ou cor inválidos no alvo {target['id']}")
    return targets


def run(args, *, on_frame=None, on_progress=None, stop_event=None):
    if args.a_cada < 1 or args.ocr_a_cada < 1 or args.max_quadros < 0 or args.imgsz < 32 or not 0 <= args.limiar <= 1:
        raise ValueError("Intervalos devem ser positivos; limiar deve estar entre 0 e 1")
    targets = load_targets(args)
    model_path = Path(args.modelo)
    if not model_path.is_file():
        raise ValueError(f"Modelo local não encontrado: {model_path}. Nenhum download automático será feito.")
    if args.modelo_placa and not Path(args.modelo_placa).is_file():
        raise ValueError("Modelo de placas não encontrado")
    import cv2
    from ultralytics import YOLO
    from .vision import configure_tesseract, read_plate, vehicle_colors

    if not args.sem_ocr:
        configure_tesseract(args.tesseract)
    elif any(t["placa"] for t in targets):
        raise ValueError("Um alvo com placa exige OCR habilitado")
    model = YOLO(str(model_path))
    plate_model = YOLO(args.modelo_placa) if args.modelo_placa else None
    source = int(args.fonte) if args.fonte.isdigit() else args.fonte
    source_id = args.origem or (f"camera:{source}" if isinstance(source, int) else Path(source).name if "://" not in source else "camera_rede")
    run_id = getattr(args, "run_id", None) or uuid.uuid4().hex
    frame = cycle = alert_count = processed = 0
    total_ms = 0.0
    store = AlertStore(args.banco)
    stats_path = Path(args.relatorio).resolve()
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    emitted = set()
    capture = open_source(source)
    failure = None
    cancelled = False
    if on_progress:
        on_progress({"execucao": run_id, "origem": source_id, "fase": "conectando"})
    try:
        if not capture.isOpened():
            raise RuntimeError("Não foi possível abrir a fonte de vídeo")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not 0 < fps < 1000:
            fps = 30.0
        tracker = Tracker(max_age=max(args.a_cada * 2, int(fps * .6)))
        live = isinstance(source, int) or is_network(source)
        last_generation = 0
        last_processed_seconds = None
        started = time.monotonic()
        while not args.max_quadros or frame < args.max_quadros:
            if stop_event is not None and stop_event.is_set():
                cancelled = True
                break
            ok, image = capture.read()
            if stop_event is not None and stop_event.is_set():
                cancelled = True
                break
            if not ok:
                if is_network(source):
                    raise RuntimeError(getattr(capture, "failure", None) or "Transmissão interrompida; confira o app e a rede Wi-Fi")
                break
            frame += 1
            if frame % args.a_cada:
                continue
            tick = time.perf_counter()
            observed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            seconds = time.monotonic() - started if live else (frame - 1) / fps
            generation = getattr(capture, "delivered_generation", 0)
            if generation != last_generation or (live and last_processed_seconds is not None and seconds - last_processed_seconds > 2):
                # IDs sempre novos: um celular reconectado não herda placas antigas.
                tracker.tracks.clear()
            last_generation = generation
            last_processed_seconds = seconds
            result = model(image, classes=list(VEHICLES), conf=.4, imgsz=args.imgsz, verbose=False)[0]
            height, width = image.shape[:2]
            detections = []
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
                if x2 - x1 >= 80 and y2 > y1:
                    detections.append({"box": (x1, y1, x2, y2), "tipo": VEHICLES[int(box.cls.item())], "confianca_deteccao": float(box.conf.item())})
            tracks = tracker.update(detections, frame)
            active_ids = set(tracker.tracks)
            emitted = {key for key in emitted if key[0] in active_ids}
            cycle += 1
            # Rodízio limitado: não deixa os primeiros veículos monopolizarem OCR.
            eligible = sorted(zip(detections, tracks), key=lambda pair: (pair[1].last_ocr_frame, pair[1].id))
            selected = {t.id for d, t in eligible if d["box"][2] - d["box"][0] >= 120}
            selected = [t.id for _, t in eligible if t.id in selected][:2] if cycle % args.ocr_a_cada == 0 else []
            live_results = []
            for detection, track in zip(detections, tracks):
                x1, y1, x2, y2 = detection["box"]
                crop = image[y1:y2, x1:x2]
                colors = vehicle_colors(crop)
                if track.last_ocr_seconds >= 0 and seconds - track.last_ocr_seconds > 2:
                    track.votes.readings.clear()
                if not args.sem_ocr and track.id in selected:
                    plate, confidence = read_plate(crop, plate_model)
                    track.votes.add(plate, confidence)
                    track.last_ocr_frame = frame
                    track.last_ocr_seconds = seconds
                consensus = track.votes.consensus()
                labels = []
                for target in targets:
                    key = (track.id, target["id"])
                    match = candidate(detection["tipo"], colors, consensus, target, args.limiar)
                    if not match or track.hits < 3:
                        continue
                    labels.append(match["correspondencia"])
                    if key in emitted:
                        continue
                    payload = match | {"tipo": detection["tipo"], "cores": colors, "confianca_deteccao": detection["confianca_deteccao"], "observado_em": observed_at, "quadro": frame, "box": detection["box"], "duracao_processamento_ate_alerta_ms": round((time.perf_counter() - tick) * 1000, 2), "localizacao_placa": "modelo" if plate_model else "contornos_heuristicos", "nota": "Candidato para revisão; notas não são probabilidade de identificação."}
                    alert_id, created = store.create(run=run_id, track=track.id, target=target["id"], source=source_id, video_seconds=seconds, payload=payload, write_evidence=lambda path: cv2.imwrite(path, crop))
                    emitted.add(key)
                    if created:
                        alert_count += 1
                        print(f"CANDIDATO {alert_id} | {source_id} {seconds:.2f}s | {match['correspondencia']} | placa={match['placa'] or '-'}", flush=True)
                live_results.append({"track": track.id, "tipo": detection["tipo"], "box": list(detection["box"]),
                                     "cores": colors, "confianca_deteccao": detection["confianca_deteccao"],
                                     "placa": consensus["placa"] if consensus else None, "correspondencias": labels})
                if args.mostrar or on_frame is not None:
                    color = (0, 200, 255) if labels else (160, 160, 160)
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                    text = f"ID {track.id} {detection['tipo']} {consensus['placa'] if consensus else ''} {'/'.join(labels)}"
                    cv2.putText(image, text, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
            processed += 1
            total_ms += (time.perf_counter() - tick) * 1000
            if on_frame:
                on_frame(image)
            if on_progress:
                on_progress({"execucao": run_id, "origem": source_id, "fase": "analisando", "quadros_lidos": frame, "quadros_processados": processed, "alertas": alert_count, "veiculos_no_quadro": len(detections), "instante_video": round(seconds, 2), "processamento_medio_ms": round(total_ms / processed, 2), "deteccoes": live_results, "fps_processamento": round(processed / max(time.monotonic() - started, .001), 2)})
            if args.mostrar:
                cv2.imshow("Horulince - candidatos para revisao", image)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cancelled = True
                    break
    except Exception as error:
        failure = error
    finally:
        capture.release()
        if args.mostrar:
            cv2.destroyAllWindows()
    report = {"execucao": run_id, "origem": source_id, "quadros_lidos": frame, "quadros_processados": processed, "alertas": alert_count, "reconexoes": getattr(capture, "reconnections", 0), "processamento_medio_ms": round(total_ms / processed, 2) if processed else None, "precisao": None, "revocacao": None, "nota": "Tempo de processamento local; não mede latência de rede ou revisão. Qualidade exige referência anotada."}
    report["estado_execucao"] = "erro" if failure else "interrompida" if cancelled else "concluida"
    store.record_run(report, {"alvos": targets, "a_cada": args.a_cada, "ocr_a_cada": args.ocr_a_cada, "imgsz": args.imgsz, "sem_ocr": args.sem_ocr, "limiar_caracteristicas": args.limiar, "modelo": model_path.name, "modelo_placa": Path(args.modelo_placa).name if args.modelo_placa else None})
    stats_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failure is not None:
        raise failure
    return report
