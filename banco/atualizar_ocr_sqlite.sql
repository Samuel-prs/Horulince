-- Extensao aditiva de leituras OCR. Imagens em placas/, ao lado do SQLite.
-- run nao possui FK: o resumo da execucao e salvo somente ao encerrar.
PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS plate_reads (
    id TEXT PRIMARY KEY, run TEXT NOT NULL, track INTEGER NOT NULL,
    source TEXT NOT NULL, video_seconds REAL NOT NULL, created_at TEXT NOT NULL,
    plate TEXT NOT NULL, evidence TEXT NOT NULL, payload TEXT NOT NULL,
    UNIQUE(run,track,plate)
);
CREATE INDEX IF NOT EXISTS idx_plate_reads_plate ON plate_reads(plate,created_at);
COMMIT;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
