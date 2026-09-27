-- Unified schema for the grocery price tracker.
-- One row = one item, at one store, on one calendar day.
-- The UNIQUE constraint makes daily runs idempotent: re-running the
-- same day for the same store/item just updates the row instead of
-- duplicating it (see src/db.py: INSERT ... ON CONFLICT DO UPDATE).

CREATE TABLE IF NOT EXISTS price_snapshots (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_date           TEXT    NOT NULL,   -- 'YYYY-MM-DD', the day this snapshot represents
    scraped_at            TEXT    NOT NULL,   -- ISO timestamp of the actual run
    store                 TEXT    NOT NULL,   -- 'keells' | 'cargills' | 'arpico' | 'spar' | 'glomark'
    source_stream         TEXT    NOT NULL,   -- 'catalog' | 'promotion'
    category               TEXT,               -- e.g. 'vegetables', 'fruits', 'mega_discount'
    item_name             TEXT    NOT NULL,
    item_name_normalized  TEXT,               -- lowercased/trimmed, for cross-store matching later
    matched_group_id       TEXT,               -- filled in by the (future) product-matching step
    sku                   TEXT,
    unit                  TEXT,
    uom                   TEXT,
    brand                 TEXT,
    price                 REAL,               -- current selling price
    mrp                   REAL,               -- regular / pre-promo price, if known
    promo_price           REAL,               -- promotional price, if different from price
    discount_pct          REAL,
    promo_type            TEXT,               -- free text, e.g. 'BOGO', 'collection: Mega Discount'
    is_promo              INTEGER DEFAULT 0,
    available             INTEGER,
    source_url            TEXT,
    raw_json              TEXT,               -- original API record, kept for auditing/debugging
    UNIQUE (scrape_date, store, source_stream, category, item_name, sku)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date_store ON price_snapshots (scrape_date, store);
CREATE INDEX IF NOT EXISTS idx_snapshots_item ON price_snapshots (item_name_normalized);

CREATE TABLE IF NOT EXISTS credit_card_promos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_date   TEXT NOT NULL,
    bank          TEXT NOT NULL,
    merchant      TEXT,
    title         TEXT,
    card_types    TEXT,
    discount      TEXT,
    valid_until   TEXT,
    description   TEXT,
    url           TEXT,
    UNIQUE (logged_date, bank, merchant, title)
);

CREATE TABLE IF NOT EXISTS run_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at       TEXT NOT NULL,
    store        TEXT NOT NULL,
    status       TEXT NOT NULL,   -- 'ok' | 'failed'
    rows_written INTEGER DEFAULT 0,
    message      TEXT
);
