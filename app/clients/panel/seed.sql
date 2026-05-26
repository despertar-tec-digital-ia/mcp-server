CREATE TABLE IF NOT EXISTS panel_clients (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    slug       TEXT    NOT NULL UNIQUE,
    giro       TEXT,
    status     TEXT    NOT NULL DEFAULT 'setup',
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
