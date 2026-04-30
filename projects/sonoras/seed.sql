-- Schema: Sonora's Carbón y Sal — Módulo de Ofertas
-- Se ejecuta automáticamente desde db.py al inicializar.
-- Usa IF NOT EXISTS

CREATE TABLE IF NOT EXISTS offers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       TEXT    NOT NULL DEFAULT 'sonoras',
    title           TEXT    NOT NULL,
    description     TEXT,
    image_url       TEXT,
    fb_post_id      TEXT    UNIQUE,
    starts_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME,
    is_active       BOOLEAN DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_offers_active
    ON offers(client_id, is_active, expires_at);

CREATE INDEX IF NOT EXISTS idx_offers_fb_post
    ON offers(fb_post_id);
