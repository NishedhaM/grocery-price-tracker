"""
build_ilp_dataset.py
--------------------
Exports everything in db/grocery_prices.db to one Excel workbook and adds
ILP-ready sheets for the grocery basket optimisation model (proposal 4.6,
Phase 2): item set I, stores S, cost matrix c(i,s), and bank card offers
r/m/u(s,k) by date.

Usage (from the repo root):
    pip install pandas openpyxl rapidfuzz
    python scripts/build_ilp_dataset.py
    python scripts/build_ilp_dataset.py --db db/grocery_prices.db --out grocery_ilp_dataset.xlsx

Optional: data/manual_card_offers.csv lets you add or correct card offers
whose conditions the scrapers cannot read (e.g. People's Bank minimum
spend / valid days). Rows there replace scraped rows with the same offer_id.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re

import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import basket as basket_mod  # noqa: E402

# ----------------------------------------------------------------------------
# Scope (must match the revised proposal, section 4.5)
# ----------------------------------------------------------------------------
STORES = ["keells", "cargills", "arpico"]
STORE_LABEL = {"keells": "Keells", "cargills": "Cargills", "arpico": "Arpico"}
BANKS = ["HNB", "People's Bank", "Seylan"]
MATCH_ACCEPT = 90      # RapidFuzz score accepted automatically
MATCH_REVIEW = 80      # 80-89 kept but flagged for manual review
CALENDAR_START = dt.date(2026, 6, 20)
CALENDAR_END = dt.date(2026, 12, 31)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l|pcs|pc)\b", re.I)
STOPWORDS = r"\b(fresh|leaf|pack|bulk|each|unit|net bag|chopped|large|small)\b"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def to_num(v):
    """'₨ 2,125.00' -> 2125.0 ; None/'' -> None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.]", "", str(v).replace(",", ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def norm_name(name: str) -> str:
    """Matching key: lower case, no sizes/brands-noise words, singular."""
    n = str(name).lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = SIZE_RE.sub(" ", n)
    n = re.sub(STOPWORDS, " ", n)
    n = re.sub(r"[^a-z ]", " ", n)
    words = []
    for t in n.split():
        if t.endswith("oes"):
            t = t[:-2]
        elif t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
            t = t[:-1]
        words.append(t)
    return " ".join(words).strip()


def weight_kg(name: str):
    m = SIZE_RE.search(str(name))
    if m and m.group(2).lower() in ("g", "kg"):
        return float(m.group(1)) * (1 if m.group(2).lower() == "kg" else 0.001)
    return None


# ----------------------------------------------------------------------------
# 1. Load and clean
# ----------------------------------------------------------------------------
def load(db_path: str):
    import sqlite3
    con = sqlite3.connect(db_path)
    prices = pd.read_sql("SELECT * FROM price_snapshots", con)
    cards = pd.read_sql("SELECT * FROM credit_card_promos", con)
    runs = pd.read_sql("SELECT * FROM run_log", con)
    con.close()
    return prices, cards, runs


