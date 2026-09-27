"""
Daily orchestrator: run every configured store's scraper, normalize
its rows into the shared schema, and write them into SQLite.

Usage:
    python -m src.run_daily
    python -m src.run_daily --stores keells,cargills
    python -m src.run_daily --date 2026-09-10   # backfill a specific date

Design notes:
- Each store runs inside its own try/except: one store failing (a
  changed API, an expired cookie) never stops the others from writing
  their data, which matters a lot for an unattended daily job.
- Every run — success or failure — is recorded in run_log so you can
  see gaps in the daily series later without digging through CI logs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from . import db
from .scrapers import cargills, keells, arpico, creditcards

SCRAPERS = {
    "cargills": cargills.scrape_all,
    "keells": keells.scrape_all,
    "arpico": arpico.scrape_all,
}

# Credit card promos write into a different table (credit_card_promos,
# keyed by bank/merchant/title) so they're handled separately below
# rather than through the price_snapshots upsert path.
CREDIT_CARD_SCRAPERS = {
    "seylan": creditcards.scrape_seylan,
    "combank": creditcards.scrape_combank,
    "hnb": creditcards.scrape_hnb,
    "sampath": creditcards.scrape_sampath,
    "boc": creditcards.scrape_boc,
    "peoples": creditcards.scrape_peoples,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    all_targets = list(SCRAPERS.keys()) + list(CREDIT_CARD_SCRAPERS.keys())
    parser.add_argument("--stores", default=",".join(all_targets),
                         help="comma-separated subset of: " + ",".join(all_targets))
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; defaults to today")
    args = parser.parse_args()

    scrape_date = args.date or dt.date.today().isoformat()
    requested = [s.strip() for s in args.stores.split(",") if s.strip()]

    conn = db.get_connection()
    db.init_db(conn)

    def _safe_log_run(run_at: str, store: str, status: str, *,
                       rows_written: int = 0, message: str = "") -> None:
        """db.log_run itself failing (e.g. the same DB error that just
        failed the scrape) must never take down the whole run — every
        remaining store still deserves its own attempt. Worst case, this
        store's outcome just doesn't get an entry in run_log."""
        try:
            db.log_run(conn, run_at, store, status, rows_written=rows_written, message=message)
        except Exception as log_exc:  # noqa: BLE001
            print(f"[warn] could not write run_log for {store}: {log_exc}", file=sys.stderr)

    exit_code = 0
    for store in requested:
        run_at = dt.datetime.utcnow().isoformat()

        if store in SCRAPERS:
            try:
                rows = SCRAPERS[store](scrape_date)
                n = db.upsert_many(conn, rows)
                _safe_log_run(run_at, store, "ok", rows_written=n)
                print(f"[ok] {store}: {n} rows for {scrape_date}")
            except Exception as exc:  # noqa: BLE001 - a single store must never kill the run
                conn.rollback()  # clear any half-finished transaction before the next store
                _safe_log_run(run_at, store, "failed", rows_written=0, message=str(exc))
                print(f"[FAILED] {store}: {exc}", file=sys.stderr)
                exit_code = 1
            continue

        if store in CREDIT_CARD_SCRAPERS:
            try:
                rows = CREDIT_CARD_SCRAPERS[store](scrape_date)
                for row in rows:
                    db.upsert_credit_card_promo(conn, row)
                _safe_log_run(run_at, store, "ok", rows_written=len(rows))
                print(f"[ok] {store}: {len(rows)} credit-card promo rows for {scrape_date}")
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _safe_log_run(run_at, store, "failed", rows_written=0, message=str(exc))
                print(f"[FAILED] {store}: {exc}", file=sys.stderr)
                exit_code = 1
            continue

        print(f"[skip] unknown target '{store}'")

    conn.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
