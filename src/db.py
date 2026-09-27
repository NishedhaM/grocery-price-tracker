"""
SQLite storage layer for the grocery price tracker.

Design goal: running the daily job twice for the same date never creates
duplicate rows (see the UNIQUE constraint in db/schema.sql) — it just
re-writes that day's numbers, which matters because GitHub Actions
schedules can occasionally fire twice or be re-run manually.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "grocery_prices.db"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    return " ".join(str(name).strip().lower().split())


def upsert_snapshot(conn: sqlite3.Connection, row: dict) -> None:
    """Insert one price_snapshots row; update it in place if the same
    (date, store, stream, category, item, sku) combination already exists.
    """
    row = dict(row)  # don't mutate caller's dict
    row.setdefault("item_name_normalized", normalize_name(row.get("item_name")))
    if isinstance(row.get("raw_json"), (dict, list)):
        row["raw_json"] = json.dumps(row["raw_json"], ensure_ascii=False)

    columns = [
        "scrape_date", "scraped_at", "store", "source_stream", "category",
        "item_name", "item_name_normalized", "sku", "unit", "uom", "brand",
        "price", "mrp", "promo_price", "discount_pct", "promo_type",
        "is_promo", "available", "source_url", "raw_json",
    ]
    values = [row.get(c) for c in columns]
    placeholders = ", ".join(["?"] * len(columns))
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in
                               ("scrape_date", "store", "source_stream", "category", "item_name", "sku"))

    sql = f"""
        INSERT INTO price_snapshots ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (scrape_date, store, source_stream, category, item_name, sku)
        DO UPDATE SET {update_clause}
    """
    conn.execute(sql, values)


def upsert_many(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    n = 0
    for row in rows:
        upsert_snapshot(conn, row)
        n += 1
    conn.commit()
    return n


def log_run(conn: sqlite3.Connection, run_at: str, store: str, status: str,
            rows_written: int = 0, message: str = "") -> None:
    conn.execute(
        "INSERT INTO run_log (run_at, store, status, rows_written, message) VALUES (?, ?, ?, ?, ?)",
        (run_at, store, status, rows_written, message),
    )
    conn.commit()


def upsert_credit_card_promo(conn: sqlite3.Connection, row: dict) -> None:
    columns = ["logged_date", "bank", "merchant", "title", "card_types",
               "discount", "valid_until", "description", "url"]
    values = [row.get(c) for c in columns]
    placeholders = ", ".join(["?"] * len(columns))
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in
                               ("logged_date", "bank", "merchant", "title"))
    sql = f"""
        INSERT INTO credit_card_promos ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (logged_date, bank, merchant, title)
        DO UPDATE SET {update_clause}
    """
    conn.execute(sql, values)
    conn.commit()