def clean_prices(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    p["item_name"] = p["item_name"].astype(str).str.strip()
    p["is_placeholder"] = (p["item_name"] == "No Products Found").astype(int)
    p["in_scope_store"] = p["store"].isin(STORES).astype(int)
    p["price_lkr"] = p["price"].map(to_num)
    p["mrp_lkr"] = p["mrp"].map(to_num)
    p["promo_price_lkr"] = p["promo_price"].map(to_num)

    # Keells: the scraper leaves uom/promo empty, but they are in raw_json.
    def keells_extra(r):
        if r["store"] != "keells" or not r["raw_json"]:
            return pd.Series([r["uom"], r["is_promo"], None, None])
        try:
            j = json.loads(r["raw_json"])
        except Exception:
            return pd.Series([r["uom"], r["is_promo"], None, None])
        uom = j.get("uom") or r["uom"]
        promo = j.get("isPromotionApplied")
        if promo is None:
            promo = j.get("Is Promo")
        disc = j.get("promotionDiscountValue")
        item_id = j.get("itemID") or j.get("Item ID")
        return pd.Series([uom, int(bool(promo)) if promo is not None else r["is_promo"], disc, item_id])

    p[["uom", "is_promo", "keells_promo_discount_value", "keells_item_id"]] = p.apply(keells_extra, axis=1)
    p["match_key"] = p["item_name"].map(norm_name)
    keep = ["id", "scrape_date", "scraped_at", "store", "in_scope_store", "source_stream", "category",
            "item_name", "match_key", "sku", "keells_item_id", "unit", "uom", "brand", "price_lkr", "mrp_lkr",
            "promo_price_lkr", "discount_pct", "promo_type", "is_promo", "keells_promo_discount_value",
            "available", "is_placeholder", "matched_group_id", "source_url"]
    return p[keep]


# ----------------------------------------------------------------------------
# 2. Produce basket: matched items, price per kg or per unit, per store
# ----------------------------------------------------------------------------
def unit_price(r, keells_uom: dict):
    """Return (basis, price per basis) so stores are comparable."""
    price = r["price_lkr"]
    if price is None or pd.isna(price):
        return None, None
    name = r["item_name"]
    if r["store"] == "keells":
        uom = r["uom"] if isinstance(r["uom"], str) and r["uom"] else keells_uom.get(r["keells_item_id"])
        if str(uom).upper() == "KG":
            return "kg", price
        w = weight_kg(name)
        return ("kg", price / w) if w else ("unit", price)
    if r["store"] == "cargills":
        u = str(r["uom"]).lower() if isinstance(r["uom"], str) else ""
        q = to_num(r["unit"]) or 1
        if u in ("g", "kg"):
            return "kg", price / (q * (1 if u == "kg" else 0.001))
        if u in ("pc", "pcs"):
            return "unit", price / q
        return "unit", price
    w = weight_kg(name)
    return ("kg", price / w) if w else ("unit", price)


def build_basket(p: pd.DataFrame):
    produce = p[(p.in_scope_store == 1) & (p.is_placeholder == 0)
                & p.category.isin(["vegetables", "fruits", "vegetables_fruits"])].copy()
    keells_uom = (produce[(produce.store == "keells") & produce.uom.notna()]
                  .drop_duplicates("keells_item_id").set_index("keells_item_id")["uom"].to_dict())
    produce[["basis", "price_per_basis"]] = produce.apply(
        lambda r: pd.Series(unit_price(r, keells_uom)), axis=1)
    produce = produce[produce.price_per_basis.notna()]

    # Reference snapshot: the dates on which all three stores were collected
    # closest together (Keells and Cargills 2026-06-21, Arpico 2026-07-02).
    window = produce[produce.scrape_date <= "2026-07-10"]
    ref = {s: ", ".join(sorted(window[window.store == s].scrape_date.unique())) for s in STORES}
    snap = (window.sort_values("scrape_date")
            .drop_duplicates(["store", "match_key"], keep="last"))
    latest_keells = (produce[produce.store == "keells"].sort_values("scrape_date")
                     .drop_duplicates("match_key", keep="last").set_index("match_key"))

    # Anchor on the Keells product list (the most complete catalogue).
    anchor = latest_keells.reset_index()
    rows = []
    for _, k in anchor.iterrows():
        row = {"match_key": k.match_key, "basis": k.basis, "keells_name": k.item_name,
               "keells_latest_price": round(k.price_per_basis, 2), "keells_latest_date": k.scrape_date}
        ks = snap[(snap.store == "keells") & (snap.keells_item_id == k.keells_item_id)]
        if len(ks) and ks.iloc[0].basis == k.basis:
            row["keells_price"], row["keells_date"], row["keells_score"] = ks.iloc[0].price_per_basis, ks.iloc[0].scrape_date, 100
            row["keells_date_aligned"] = "yes"
        else:   # not in the June snapshot: fall back to the latest Keells price, flagged
            row["keells_price"], row["keells_date"], row["keells_score"] = k.price_per_basis, k.scrape_date, 100
            row["keells_date_aligned"] = "no"
        for s in ("cargills", "arpico"):
            cand = snap[(snap.store == s) & (~snap.match_key.str.contains("bee safe"))]
            m = process.extractOne(k.match_key, cand.match_key.tolist(), scorer=fuzz.token_sort_ratio)
            if not m or m[1] < MATCH_REVIEW:
                continue
            c = cand[cand.match_key == m[0]].iloc[0]
            if c.basis != k.basis:          # 1 unit vs per-kg cannot be compared
                continue
            row[f"{s}_name"], row[f"{s}_score"] = c.item_name, round(m[1], 1)
            row[f"{s}_price"], row[f"{s}_date"] = round(c.price_per_basis, 2), c.scrape_date
        rows.append(row)
    b = pd.DataFrame(rows)
    for s in STORES:
        for col in (f"{s}_price", f"{s}_date", f"{s}_score", f"{s}_name"):
            if col not in b:
                b[col] = None
    b["keells_name"] = b["keells_name"]
    b["stores_priced"] = b[[f"{s}_price" for s in STORES]].notna().sum(axis=1)
    b = b[b.stores_priced >= 2].copy()
    b["needs_review"] = b.apply(lambda r: "yes" if any(
        pd.notna(r[f"{s}_score"]) and r[f"{s}_score"] < MATCH_ACCEPT for s in ("cargills", "arpico")) else "", axis=1)
    b = b.sort_values(["stores_priced", "match_key"], ascending=[False, True]).reset_index(drop=True)
    b.insert(0, "item_id", [f"I{n:03d}" for n in range(1, len(b) + 1)])
    b["category"] = "fresh_produce"
    b["quantity"] = 1.0
    return b, ref


def build_basket_from_searches(p: pd.DataFrame):
    """Use the daily basket searches (source_stream='basket') when they
    exist: pick the cheapest acceptable product per store per basket item
    (src/basket.py pick_best) on the latest date that has basket data."""
    b = p[(p.source_stream == "basket") & (p.in_scope_store == 1) & (p.is_placeholder == 0)]
    if b.empty:
        return None, None
    per_date = b.groupby("scrape_date").store.nunique()
    date = per_date[per_date == per_date.max()].index.max()
    day = b[b.scrape_date == date]
    rows = []
    for item in basket_mod.load_basket():
        row = {"item_id": item["basket_id"], "item_name": item["item"], "category": item["category"],
               "pack_size": item["pack_size"], "quantity": item["monthly_qty"]}
        for s in STORES:
            cands = day[(day.store == s) & (day.category == item["basket_id"])]
            pick = basket_mod.pick_best(
                [{"item_name": r.item_name, "price": r.price_lkr, "unit": r.unit, "uom": r.uom,
                  "is_promo": r.is_promo} for r in cands.itertuples()], item)
            row[f"{s}_name"] = pick["item_name"] if pick else None
            row[f"{s}_price"] = pick["scaled_price"] if pick else None
            row[f"{s}_date"] = date if pick else None
            row[f"{s}_candidates"] = len(cands)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["stores_priced"] = out[[f"{s}_price" for s in STORES]].notna().sum(axis=1)
    return out, date


# ----------------------------------------------------------------------------
# 3. Card offers -> structured r(s,k), m(s,k), u(s,k), valid days
# ----------------------------------------------------------------------------
DATE_YMD = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATE_LONG = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})")


