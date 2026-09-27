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

import requests

from .. import config


def _bootstrap_session() -> requests.Session:
    """Get a fresh ASP.NET_SessionId instead of relying on a hardcoded
    one, which is what made the original scripts break within hours."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; grocery-price-tracker/1.0)"})
    try:
        session.get(config.CARGILLS_HOME_URL, timeout=20)
    except requests.RequestException:
        pass  # fall through; static cookies below may still be enough
    session.cookies.update(config.CARGILLS_STATIC_COOKIES)
    return session


def _post_category(session: requests.Session, *, referer: str, category_id: str = "",
                    section_id: str = "", collection_id: str = "") -> list[dict]:
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://cargillsonline.com",
        "referer": referer,
    }
    payload = {
        "CategoryId": category_id,
        "Search": "",
        "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
        "PageIndex": 1,
        "PageSize": 10000,
        "BannerId": "",
        "SectionId": section_id,
        "CollectionId": collection_id,
        "SectionType": "QmFubmVy" if section_id else "",
        "DataType": "Q29sbGVjdGlvbg==" if collection_id else "",
        "SubCatId": "-1",
        "PromoId": "",
    }
    resp = session.post(config.CARGILLS_BASE_URL, headers=headers, json=payload, timeout=30)
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


def scrape_all(scrape_date: str | None = None) -> list[dict]:
    scrape_date = scrape_date or dt.date.today().isoformat()
    scraped_at = dt.datetime.utcnow().isoformat()
    session = _bootstrap_session()
    rows: list[dict] = []

    for cat in config.CARGILLS_CATALOG_CATEGORIES:
        items = _post_category(session, referer=cat["referer"], category_id=cat["category_id"])
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=cat["key"], source_stream="catalog",
                             source_url=cat["referer"]) for i in items)

    for coll in config.CARGILLS_PROMO_COLLECTIONS:
        items = _post_category(session, referer=coll["referer"],
                                section_id=coll["section_id"], collection_id=coll["collection_id"])
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=coll["key"], source_stream="promotion",
                             source_url=coll["referer"]) for i in items)

    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Cargills: {len(result)} rows")
