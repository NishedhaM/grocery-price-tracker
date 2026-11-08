"""
Arpico (myarpico.com) scraper.

Adapted from research data/ARPICO/promotions/Promotions.py, the one
genuinely-Arpico script in the zip — its sibling
research data/ARPICO/Veg/Veg.py was actually a copy of the SPAR
scraper (it calls spar2u.lk, saved under the Arpico folder by
mistake), so it isn't reused here.

Only the promotions listing is implemented. Arpico's full item
catalog (non-promo prices) wasn't captured by any script in the
original project, so fetch_catalog() is a stub — to fill it in,
open myarpico.com's category pages in your browser's dev tools the
same way Promotions.py's route=product/special call was found, and
look for the equivalent route=product/category (or similar) call.
"""
from __future__ import annotations

import datetime as dt
import re

import requests
from bs4 import BeautifulSoup

from .. import basket, config
import time


def _to_row(card, *, scrape_date: str, scraped_at: str, source_stream: str = "promotion",
            category: str = "special_offers") -> dict | None:
    name_tag = (card.select_one(".caption h4 a") or card.select_one("h4 a")
                or card.select_one(".product-title a"))
    if not name_tag:
        return None
    name = name_tag.get_text(strip=True)

    regular_price = None
    old_price = card.select_one(".price-old")
    if old_price:
        regular_price = old_price.get_text(" ", strip=True)

    promo_price = None
    new_price = card.select_one(".price-new")
    if new_price:
        promo_price = new_price.get_text(" ", strip=True)
    else:
        price_tag = card.select_one(".price")
        if price_tag:
            promo_price = price_tag.get_text(" ", strip=True)

    def _num(s):
        if not s:
            return None
        m = re.search(r"[\d.,]+", s.replace(",", ""))
        return float(m.group().replace(",", "")) if m else None

    mrp = _num(regular_price)
    price = _num(promo_price) or mrp

    return {
        "scrape_date": scrape_date,
        "scraped_at": scraped_at,
        "store": "arpico",
        "source_stream": source_stream,
        "category": category,
        "item_name": name,
        "sku": None,
        "unit": None,
        "uom": None,
        "brand": None,
        "price": price,
        "mrp": mrp,
        "promo_price": price if (mrp and price and mrp != price) else None,
        "discount_pct": round((mrp - price) / mrp * 100, 2) if (mrp and price and mrp) else None,
        "promo_type": "special_offer" if (mrp and price and mrp != price) else None,
        "is_promo": 1 if (mrp and price and mrp != price) else 0,
        "available": None,
        "source_url": config.ARPICO_PROMOTIONS_URL,
        "raw_json": {"name": name, "regular_price": regular_price, "promo_price": promo_price},
    }


def fetch_promotions(scrape_date: str | None = None) -> list[dict]:
    scrape_date = scrape_date or dt.date.today().isoformat()
    scraped_at = dt.datetime.utcnow().isoformat()

    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    session = requests.Session()
    session.cookies.update(config.ARPICO_STORE_COOKIES)

    rows: list[dict] = []
    for page in range(1, config.ARPICO_PROMO_PAGES + 1):
        params = {"route": "product/special", "language": "en-gb", "limit": "100", "page": page}
        resp = session.get(config.ARPICO_PROMOTIONS_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".product-thumb")
        if not cards:
            break
        for card in cards:
            row = _to_row(card, scrape_date=scrape_date, scraped_at=scraped_at)
            if row:
                rows.append(row)
    return rows


def fetch_basket(scrape_date: str | None = None) -> list[dict]:
    """Search myarpico.com (OpenCart route=product/search) for every basket
    item at the Kadawatha store, so regular (non-promo) prices are captured
    too. Arpico's full category catalogue is still not scraped."""
    scrape_date = scrape_date or dt.date.today().isoformat()
    scraped_at = dt.datetime.utcnow().isoformat()
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    session = requests.Session()
    session.cookies.update(config.ARPICO_STORE_COOKIES)
    rows: list[dict] = []
    for b in basket.load_basket():
        params = {"route": "product/search", "search": b["search_term"], "language": "en-gb", "limit": "40"}
        try:
            resp = session.get(config.ARPICO_PROMOTIONS_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"[warn] Arpico basket search '{b['search_term']}' failed: {exc}")
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".product-thumb")[:40]:
            row = _to_row(card, scrape_date=scrape_date, scraped_at=scraped_at,
                          source_stream="basket", category=b["basket_id"])
            if row:
                rows.append(row)
        time.sleep(config.SEARCH_DELAY_SECONDS)
    return rows


def scrape_all(scrape_date: str | None = None) -> list[dict]:
    rows = fetch_promotions(scrape_date)
    try:
        rows += fetch_basket(scrape_date)
    except Exception as exc:  # noqa: BLE001 - keep the promotions even if search breaks
        print(f"[warn] Arpico basket search failed: {exc}")
    if not rows:
        raise RuntimeError("Arpico returned no products")
    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Arpico: {len(result)} rows")