def parse_dates(text: str):
    out = [dt.date.fromisoformat(d) for d in DATE_YMD.findall(text or "")]
    for d, mon, y in DATE_LONG.findall(text or ""):
        try:
            out.append(dt.datetime.strptime(f"{d} {mon} {y}", "%d %B %Y").date())
        except ValueError:
            pass
    return out


def find_store(text: str):
    t = (text or "").lower()
    for s in STORES:
        if s in t or (s == "cargills" and "food city" in t):
            return STORE_LABEL[s]
    return None


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def parse_offer(r) -> dict:
    r = {k: _s(v) for k, v in r.items()}
    bank, merchant = r["bank"], r["merchant"]
    title, desc = r["title"], r["description"]
    if title.strip().lower() == "related promotions":       # Seylan page layout
        primary = desc.split("\n")[0]
        valid_text = next((l for l in desc.split("\n") if l.lower().startswith("valid")), "")
    elif title.strip() and title.strip().lower() != str(merchant).lower():
        # Use the title when it states the offer; otherwise the description's first sentence.
        primary = title if re.search(r"\d+\s?%", title) else (desc.split("\n")[0] or title)
        valid_text = r["valid_until"] or ""
    else:                                                   # People's Bank: name only
        primary, valid_text = "", r["valid_until"] or ""
    merchant = merchant if isinstance(merchant, str) and merchant else find_store(primary)

    rate = re.search(r"(\d+(?:\.\d+)?)\s?%", primary)
    rate = float(rate.group(1)) / 100 if rate else (to_num(r["discount"]) or 0) / 100 or None
    rate_source = "offer text" if re.search(r"\d+\s?%", primary) else "scraper discount column (unverified)"
    m = re.search(r"(?:ABOVE|OVER|MINIMUM(?: SPEND)?(?: OF)?|SPEND)\s*(?:LKR|RS\.?)\s*([\d,]+)", primary, re.I)
    min_spend = to_num(m.group(1)) if m else None
    cap = re.search(r"(?:MAX(?:IMUM)?(?: DISCOUNT| CASHBACK)?(?: OF)?|CAPPED AT)\s*(?:LKR|RS\.?)\s*([\d,]+)", primary, re.I)
    cap = to_num(cap.group(1)) if cap else None

    up = primary.upper()
    if "TOTAL BILL" in up or "BILL" in up and not any(k in up for k in ("VEGETABLE", "DAIRY", "FRUIT", "MEAT", "SEAFOOD")):
        eligible = "total_bill" if "TOTAL BILL" in up else ""
    else:
        eligible = ""
    if not eligible:
        cats = [c for c in ("vegetables", "fruits", "seafood", "meat", "dairy") if c[:-1].upper() in up or c.upper() in up]
        eligible = ";".join(cats)
    offer_type = "cashback" if "CASHBACK" in up else "discount"
    assumed_total = False
    if not eligible and primary:
        eligible, assumed_total = "total_bill", True

    vt = f"{valid_text} {primary}".lower()
    days = [d for d in WEEKDAYS if d in vt]
    if "weekend" in vt:
        days = sorted(set(days + ["saturday", "sunday"]), key=WEEKDAYS.index)
    dates = parse_dates(valid_text)
    specific = ""
    valid_from = valid_to = None
    if valid_text.lower().startswith("valid on"):
        specific = ";".join(sorted({d.isoformat() for d in dates}))
    elif dates:
        if "from" in valid_text.lower() and len(dates) >= 2:
            valid_from, valid_to = min(dates), max(dates)
        else:
            valid_to = max(dates)

    notes = []
    if rate_source != "offer text":
        notes.append("discount % not in offer text")
    if min_spend is None and eligible != "total_bill" and primary:
        notes.append("minimum spend not stated")
    if not primary:
        notes.append("no offer conditions captured: fill from bank website")
    if not days and not specific and primary:
        notes.append("valid days not found")
    if assumed_total:
        notes.append("no category named: assumed whole bill")
    if bank == "HNB":
        notes.append("HNB validity text comes from nearest-line match: spot check")
    if to_num(r["discount"]) and rate and abs(to_num(r["discount"]) / 100 - rate) > 1e-9 and rate_source == "offer text":
        notes.append(f"scraper discount column said {r['discount']}, offer text says {rate:.0%}")
    return {
        "bank": bank, "store": merchant, "offer_type": offer_type, "discount_rate": rate,
        "min_spend_lkr": min_spend, "max_discount_lkr": cap, "eligible": eligible,
        "valid_weekdays": ";".join(days), "specific_dates": specific,
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_to": valid_to.isoformat() if valid_to else None,
        "card_types": r["card_types"], "offer_text": primary[:300], "validity_text": valid_text[:200],
        "logged_date": r["logged_date"], "url": r["url"], "notes": "; ".join(notes),
    }


