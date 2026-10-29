"""Persistência local e histórico de decisões. SQLite não fornece autenticação."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

STATES = {"confirmado_para_analise", "descartado", "revisao_solicitada"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AlertStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = self.path.parent / "evidencias"
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
            ''')

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

    def review(self, alert_id, state, actor, reason):
        if state not in STATES or not actor.strip() or not reason.strip():
            raise ValueError("Informe estado válido, operador e justificativa")
        with self.connect() as db:
            updated = db.execute("UPDATE alerts SET state=? WHERE id=?", (state, alert_id))
            if updated.rowcount != 1:
                raise ValueError("Alerta não encontrado")
            db.execute("INSERT INTO audit(alert_id,at,actor,action,reason) VALUES(?,?,?,?,?)", (alert_id, now(), actor.strip(), state, reason.strip()))

    def audit(self, alert_id=None):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audit" + (" WHERE alert_id=?" if alert_id else "") + " ORDER BY seq", (alert_id,) if alert_id else ())]
