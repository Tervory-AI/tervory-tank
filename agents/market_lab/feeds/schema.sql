-- Market Lab baseline feeds.
-- Additive and idempotent. Portable across SQLite (the runner) and PostgreSQL
-- (apply this file as-is when the Market Lab box imports the package).

CREATE TABLE IF NOT EXISTS feed_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    url TEXT NOT NULL,
    licence TEXT NOT NULL,
    terms_checked_at TEXT NOT NULL,
    cadence TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    ref TEXT NOT NULL,
    title TEXT NOT NULL,
    unit TEXT NOT NULL,
    geo_level TEXT NOT NULL CHECK (geo_level IN ('national', 'state', 'county', 'port', 'metro')),
    geo TEXT NOT NULL,
    frequency TEXT NOT NULL,
    UNIQUE (source_id, ref)
);

CREATE TABLE IF NOT EXISTS points (
    series_id TEXT NOT NULL,
    date TEXT NOT NULL,
    value NUMERIC NOT NULL,
    fetched_at TEXT NOT NULL,
    revision TEXT NOT NULL,
    PRIMARY KEY (series_id, date, revision)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    geo TEXT NOT NULL,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    started TEXT NOT NULL,
    finished TEXT NOT NULL,
    rows INTEGER NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS points_series_idx ON points (series_id);
CREATE INDEX IF NOT EXISTS events_source_idx ON events (source_id, date);
CREATE INDEX IF NOT EXISTS fetch_runs_source_idx ON fetch_runs (source_id, started);