def build_offers(cards: pd.DataFrame, manual_csv: str | None):
    c = cards[cards.bank.isin(BANKS)]
    parsed = pd.DataFrame([parse_offer(r) for _, r in c.iterrows()])
    parsed = parsed[parsed.store.isin(STORE_LABEL.values())]
    keys = ["bank", "store", "offer_type", "discount_rate", "min_spend_lkr", "eligible",
            "valid_weekdays", "specific_dates", "valid_to"]
    agg = (parsed.fillna({"min_spend_lkr": -1, "valid_to": "", "eligible": ""})
           .groupby(keys, dropna=False)
           .agg(first_seen=("logged_date", "min"), last_seen=("logged_date", "max"),
                days_logged=("logged_date", "nunique"), valid_from=("valid_from", "first"),
                max_discount_lkr=("max_discount_lkr", "first"), card_types=("card_types", "first"),
                offer_text=("offer_text", "first"), validity_text=("validity_text", "first"),
                url=("url", "first"), notes=("notes", "first"))
           .reset_index())
    agg["min_spend_lkr"] = agg["min_spend_lkr"].replace(-1, None)
    agg["valid_to"] = agg["valid_to"].replace("", None)
    # Unknown start date -> first day we saw the offer.
    agg["valid_from"] = agg["valid_from"].fillna(agg["first_seen"])
    # Unknown end date -> last day we saw it.
    agg["valid_to"] = agg["valid_to"].fillna(agg["last_seen"])
    agg = agg.sort_values(["bank", "store", "first_seen"]).reset_index(drop=True)
    agg.insert(0, "offer_id", [f"O{n:03d}" for n in range(1, len(agg) + 1)])
    agg["usable_in_ilp"] = agg.apply(
        lambda r: "no" if "no offer conditions" in (r.notes or "") else "yes", axis=1)

    if manual_csv and os.path.exists(manual_csv):
        man = pd.read_csv(manual_csv, dtype=str)
        man = man[man.offer_id.notna()]
        agg = agg[~agg.offer_id.isin(man.offer_id)]
        man["notes"] = "manual entry"
        man["usable_in_ilp"] = "yes"
        agg = pd.concat([agg, man], ignore_index=True)
    cols = ["offer_id", "bank", "store", "offer_type", "discount_rate", "min_spend_lkr", "max_discount_lkr",
            "eligible", "valid_weekdays", "specific_dates", "valid_from", "valid_to", "first_seen",
            "last_seen", "days_logged", "card_types", "usable_in_ilp", "notes", "offer_text",
            "validity_text", "url"]
    return agg[cols]


