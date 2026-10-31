-- Horulince | Estrutura SQLite compatível com horulince/storage.py
-- Codificação: UTF-8. Não contém dados de pessoas, veículos ou credenciais.
-- Execute em um banco novo. IF NOT EXISTS permite repetir a criação,
-- mas não corrige estruturas antigas ou tabelas existentes incompatíveis.
-- SQLite cria o arquivo ao conectar: não existe CREATE DATABASE neste SGBD.

-- Esta opção deve ser ativada em CADA conexão (o sistema já faz isso).
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Resumos de execuções finalizadas, incluindo interrupções e erros tratados.
-- summary e configuration são documentos JSON serializados pela aplicação.
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    configuration TEXT NOT NULL
);

-- Candidatos produzidos pela análise; a decisão depende de revisão humana.
-- run é o identificador da execução e track é local à execução.
-- NÃO adicionar FK de alerts.run para runs.id neste fluxo: os alertas são
-- gravados durante a análise e runs só recebe o resumo quando ela termina.
CREATE TABLE IF NOT EXISTS alerts (
    id            TEXT PRIMARY KEY,
    run           TEXT NOT NULL,
    track         INTEGER NOT NULL,
    target        TEXT NOT NULL,
    source        TEXT NOT NULL,
    video_seconds REAL NOT NULL,
    created_at    TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'pendente',
    evidence      TEXT NOT NULL,
    payload       TEXT NOT NULL,
    UNIQUE (run, track, target)
);

-- Histórico de criação e de revisão dos candidatos.
-- O operador é informado na aplicação; não representa usuário autenticado.
CREATE TABLE IF NOT EXISTS audit (
    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    at       TEXT NOT NULL,
    actor    TEXT NOT NULL,
    action   TEXT NOT NULL,
    reason   TEXT NOT NULL,
    FOREIGN KEY (alert_id) REFERENCES alerts(id)
);

-- Índices auxiliares para os filtros/ordenações utilizados pelo sistema.
-- As PKs e UNIQUE acima já recebem os índices internos do SQLite.
CREATE INDEX IF NOT EXISTS idx_alerts_created_at
    ON alerts (created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_state_created_at
    ON alerts (state, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_alert_id_seq
    ON audit (alert_id, seq);

-- Extensão isolada das demonstrações legadas.
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

-- Leituras de placa, independentes dos alertas de correspondencia.
CREATE TABLE IF NOT EXISTS plate_reads (
    id TEXT PRIMARY KEY, run TEXT NOT NULL, track INTEGER NOT NULL,
    source TEXT NOT NULL, video_seconds REAL NOT NULL, created_at TEXT NOT NULL,
    plate TEXT NOT NULL, evidence TEXT NOT NULL, payload TEXT NOT NULL,
    UNIQUE(run,track,plate)
);
CREATE INDEX IF NOT EXISTS idx_plate_reads_plate ON plate_reads(plate,created_at);

COMMIT;

-- Verificação: deve retornar "ok" e nenhuma linha, respectivamente.
PRAGMA integrity_check;
PRAGMA foreign_key_check;
