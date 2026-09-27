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

from .. import config


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


def _to_row(item: dict, *, scrape_date: str, scraped_at: str, category: str) -> dict:
    price = item.get("amount") or 0
    mrp = item.get("mrp") or item.get("MRP") or 0
    promo_amount = (float(mrp) - float(price)) if (mrp and price) else 0
    discount_pct = round((promo_amount / float(mrp)) * 100, 2) if mrp else 0

    return {
        "scrape_date": scrape_date,
        "scraped_at": scraped_at,
        "store": "keells",
        "source_stream": "catalog",
        "category": category,
        "item_name": item.get("name"),
        "sku": item.get("itemCode") or item.get("itemID"),
        "unit": None,
        "uom": None,
        "brand": None,
        "price": price,
        "mrp": mrp or None,
        "promo_price": price if promo_amount else None,
        "discount_pct": discount_pct or None,
        "promo_type": "promotion" if item.get("isPromotionApplied") else None,
        "is_promo": 1 if promo_amount else 0,
        "available": item.get("isAvailable"),
        "source_url": config.KEELLS_API_URL,
        "raw_json": item,
    }


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
        data = resp.json()
        items = (
            data.get("result", {}).get("itemDetailResult", {}).get("itemDetails")
            or data.get("result", {}).get("itemDetailsList")
            or []
        )
        rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                             category=dept["key"]) for i in items)

    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Keells: {len(result)} rows")