def offer_calendar(offers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    d = CALENDAR_START
    while d <= CALENDAR_END:
        wd = WEEKDAYS[d.weekday()]
        for _, o in offers[offers.usable_in_ilp == "yes"].iterrows():
            spec = str(o.specific_dates or "")
            if spec and spec != "nan":
                active = d.isoformat() in spec.split(";")
            else:
                days = [x for x in str(o.valid_weekdays or "").split(";") if x and x != "nan"]
                active = (str(o.valid_from) <= d.isoformat() <= str(o.valid_to)) and (not days or wd in days)
            if active:
                rows.append({"date": d.isoformat(), "weekday": wd.title(), "store": o.store, "bank": o.bank,
                             "offer_id": o.offer_id, "discount_rate": o.discount_rate,
                             "min_spend_lkr": o.min_spend_lkr, "max_discount_lkr": o.max_discount_lkr,
                             "eligible": o.eligible})
        d += dt.timedelta(days=1)
    return pd.DataFrame(rows, columns=["date", "weekday", "store", "bank", "offer_id", "discount_rate",
                                        "min_spend_lkr", "max_discount_lkr", "eligible"])


# ----------------------------------------------------------------------------
# 4. Data quality summary
# ----------------------------------------------------------------------------
def quality(p, cards, runs):
    rows = []
    for s in ["keells", "cargills", "arpico", "glomark", "spar"]:
        g = p[(p.store == s) & (p.is_placeholder == 0)]
        daily = g[g.scrape_date >= "2026-09-27"]
        rows.append({"area": "Prices", "name": STORE_LABEL.get(s, s.title()),
                     "in_scope": "yes" if s in STORES else "no",
                     "real_rows": len(g), "first_date": g.scrape_date.min(), "last_real_date": g.scrape_date.max(),
                     "days_with_data_since_27_Sep": daily.scrape_date.nunique(),
                     "distinct_items": g.item_name.nunique(),
                     "placeholder_rows": int(p[(p.store == s)].is_placeholder.sum())})
    for b in ["HNB", "People's Bank", "Seylan"]:
        g = cards[cards.bank == b]
        rows.append({"area": "Card offers", "name": b, "in_scope": "yes", "real_rows": len(g),
                     "first_date": g.logged_date.min(), "last_real_date": g.logged_date.max(),
                     "days_with_data_since_27_Sep": g[g.logged_date >= "2026-09-27"].logged_date.nunique(),
                     "distinct_items": g.merchant.nunique(), "placeholder_rows": 0})
    for b, key in [("Commercial Bank", "combank"), ("Sampath", "sampath"), ("BOC", "boc")]:
        r = runs[runs.store == key]
        rows.append({"area": "Card offers", "name": b, "in_scope": "no", "real_rows": int(r.rows_written.sum()),
                     "first_date": None, "last_real_date": None, "days_with_data_since_27_Sep": 0,
                     "distinct_items": 0, "placeholder_rows": 0})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 5. Write workbook
# ----------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", start_color="1F4E78")
INPUT_FONT = Font(name="Arial", size=10, color="0000FF")
CHECK_FILL = PatternFill("solid", start_color="FFFF00")


def style_sheet(ws, widths=None):
    for cell in ws[1]:
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 200)), start=1):
        w = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, w + 2), 45)
    if widths:
        for col, w in widths.items():
            ws.column_dimensions[col].width = w


