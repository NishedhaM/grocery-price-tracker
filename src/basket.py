"""
Fixed monthly basket (data/basket.csv) used for the ILP model.

Each store is searched daily for every basket item (source_stream =
'basket', category = basket_id). Search results are stored as-is; the
choice of which product represents the basket item at each store is made
afterwards by pick_best(), so the rule can change without re-scraping.

Matching rule (documented in the thesis methodology):
  * the product name must contain every word in must_contain and none in
    must_not_contain;
  * its pack size must be parseable and in the same dimension (weight,
    volume or count) as the basket pack size;
  * the price is scaled to the basket pack size (e.g. a 2kg bag at
    LKR 600 -> LKR 300 for a 1kg basket item);
  * among the acceptable products, the cheapest scaled price is chosen
    ("cheapest equivalent product"). Add a brand to must_contain to force
    an identical-brand comparison for that item instead.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

BASKET_PATH = Path(__file__).resolve().parent.parent / "data" / "basket.csv"

_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|ml|l|ltr|litres?|liters?|pcs|pc|pack|rolls?|eggs|s)\b", re.I)
_DIM = {"kg": ("w", 1000), "g": ("w", 1), "gm": ("w", 1), "gram": ("w", 1), "grams": ("w", 1),
        "l": ("v", 1000), "ltr": ("v", 1000), "litre": ("v", 1000), "litres": ("v", 1000),
        "liter": ("v", 1000), "liters": ("v", 1000), "ml": ("v", 1),
        "pcs": ("n", 1), "pc": ("n", 1), "pack": ("n", 1), "s": ("n", 1),
        "roll": ("n", 1), "rolls": ("n", 1), "eggs": ("n", 1)}


def load_basket(path: Path = BASKET_PATH) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("basket_id")]
    for r in rows:
        r["monthly_qty"] = float(r.get("monthly_qty") or 1)
        r["must_contain"] = [w.strip().lower() for w in (r.get("must_contain") or "").split(";") if w.strip()]
        r["must_not_contain"] = [w.strip().lower() for w in (r.get("must_not_contain") or "").split(";") if w.strip()]
    return rows


def parse_size(text: str | None):
    """'Anchor Milk Powder 400G' -> ('w', 400.0). Returns None if no size."""
    if not text:
        return None
    m = None
    for m in _SIZE.finditer(str(text)):
        pass  # keep the last size mentioned (pack size is usually at the end)
    if not m:
        return None
    dim, factor = _DIM[m.group(2).lower()]
    return dim, float(m.group(1)) * factor


def size_from_row(name: str | None, unit=None, uom=None):
    """Prefer the store's own unit fields, fall back to the product name."""
    if unit not in (None, "") and uom:
        s = parse_size(f"{unit}{uom}")
        if s:
            return s
    if uom and str(uom).upper() == "KG":          # Keells loose items priced per kg
        return ("w", 1000.0)
    return parse_size(name)


def acceptable(name: str, item: dict) -> bool:
    n = (name or "").lower()
    return all(w in n for w in item["must_contain"]) and not any(w in n for w in item["must_not_contain"])


def pick_best(candidates: list[dict], item: dict) -> dict | None:
    """candidates: dicts with item_name, price, unit, uom. Returns the chosen
    candidate with added keys scaled_price, size_ratio, or None."""
    target = parse_size(item["pack_size"])
    best = None
    for c in candidates:
        if c.get("price") in (None, "") or not acceptable(c.get("item_name"), item):
            continue
        size = size_from_row(c.get("item_name"), c.get("unit"), c.get("uom"))
        if not target or not size or size[0] != target[0] or size[1] <= 0:
            continue
        ratio = target[1] / size[1]
        if ratio > 20 or ratio < 0.05:   # e.g. 10g sachet vs 1kg bag: not comparable
            continue
        scaled = float(c["price"]) * ratio
        if best is None or scaled < best["scaled_price"]:
            best = dict(c, scaled_price=round(scaled, 2), size_ratio=round(ratio, 4))
    return best
