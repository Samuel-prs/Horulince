"""Persistência local e histórico de decisões. SQLite não fornece autenticação."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

STATES = {"confirmado_para_analise", "descartado", "revisao_solicitada"}
OPEN_STATES = {"pendente", "revisao_solicitada"}
FINAL_STATES = {"confirmado_para_analise", "descartado"}


class ReviewConflict(ValueError):
    """A decisão já foi finalizada ou a tela ficou desatualizada."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AlertStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = self.path.parent / "evidencias"
        self.plate_dir = self.path.parent / "placas"
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, summary TEXT NOT NULL, configuration TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY, run TEXT NOT NULL, track INTEGER NOT NULL,
                    target TEXT NOT NULL, source TEXT NOT NULL, video_seconds REAL NOT NULL,
                    created_at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pendente',
                    evidence TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(run, track, target)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT NOT NULL,
                    at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
                    reason TEXT NOT NULL, FOREIGN KEY(alert_id) REFERENCES alerts(id)
                );
                CREATE TABLE IF NOT EXISTS plate_reads (
                    id TEXT PRIMARY KEY, run TEXT NOT NULL, track INTEGER NOT NULL,
                    source TEXT NOT NULL, video_seconds REAL NOT NULL, created_at TEXT NOT NULL,
                    plate TEXT NOT NULL, evidence TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(run,track,plate)
                );
                CREATE INDEX IF NOT EXISTS idx_plate_reads_plate ON plate_reads(plate,created_at);
            ''')

    def record_plate(self, *, run, track, source, video_seconds, payload, write_evidence):
        """OCR válido com estado explícito; somente consenso pode ser consolidado."""
        from .core import valid_plate
        import math
        plate = payload.get("placa", "")
        state = payload.get("estado_leitura", "consolidada")
        consensus = payload.get("consolidacao") or {}
        readings, attempts = consensus.get("leituras", 0), consensus.get("tentativas", 0)
        if not valid_plate(plate) or state not in {"pendente_consenso","consolidada"}:
            raise ValueError("Formato ou estado da leitura de placa inválido")
        if state == "consolidada" and (readings < 3 or attempts < readings or readings/max(attempts,1) < .7):
            raise ValueError("Somente placas válidas com consenso temporal podem ser armazenadas")
        confidence = payload.get("confianca_ocr",consensus.get("confianca_ocr_media",0))
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 55 <= confidence <= 100:
            raise ValueError("A leitura precisa atingir o escore mínimo do OCR")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id,payload FROM plate_reads WHERE run=? AND track=? AND plate=?", (run,track,plate)).fetchone()
            if row:
                previous = json.loads(row["payload"])
                if state == "consolidada" and previous.get("estado_leitura") != "consolidada":
                    previous.update(estado_leitura="consolidada",consolidacao=consensus,
                                    quadro_confirmacao=payload.get("quadro"),confirmada_em_video=video_seconds,
                                    nota=payload.get("nota"))
                    db.execute("UPDATE plate_reads SET payload=? WHERE id=?",(json.dumps(previous,ensure_ascii=False),row["id"]))
                return row["id"], False
            payload = payload | {"estado_leitura":state,"track":track}
            identifier = uuid.uuid4().hex
            self.plate_dir.mkdir(parents=True,exist_ok=True)
            path = self.plate_dir / f"{identifier}.jpg"
            try:
                if not write_evidence(str(path)) or not path.is_file():
                    raise OSError("Não foi possível salvar a imagem da placa")
                db.execute("INSERT INTO plate_reads VALUES(?,?,?,?,?,?,?,?,?)",
                           (identifier,run,track,source,video_seconds,now(),plate,str(path),json.dumps(payload,ensure_ascii=False)))
            except Exception:
                path.unlink(missing_ok=True)
                raise
        return identifier, True

    def plate_count(self):
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM plate_reads").fetchone()[0]

    def record_run(self, summary, configuration):
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,summary,configuration) VALUES(?,?,?)", (summary["execucao"], json.dumps(summary, ensure_ascii=False), json.dumps(configuration, ensure_ascii=False)))

    def get_run(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            return {"summary": json.loads(row["summary"]), "configuration": json.loads(row["configuration"])} if row else None

    def runs(self):
        with self.connect() as db:
            return [{"id": row["id"], "summary": json.loads(row["summary"]), "configuration": json.loads(row["configuration"])} for row in db.execute("SELECT * FROM runs ORDER BY rowid DESC")]

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, *, run, track, target, source, video_seconds, payload, write_evidence):
        """Um alerta por alvo/track/execução; evidência só para candidatos."""
        with self.connect() as db:
            existing = db.execute("SELECT id FROM alerts WHERE run=? AND track=? AND target=?", (run, track, target)).fetchone()
            if existing:
                return existing["id"], False
            alert_id = uuid.uuid4().hex
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            evidence = self.evidence_dir / f"{alert_id}.jpg"
            try:
                if not write_evidence(str(evidence)) or not evidence.is_file():
                    raise OSError("Não foi possível salvar a evidência")
                db.execute("INSERT INTO alerts(id,run,track,target,source,video_seconds,created_at,evidence,payload) VALUES(?,?,?,?,?,?,?,?,?)", (alert_id, run, track, target, source, video_seconds, now(), str(evidence), json.dumps(payload, ensure_ascii=False)))
                db.execute("INSERT INTO audit(alert_id,at,actor,action,reason) VALUES(?,?,?,?,?)", (alert_id, now(), "sistema", "criado", "Candidato aguardando revisão humana"))
            except Exception:
                evidence.unlink(missing_ok=True)
                raise
        return alert_id, True

    def list(self, state=None):
        if state is not None and state not in STATES | {"pendente"}:
            raise ValueError("Estado inválido")
        with self.connect() as db:
            rows = db.execute("SELECT * FROM alerts" + (" WHERE state=?" if state else "") + " ORDER BY created_at", (state,) if state else ()).fetchall()
            return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def review(self, alert_id, state, actor, reason, *, expected_state=None):
        if (not isinstance(state, str) or state not in STATES or not isinstance(actor, str)
                or not isinstance(reason, str) or not actor.strip() or not reason.strip()):
            raise ValueError("Informe estado válido, operador e justificativa")
        actor, reason = actor.strip(), reason.strip()
        if len(actor) > 100 or len(reason) > 2000:
            raise ValueError("Use até 100 caracteres no operador e 2000 na justificativa")
        if expected_state is not None and (not isinstance(expected_state, str) or expected_state not in OPEN_STATES):
            raise ValueError("Estado esperado inválido para revisão")
        with self.connect() as db:
            # UPDATE condicional garante uma única decisão mesmo entre processos.
            query = "UPDATE alerts SET state=? WHERE id=? AND state IN ('pendente','revisao_solicitada')"
            params = [state, alert_id]
            if expected_state is not None:
                query += " AND state=?"
                params.append(expected_state)
            updated = db.execute(query, params)
            if updated.rowcount != 1:
                existing = db.execute("SELECT state FROM alerts WHERE id=?", (alert_id,)).fetchone()
                if existing is None:
                    raise ValueError("Alerta não encontrado")
                if existing["state"] in FINAL_STATES:
                    raise ReviewConflict("Alerta já finalizado; a decisão registrada foi preservada")
                raise ReviewConflict("O alerta foi alterado por outro operador; atualize e confira a decisão")
            db.execute("INSERT INTO audit(alert_id,at,actor,action,reason) VALUES(?,?,?,?,?)", (alert_id, now(), actor, state, reason))

    def audit(self, alert_id=None):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audit" + (" WHERE alert_id=?" if alert_id else "") + " ORDER BY seq", (alert_id,) if alert_id else ())]