def write_workbook(out, readme, dq, p, cards, runs, basket, mode, offers, cal):
    stores_df = pd.DataFrame({
        "store_id": STORES, "store": [STORE_LABEL[s] for s in STORES],
        "price_dates_used": [", ".join(sorted({str(d) for d in basket[f"{s}_date"].dropna()})) for s in STORES],
        "accessible (1/0)": [1, 1, 1]})
    pay = pd.DataFrame({"payment_id": ["CASH", "HNB", "PEOPLES", "SEYLAN"],
                        "payment_option": ["Cash / no offer", "HNB credit card", "People's Bank credit card",
                                           "Seylan credit card"],
                        "user_holds (1/0)": [1, 1, 1, 1]})
    if mode == "basket":
        # Columns B, E, F must stay item_name, basis, quantity for the cost-matrix formulas.
        items = basket[["item_id", "item_name", "category", "pack_size", "quantity", "stores_priced",
                        "keells_name", "cargills_name", "arpico_name",
                        "keells_candidates", "cargills_candidates", "arpico_candidates"]].copy()
        items.insert(3, "basis", "pack")
        items = items[["item_id", "item_name", "category", "pack_size", "basis", "quantity", "stores_priced",
                       "keells_name", "cargills_name", "arpico_name",
                       "keells_candidates", "cargills_candidates", "arpico_candidates"]]
        items = items.rename(columns={"quantity": "monthly_qty (input)", "keells_name": "keells_product",
                                      "cargills_name": "cargills_product", "arpico_name": "arpico_product"})
        name_col = {s: f"{s}_name" for s in STORES}
    else:
        items = basket[["item_id", "keells_name", "match_key", "category", "basis", "quantity", "stores_priced",
                        "needs_review", "keells_date_aligned", "cargills_name", "cargills_score", "arpico_name",
                        "arpico_score", "keells_latest_price", "keells_latest_date"]].rename(
            columns={"keells_name": "item_name", "quantity": "quantity (input)"})
        name_col = {"keells": "keells_name", "cargills": "cargills_name", "arpico": "arpico_name"}
    long = []
    for _, b in basket.iterrows():
        for s in STORES:
            if pd.notna(b[f"{s}_price"]):
                long.append({"item_id": b.item_id, "store_id": s,
                             "basis": "pack" if mode == "basket" else b.basis,
                             "price_per_basis_lkr": round(float(b[f"{s}_price"]), 2),
                             "price_date": b[f"{s}_date"],
                             "store_item_name": b[name_col[s]],
                             "match_score": None if mode == "basket" else (100 if s == "keells" else b[f"{s}_score"])})
    prices_long = pd.DataFrame(long, columns=["item_id", "store_id", "basis", "price_per_basis_lkr",
                                              "price_date", "store_item_name", "match_score"])

    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        dq.to_excel(xw, sheet_name="Data_Quality", index=False)
        stores_df.to_excel(xw, sheet_name="ILP_Stores", index=False)
        pay.to_excel(xw, sheet_name="ILP_Payment_Options", index=False)
        items.to_excel(xw, sheet_name="ILP_Items", index=False)
        prices_long.to_excel(xw, sheet_name="ILP_Prices", index=False)
        pd.DataFrame({"item_id": basket.item_id}).to_excel(xw, sheet_name="ILP_Cost_Matrix", index=False)
        offers.to_excel(xw, sheet_name="ILP_Card_Offers", index=False)
        cal.to_excel(xw, sheet_name="ILP_Offer_Calendar", index=False)
        p.to_excel(xw, sheet_name="All_Price_Snapshots", index=False)
        cards.to_excel(xw, sheet_name="All_Card_Promos_Raw", index=False)
        runs.to_excel(xw, sheet_name="All_Run_Log", index=False)

    wb = load_workbook(out)
    # Cost matrix with live formulas: c(i,s) = quantity x price per basis.
    ws = wb["ILP_Cost_Matrix"]
    headers = ["item_id", "item_name", "basis", "quantity",
               "price_keells", "price_cargills", "price_arpico",
               "avail_keells", "avail_cargills", "avail_arpico",
               "cost_keells", "cost_cargills", "cost_arpico", "cheapest_store_cost"]
    for j, h in enumerate(headers, start=1):
        ws.cell(row=1, column=j, value=h)
    n = len(basket)
    for i in range(2, n + 2):
        ws[f"B{i}"] = f"=INDEX(ILP_Items!$B:$B,MATCH($A{i},ILP_Items!$A:$A,0))"
        ws[f"C{i}"] = f"=INDEX(ILP_Items!$E:$E,MATCH($A{i},ILP_Items!$A:$A,0))"
        ws[f"D{i}"] = f"=INDEX(ILP_Items!$F:$F,MATCH($A{i},ILP_Items!$A:$A,0))"
        for col, s in zip("EFG", STORES):
            ws[f"{col}{i}"] = (f'=IF(COUNTIFS(ILP_Prices!$A:$A,$A{i},ILP_Prices!$B:$B,"{s}")=0,"",'
                               f'SUMIFS(ILP_Prices!$D:$D,ILP_Prices!$A:$A,$A{i},ILP_Prices!$B:$B,"{s}"))')
        for pc, ac in zip("EFG", "HIJ"):
            ws[f"{ac}{i}"] = f'=IF({pc}{i}="",0,1)'
        for pc, cc in zip("EFG", "KLM"):
            ws[f"{cc}{i}"] = f'=IF({pc}{i}="","",$D{i}*{pc}{i})'
        ws[f"N{i}"] = f'=IF(COUNT(K{i}:M{i})=0,"",MIN(K{i}:M{i}))'
        for col in "EFGKLMN":
            ws[f"{col}{i}"].number_format = "#,##0.00"
    t = n + 2
    ws[f"A{t}"] = "TOTAL"
    for col in "KLM":
        ws[f"{col}{t}"] = f'=SUMPRODUCT(({col}2:{col}{n+1}<>"")*1,{col}2:{col}{n+1})'
    ws[f"N{t}"] = f"=SUM(N2:N{n+1})"
    ws[f"A{t+1}"] = "Items priced"
    for pc, col in zip("EFG", "KLM"):
        ws[f"{col}{t+1}"] = f'=COUNT({pc}2:{pc}{n+1})'
    for col in "KLMN":
        ws[f"{col}{t}"].number_format = "#,##0.00"
        ws[f"{col}{t}"].font = Font(name="Arial", size=10, bold=True)
    ws[f"A{t+3}"] = ("Totals per store only cover the items that store prices, so compare stores "
                     "on items priced at all three (see ILP_Items.stores_priced = 3).")

    for name in wb.sheetnames:
        sh = wb[name]
        body = Font(name="Arial", size=10)
        bold = Font(name="Arial", size=10, bold=True)
        for row in sh.iter_rows(min_row=2):
            for c in row:
                c.font = bold if c.font is not None and c.font.bold else body
        style_sheet(sh)
    wb["README"].column_dimensions["A"].width = 26
    wb["README"].column_dimensions["B"].width = 110
    for row in wb["README"].iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    # Inputs in blue; cells needing a manual check in yellow.
    wi = wb["ILP_Items"]
    for i in range(2, wi.max_row + 1):
        wi[f"F{i}"].font = INPUT_FONT
        if mode == "produce" and wi[f"H{i}"].value == "yes":
            wi[f"H{i}"].fill = CHECK_FILL
    for sh_name, col in (("ILP_Stores", "D"), ("ILP_Payment_Options", "C")):
        sh = wb[sh_name]
        for i in range(2, sh.max_row + 1):
            sh[f"{col}{i}"].font = INPUT_FONT
    wo = wb["ILP_Card_Offers"]
    hdr = {c.value: c.column_letter for c in wo[1]}
    for i in range(2, wo.max_row + 1):
        wo[f"{hdr['discount_rate']}{i}"].number_format = "0%"
        if wo[f"{hdr['notes']}{i}"].value:
            wo[f"{hdr['notes']}{i}"].fill = CHECK_FILL
        if wo[f"{hdr['usable_in_ilp']}{i}"].value == "no":
            for k in ("min_spend_lkr", "valid_weekdays", "valid_to", "usable_in_ilp"):
                wo[f"{hdr[k]}{i}"].fill = CHECK_FILL
    wc = wb["ILP_Offer_Calendar"]
    for i in range(2, wc.max_row + 1):
        wc[f"F{i}"].number_format = "0%"
    wb.save(out)


