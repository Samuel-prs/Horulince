-- Horulince: extensão aditiva para demonstrações legadas e acervo.
-- Execute fora de outra transação; não apaga dados existentes.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS demo_runs (
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

COMMIT;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
