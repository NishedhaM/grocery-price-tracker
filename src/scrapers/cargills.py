"""
Cargills Food City scraper.

Consolidates what were six separate one-off scripts in the original
research zip (fruits.py, food-city Veg.py, snacks.py, shampoo.py,
promotion_baby.py, peomotion_fathers_day.py, and the file mislabeled
"keells_scraper.py" at the project root — that one actually calls
cargillsonline.com, not keellssuper.com, so its output was Cargills
data saved under a Keells filename). All of them hit the same
GetMenuCategoryItemsPagingV3 endpoint with different Category/Section/
Collection IDs, so here they're just config entries (see config.py).
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

import time

import requests

from .. import config
from .. import basket

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def _browser_cookies() -> dict:
    """Load cargillsonline.com in headless Chrome and return every cookie it
    sets (ASP.NET_SessionId, AuthToken, WSTAPWS, ...). The June 2026 scripts
    that worked used cookies copied from a real browser; the plain
    requests.get() bootstrap that replaced them never received AuthToken,
    and from that point the API only ever answered "No Products Found"."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=" + _UA)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(config.CARGILLS_HOME_URL)
        time.sleep(8)
        # Opening a category page makes the site set its store/location cookies.
        driver.get(config.CARGILLS_CATALOG_CATEGORIES[0]["referer"])
        time.sleep(6)
        return {c["name"]: c["value"] for c in driver.get_cookies()}
    finally:
        driver.quit()


def _bootstrap_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    try:
        session.cookies.update(_browser_cookies())
    except Exception as exc:  # noqa: BLE001 - fall back to a plain session
        print(f"[warn] Cargills: browser cookie bootstrap failed ({exc}); using plain session")
        try:
            session.get(config.CARGILLS_HOME_URL, timeout=20)
        except requests.RequestException:
            pass
    for k, v in config.CARGILLS_STATIC_COOKIES.items():
        session.cookies.setdefault(k, v)
    return session


def _is_placeholder(item: dict) -> bool:
    name = str(item.get("ItemName") or item.get("Name") or item.get("ProductName") or "").strip().lower()
    return not name or name == "no products found"


def _post_category(session: requests.Session, *, referer: str, category_id: str = "",
                    section_id: str = "", collection_id: str = "", search: str = "",
                    page_size: int = 10000) -> list[dict]:
    """Returns real product dicts only (placeholders removed). Tries the V3
    endpoint first and the older V2 endpoint if V3 returns nothing real."""
    for url in config.CARGILLS_ENDPOINTS:
        items = _post_once(session, url, referer=referer, category_id=category_id,
                           section_id=section_id, collection_id=collection_id,
                           search=search, page_size=page_size)
        real = [i for i in items if isinstance(i, dict) and not _is_placeholder(i)]
        if real:
            return real
    return []


def _post_once(session: requests.Session, url: str, *, referer: str, category_id: str,
               section_id: str, collection_id: str, search: str, page_size: int) -> list[dict]:
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://cargillsonline.com",
        "referer": referer,
    }
    payload = {
        "CategoryId": category_id,
        "Search": search,
        "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
        "PageIndex": 1,
        "PageSize": page_size,
        "BannerId": "",
        "SectionId": section_id,
        "CollectionId": collection_id,
        "SectionType": "QmFubmVy" if section_id else "",
        "DataType": "Q29sbGVjdGlvbg==" if collection_id else "",
        "SubCatId": "-1",
        "PromoId": "",
    }
    resp = session.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    items = []
    if isinstance(data, dict):
        items = data.get("Data") or data.get("data") or data.get("Result") or []
        if isinstance(items, dict):
            items = (items.get("Items") or items.get("Products") or items.get("ItemList") or [])
    elif isinstance(data, list):
        items = data
    return items if isinstance(items, list) else []


def _to_row(item: dict, *, scrape_date: str, scraped_at: str, category: str,
            source_stream: str, source_url: str) -> dict:
    price = item.get("Price") or item.get("SellingPrice") or item.get("SalePrice")
    mrp = item.get("MRP") or item.get("Mrp")
    discount = item.get("DiscountAmount") or item.get("Discount")
    discount_pct = None
    try:
        if mrp and price and float(mrp) > 0:
            discount_pct = round((float(mrp) - float(price)) / float(mrp) * 100, 2)
    except (TypeError, ValueError):
        discount_pct = None

    return {
        "scrape_date": scrape_date,
        "scraped_at": scraped_at,
        "store": "cargills",
        "source_stream": source_stream,
        "category": category,
        "item_name": item.get("ItemName") or item.get("Name") or item.get("ProductName"),
        "sku": item.get("SKUCODE") or item.get("SKU") or item.get("Sku"),
        "unit": item.get("UnitSize") or item.get("Size"),
        "uom": item.get("UOM") or item.get("UnitOfMeasure"),
        "brand": item.get("BrandName") or item.get("Brand"),
        "price": price,
        "mrp": mrp,
        "promo_price": price if (mrp and price and mrp != price) else None,
        "discount_pct": discount_pct,
        "promo_type": f"collection:{category}" if source_stream == "promotion" else None,
        "is_promo": 1 if (discount or discount_pct) else 0,
        "available": item.get("IsAvailable") or item.get("Available"),
        "source_url": source_url,
        "raw_json": item,
    }


def scrape_basket(session: requests.Session, *, scrape_date: str, scraped_at: str) -> list[dict]:
    """Search Cargills for every basket item; keep the top results."""
    rows: list[dict] = []
    for item in basket.load_basket():
        try:
            items = _post_category(session, referer=config.CARGILLS_HOME_URL,
                                   search=item["search_term"], page_size=40)
        except Exception as exc:  # noqa: BLE001 - one search must not stop the rest
            print(f"[warn] Cargills basket search '{item['search_term']}' failed: {exc}")
            continue
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=item["basket_id"], source_stream="basket",
                             source_url=config.CARGILLS_HOME_URL) for i in items[:40])
        time.sleep(config.SEARCH_DELAY_SECONDS)
    return rows


def scrape_all(scrape_date: str | None = None) -> list[dict]:
    scrape_date = scrape_date or dt.date.today().isoformat()
    scraped_at = dt.datetime.utcnow().isoformat()
    session = _bootstrap_session()
    rows: list[dict] = []
    empty: list[str] = []

    for cat in config.CARGILLS_CATALOG_CATEGORIES:
        items = _post_category(session, referer=cat["referer"], category_id=cat["category_id"])
        if not items:
            empty.append(cat["key"])
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=cat["key"], source_stream="catalog",
                             source_url=cat["referer"]) for i in items)

    for coll in config.CARGILLS_PROMO_COLLECTIONS:
        items = _post_category(session, referer=coll["referer"],
                                section_id=coll["section_id"], collection_id=coll["collection_id"])
        if not items:
            empty.append(coll["key"])   # seasonal banner probably rotated: update config.py
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=coll["key"], source_stream="promotion",
                             source_url=coll["referer"]) for i in items)

    rows.extend(scrape_basket(session, scrape_date=scrape_date, scraped_at=scraped_at))

    if empty:
        print(f"[warn] Cargills: no products for {', '.join(empty)}")
    if not rows:
        # Raising makes run_daily log this store as 'failed' instead of 'ok'.
        raise RuntimeError("Cargills returned no real products (only 'No Products Found'); "
                           "session/cookie bootstrap or endpoint has changed")
    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Cargills: {len(result)} rows")