README_ROWS = [
    ("Purpose", "All data from the grocery price tracker database in one workbook, plus ILP-ready sheets for the "
                "basket optimisation model in proposal section 4.6 (Phase 2). Regenerate with "
                "scripts/build_ilp_dataset.py after each new day of data."),
    ("Scope", "Stores: Keells, Cargills, Arpico. Banks: HNB, People's Bank, Seylan. Glomark, SPAR and other banks "
              "stay in the All_ sheets but are excluded from ILP sheets."),
    ("ILP_Stores", "Set S. 'accessible' is a user input (blue): set 0 to exclude a store."),
    ("ILP_Payment_Options", "Set C (cards + cash). 'user_holds' is a user input (blue)."),
    ("ILP_Items", "Set I: produce items matched across stores (RapidFuzz token-sort score; >= 90 accepted, 80-89 "
                  "flagged yellow for review). quantity (blue) is the amount per basis (kg or unit) in the basket."),
    ("ILP_Prices", "Long table: price per kg or per unit of each item at each store, with the snapshot date. "
                   "This is the source of c(i,s) and a(i,s)."),
    ("ILP_Cost_Matrix", "Wide c(i,s) = quantity x price, and availability a(i,s) (1 if priced). Formulas update when "
                        "you change quantities. Load columns K:M and H:J into PuLP."),
    ("ILP_Card_Offers", "Structured offers: discount rate r, minimum spend m, cap u (blank = no cap stated), eligible "
                        "categories, valid weekdays/dates. Yellow notes = verify on the bank website. Offers marked "
                        "usable_in_ilp = no lack conditions and are left out of the calendar."),
    ("ILP_Offer_Calendar", "One row per date x store x active offer: the r, m, u values the model uses for a chosen "
                           "shopping date."),
    ("All_ sheets", "Every row of price_snapshots, credit_card_promos and run_log, with cleaned prices "
                    "(text like 'Rs 2,125.00' -> 2125), Keells uom/promo recovered from raw_json, a placeholder flag "
                    "and a matching key. raw_json is omitted (too long for Excel cells)."),
    ("Modes", "basket mode (default once basket searches exist): items are the 70 basket lines in data/basket.csv, "
              "priced per pack size using the cheapest acceptable product at each store (src/basket.py). "
              "produce mode (fallback for older data): fresh produce matched across stores by name."),
    ("Important limitation", "Cross-store prices come from the only dates when all three stores were collected "
                             "together (Keells/Cargills 21 Jun, Arpico 2 Jul 2026), and only fresh produce is matched. "
                             "Use this to build and test the model; final results need the repaired Cargills scraper "
                             "and a fixed 60-80 SKU basket across all categories."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/grocery_prices.db")
    ap.add_argument("--out", default="grocery_ilp_dataset.xlsx")
    ap.add_argument("--manual-offers", default="data/manual_card_offers.csv")
    a = ap.parse_args()

    prices, cards, runs = load(a.db)
    p = clean_prices(prices)
    basket, basket_date = build_basket_from_searches(p)
    mode = "basket"
    if basket is None:
        basket, ref = build_basket(p)
        mode = "produce"
    offers = build_offers(cards, a.manual_offers)
    cal = offer_calendar(offers)
    dq = quality(p, cards, runs)
    readme = pd.DataFrame(README_ROWS, columns=["Sheet / topic", "Description"])
    write_workbook(a.out, readme, dq, p, cards, runs, basket, mode, offers, cal)
    print(f"Wrote {a.out} ({mode} mode): {len(basket)} ILP items, {len(offers)} card offers, {len(cal)} calendar rows")


if __name__ == "__main__":
    main()
