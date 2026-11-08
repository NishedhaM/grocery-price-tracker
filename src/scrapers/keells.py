"""
Keells Super scraper.

Adapted from research data/keels/items/Veg/veg.py and
research data/keels/Discounts/discounts.py — those two were the only
scripts in the original zip that actually hit keellssuper.com's own
API (zebraliveback.keellssuper.com). Everything else in the project
that was named "keells_*" turned out to be Cargills data under the
wrong label (see cargills.py's docstring) — double check that if you
ever compare row counts against the old .xlsx files.

Keells requires a session cookie minted by loading the site in a real
browser first, so this uses headless Selenium once per run to fetch
that cookie, then talks to the JSON API directly for speed.
"""
from __future__ import annotations

import datetime as dt
import time

import requests

from .. import basket, config


def _get_session_cookies() -> tuple[dict, str | None]:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(config.KEELLS_HOME_URL)
        time.sleep(6)
        cookies_raw = driver.get_cookies()
    finally:
        driver.quit()

    cookies = {}
    usersessionid = None
    for c in cookies_raw:
        cookies[c["name"]] = c["value"]
        if c["name"].startswith("auth_cookie"):
            usersessionid = c["name"].replace("auth_cookie_", "")
    return cookies, usersessionid


def _to_row(item: dict, *, scrape_date: str, scraped_at: str, category: str,
            source_stream: str = "catalog") -> dict:
    """Keells returns 'amount' = the price charged today. When a promotion
    applies, promotionDiscountValue is the saving, so the regular price is
    amount + promotionDiscountValue (this matches the 'MRP (est.)' column
    in the June 2026 promotions export). 'uom' is 'KG' for loose items sold
    per kg and 'NO' for items sold per piece/pack."""
    price = float(item.get("amount") or 0) or None
    promo_value = float(item.get("promotionDiscountValue") or 0)
    on_promo = bool(item.get("isPromotionApplied")) and promo_value > 0
    mrp = round(price + promo_value, 2) if (price and on_promo) else None
    uom = (item.get("uom") or "").strip() or None

    return {
        "scrape_date": scrape_date,
        "scraped_at": scraped_at,
        "store": "keells",
        "source_stream": source_stream,
        "category": category,
        "item_name": " ".join(str(item.get("name") or "").split()),   # strip padding spaces
        "sku": item.get("itemCode") or item.get("itemID"),
        "unit": "1" if uom == "KG" else None,
        "uom": uom,
        "brand": None,
        "price": price,
        "mrp": mrp,
        "promo_price": price if on_promo else None,
        "discount_pct": round(promo_value / mrp * 100, 2) if mrp else None,
        "promo_type": "promotion" if on_promo else None,
        "is_promo": 1 if on_promo else 0,
        "available": item.get("isAvailable"),
        "source_url": config.KEELLS_API_URL,
        "raw_json": item,
    }


def _items_from(data: dict) -> list[dict]:
    result = data.get("result") or {}
    return (result.get("itemDetailResult", {}).get("itemDetails")
            or result.get("itemDetailsList")
            or result.get("dealsProductsList")
            or [])


def scrape_basket(headers: dict, cookies: dict, *, scrape_date: str, scraped_at: str) -> list[dict]:
    """Search Keells for every basket item (same search call the website's
    search box makes, as captured in research data/keels/Discounts)."""
    rows: list[dict] = []
    for b in basket.load_basket():
        params = {
            "fromCount": 0, "toCount": 40, "outletCode": config.KEELLS_OUTLET_CODE,
            "departmentId": "", "subDepartmentId": "", "categoryId": "",
            "itemDescription": b["search_term"], "itemPricefrom": 0, "itemPriceTo": 100000,
            "isFeatured": 0, "isPromotionOnly": "false", "promotionCategory": "",
            "sortBy": "default", "BrandId": "", "storeName": "", "subDeaprtmentCode": "",
            "stockStatus": "true", "brandName": "",
        }
        try:
            resp = requests.get(config.KEELLS_SEARCH_URL, headers=headers, cookies=cookies,
                                params=params, timeout=30)
            resp.raise_for_status()
            items = _items_from(resp.json())
        except Exception as exc:  # noqa: BLE001 - one search must not stop the rest
            print(f"[warn] Keells basket search '{b['search_term']}' failed: {exc}")
            continue
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=b["basket_id"], source_stream="basket") for i in items[:40])
        time.sleep(config.SEARCH_DELAY_SECONDS)
    return rows


def scrape_all(scrape_date: str | None = None) -> list[dict]:
    scrape_date = scrape_date or dt.date.today().isoformat()
    scraped_at = dt.datetime.utcnow().isoformat()

    cookies, usersessionid = _get_session_cookies()
    if not usersessionid:
        raise RuntimeError("Keells: could not obtain usersessionid from browser cookies")

    headers = {
        "accept": "application/json",
        "origin": "https://www.keellssuper.com",
        "referer": "https://www.keellssuper.com/",
        "user-agent": "Mozilla/5.0",
        "usersessionid": usersessionid,
    }

    rows: list[dict] = []
    for dept in config.KEELLS_DEPARTMENTS:
        params = {
            "pageNo": 1,
            "itemsPerPage": 1000,
            "outletCode": config.KEELLS_OUTLET_CODE,
            "departmentId": dept["department_id"],
            "itemPricefrom": 0,
            "itemPriceTo": 100000,
            "isPromotionOnly": "false",
        }
        resp = requests.get(config.KEELLS_API_URL, headers=headers, cookies=cookies,
                             params=params, timeout=30)
        resp.raise_for_status()
        items = _items_from(resp.json())
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=dept["key"]) for i in items)

    rows.extend(scrape_basket(headers, cookies, scrape_date=scrape_date, scraped_at=scraped_at))
    if not rows:
        raise RuntimeError("Keells returned no products")
    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Keells: {len(result)} rows")
