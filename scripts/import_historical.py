"""
One-time importer for the snapshots you already collected between
20 June and 10 July 2026, before this pipeline existed. Run this
ONCE after setting up the database so that early, sparse history
isn't lost — everything after that comes from run_daily.py instead.

Setup:
    1. Copy the *entire* "Research Data collection" folder from your
       original zip into historical_data/ next to this script, so the
       relative paths below resolve. Nothing needs renaming.
    2. python scripts/import_historical.py

What this fixes along the way:
    - "keells_products.xlsx" at the project root, and
      "research data/food city/items/veg/cargills_products.xlsx",
      both actually came from cargillsonline.com's API (see
      src/scrapers/cargills.py's docstring) — they're imported here
      as Cargills data, not Keells, even though one filename says
      otherwise.
    - "research data/ARPICO/Veg/Veg.py" scraped spar2u.lk, not Arpico
      — its output (spar2u_vegetables_all_pages.xlsx) is imported as
      SPAR, and "research data/ARPICO/Veg/arpico_products.xlsx" (a
      different, undated file with Product/Price columns and no
      matching script in the zip) is imported as Arpico's catalog,
      best-effort.

Dates below are the files' own last-modified timestamps from the
original zip, which is the closest available evidence for when each
snapshot was actually taken (the proposal's Stream A/B were not yet
producing dated folders except for the one already under
food city/discounts/2026-06-21/).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import db  # noqa: E402

HERE = Path(__file__).resolve().parent
HIST_DIR = HERE.parent / "historical_data"


def _get(row, *keys):
    for k in keys:
        if k in row and pd.notna(row[k]):
            return row[k]
    return None


def _pct(mrp, price):
    try:
        mrp, price = float(mrp), float(price)
        return round((mrp - price) / mrp * 100, 2) if mrp else None
    except (TypeError, ValueError):
        return None


def generic_catalog_row(row, *, store, source_stream, category, scrape_date, source_file):
    name = _get(row, "Name", "Product", "Product Name", "name")
    price = _get(row, "Price", "Promotion Price", "price")
    mrp = _get(row, "MRP", "MRP (est.)", "Regular Price", "old_price", "mrp")
    if mrp is None and _get(row, "Discount") is not None and price is not None:
        pass  # discount given as text/amount elsewhere; leave mrp unknown
    return {
        "scrape_date": scrape_date,
        "scraped_at": scrape_date + "T00:00:00",
        "store": store,
        "source_stream": source_stream,
        "category": category,
        "item_name": name,
        "sku": _get(row, "SKU", "Code", "erpCode", "Item ID"),
        "unit": _get(row, "Unit"),
        "uom": _get(row, "UOM"),
        "brand": _get(row, "Brand"),
        "price": price,
        "mrp": mrp,
        "promo_price": price if (mrp and price and mrp != price) else None,
        "discount_pct": _pct(mrp, price) if mrp else None,
        "promo_type": "historical_import",
        "is_promo": 1 if _get(row, "hasPromo", "Is Promo", "Is Promotion Applied") else 0,
        "available": _get(row, "Available", "stock"),
        "source_url": None,
        "raw_json": {"_imported_from": source_file, **row.dropna().to_dict()},
    }


# Each entry: (relative xlsx path, sheet name or None, store, source_stream, category, scrape_date)
CATALOG_FILES = [
    ("keells_products.xlsx", None, "cargills", "catalog", "vegetables", "2026-06-20"),
    ("research data/food city/items/veg/cargills_products.xlsx", None, "cargills", "catalog", "vegetables", "2026-06-21"),
    ("research data/food city/items/fruits/cargills_fruits_products.xlsx", None, "cargills", "catalog", "fruits", "2026-06-21"),
    ("research data/keels/items/Veg/keells_with_promotions.xlsx", None, "keells", "catalog", "vegetables_fruits", "2026-06-21"),
    ("research data/GLOMARK/Veg/glomark_vegetables.xlsx", "Vegetables", "glomark", "catalog", "vegetables", "2026-06-30"),
    ("research data/ARPICO/Veg/arpico_products.xlsx", None, "arpico", "catalog", "vegetables", "2026-07-02"),
    ("research data/SPAR/Veg/spar2u_vegetables_all_pages.xlsx", None, "spar", "catalog", "vegetables", "2026-07-02"),
]

PROMOTION_FILES = [
    ("research data/food city/discounts/2026-06-21/cargills_mega_discount.xlsx", None, "cargills", "mega_discount", "2026-06-21"),
    ("research data/food city/discounts/2026-06-21/cargills_super_baby_shop.xlsx", None, "cargills", "super_baby_shop", "2026-06-21"),
    ("research data/food city/discounts/2026-06-21/cargills_super_cart_savings.xlsx", None, "cargills", "super_cart_savings", "2026-06-21"),
    ("research data/food city/discounts/2026-06-21/fathers day.xlsx", None, "cargills", "football_fever", "2026-06-21"),
    ("research data/keels/Discounts/keells_promotions_full.xlsx", None, "keells", "storewide_promo", "2026-06-24"),
    ("research data/ARPICO/promotions/arpico_promotions.xlsx", None, "arpico", "special_offers", "2026-07-02"),
    ("research data/GLOMARK/promotions/glomark_deals.xlsx", None, "glomark", "deals", "2026-06-30"),
]

CREDIT_CARD_FILES = [
    # (path, bank, scrape_date)
    ("supermarket_credit_card_offers.xlsx", None, "2026-06-20"),          # generic multi-bank scrape; Bank/Offer columns
    ("research data/Seylan Cards/seylan_promotion.xlsx", "Seylan", "2026-07-10"),
    ("research data/Seylan Cards/keells_promotion.xlsx", "Seylan", "2026-07-10"),
]


def import_catalog_and_promos(conn):
    total = 0
    for path, sheet, store, source_stream, category, scrape_date in CATALOG_FILES:
        fp = HIST_DIR / path
        if not fp.exists():
            print(f"[skip] not found: {path}")
            continue
        df = pd.read_excel(fp, sheet_name=sheet) if sheet else pd.read_excel(fp)
        rows = [generic_catalog_row(r, store=store, source_stream=source_stream, category=category,
                                     scrape_date=scrape_date, source_file=path) for _, r in df.iterrows()]
        rows = [r for r in rows if r["item_name"]]
        total += db.upsert_many(conn, rows)
        print(f"[ok] {path}: {len(rows)} rows -> {store}/{category}/{scrape_date}")

    for path, sheet, store, category, scrape_date in PROMOTION_FILES:
        fp = HIST_DIR / path
        if not fp.exists():
            print(f"[skip] not found: {path}")
            continue
        df = pd.read_excel(fp, sheet_name=sheet) if sheet else pd.read_excel(fp)
        rows = [generic_catalog_row(r, store=store, source_stream="promotion", category=category,
                                     scrape_date=scrape_date, source_file=path) for _, r in df.iterrows()]
        rows = [r for r in rows if r["item_name"]]
        total += db.upsert_many(conn, rows)
        print(f"[ok] {path}: {len(rows)} rows -> {store}/{category}/{scrape_date}")

    return total


def import_credit_cards(conn):
    total = 0
    for path, bank_hint, scrape_date in CREDIT_CARD_FILES:
        fp = HIST_DIR / path
        if not fp.exists():
            print(f"[skip] not found: {path}")
            continue
        df = pd.read_excel(fp)
        for _, row in df.iterrows():
            if "Bank" in df.columns:  # generic multi-bank scrape (Bank/Offer)
                bank = row.get("Bank")
                merchant = None
                title = row.get("Offer")
                card_types = None
                discount = None
                valid_until = None
                description = row.get("Offer")
                url = None
            else:  # structured Seylan-style export
                bank = bank_hint
                merchant = row.get("Merchant")
                title = row.get("Title")
                card_types = row.get("Card Types") or row.get("Card Type")
                discount = row.get("Discount")
                valid_until = row.get("Valid Until")
                description = row.get("Description")
                url = row.get("URL")
            db.upsert_credit_card_promo(conn, {
                "logged_date": scrape_date, "bank": bank, "merchant": merchant,
                "title": title, "card_types": card_types, "discount": discount,
                "valid_until": str(valid_until) if valid_until is not None else None,
                "description": description, "url": url,
            })
            total += 1
        print(f"[ok] {path}: imported into credit_card_promos")
    return total


def main():
    if not HIST_DIR.exists():
        print(f"Copy your old 'Research Data collection' folder into {HIST_DIR} first.")
        return 1
    conn = db.get_connection()
    db.init_db(conn)
    n1 = import_catalog_and_promos(conn)
    n2 = import_credit_cards(conn)
    conn.close()
    print(f"\nDone. {n1} price_snapshots rows, {n2} credit_card_promos rows imported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
