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

import json
import time

import requests

from .. import config
from .. import basket

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


class CargillsClient:
    """Sends the product-list requests to cargillsonline.com.

    Primary mode: the request is made *inside* a headless Chrome page on
    cargillsonline.com (JavaScript fetch), so it carries exactly the
    cookies, headers and origin the real website uses. A plain
    requests.Session was not enough: since automation started it only ever
    received "No Products Found" placeholders or a non-JSON page.
    Fallback mode: requests.Session with the browser's cookies.
    """

    _FETCH_JS = """
        const [url, body, done] = arguments;
        fetch(url, {method: 'POST', credentials: 'include',
                    headers: {'content-type': 'application/json;charset=UTF-8',
                              'accept': 'application/json, text/plain, */*'},
                    body: body})
          .then(r => r.text().then(t => done({status: r.status, text: t})))
          .catch(e => done({status: 0, text: String(e)}));
    """

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA})
        self._diagnosed = False
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("user-agent=" + _UA)
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            self.driver.set_script_timeout(90)
            self.driver.get(config.CARGILLS_HOME_URL)
            time.sleep(8)
            # Opening a category page lets the site set its store/location cookies.
            self.driver.get(config.CARGILLS_CATALOG_CATEGORIES[0]["referer"])
            time.sleep(8)
            cookies = {c["name"]: c["value"] for c in self.driver.get_cookies()}
            print(f"[info] Cargills: browser cookies = {sorted(cookies)}")
            self.session.cookies.update(cookies)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Cargills: headless browser unavailable ({exc}); using plain HTTP")
            self.driver = None
        for k, v in config.CARGILLS_STATIC_COOKIES.items():
            self.session.cookies.setdefault(k, v)

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:  # noqa: BLE001
                pass

    def _send(self, url: str, payload: dict, referer: str) -> tuple[int, str, str]:
        if self.driver is not None:
            res = self.driver.execute_async_script(self._FETCH_JS, url, json.dumps(payload))
            return int(res.get("status") or 0), res.get("text") or "", "browser"
        headers = {"accept": "application/json, text/plain, */*",
                   "content-type": "application/json;charset=UTF-8",
                   "origin": "https://cargillsonline.com", "referer": referer}
        resp = self.session.post(url, headers=headers, json=payload, timeout=30)
        return resp.status_code, resp.text, "http"

    def post(self, url: str, payload: dict, referer: str) -> list[dict]:
        """Returns the raw item list, or [] if the reply is not usable JSON."""
        status, text, mode = self._send(url, payload, referer)
        if not self._diagnosed:   # printed once per run to the Actions log
            self._diagnosed = True
            print(f"[info] Cargills first reply via {mode}: HTTP {status}, "
                  f"{len(text)} chars, starts with: {text[:160]!r}")
        if status != 200:
            print(f"[warn] Cargills {url.rsplit('/', 2)[-2]}: HTTP {status}")
            return []
        try:
            data = json.loads(text)
        except ValueError:
            print(f"[warn] Cargills {url.rsplit('/', 2)[-2]}: reply is not JSON ({text[:80]!r})")
            return []
        items = []
        if isinstance(data, dict):
            items = data.get("Data") or data.get("data") or data.get("Result") or []
            if isinstance(items, dict):
                items = items.get("Items") or items.get("Products") or items.get("ItemList") or []
        elif isinstance(data, list):
            items = data
        return items if isinstance(items, list) else []


def _is_placeholder(item: dict) -> bool:
    name = str(item.get("ItemName") or item.get("Name") or item.get("ProductName") or "").strip().lower()
    return not name or name == "no products found"


def _post_category(client: CargillsClient, *, referer: str, category_id: str = "",
                    section_id: str = "", collection_id: str = "", search: str = "",
                    page_size: int = 10000) -> list[dict]:
    """Returns real product dicts only (placeholders removed). Tries each
    endpoint in config.CARGILLS_ENDPOINTS until one returns real products."""
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
    for url in config.CARGILLS_ENDPOINTS:
        try:
            items = client.post(url, payload, referer)
        except Exception as exc:  # noqa: BLE001 - try the next endpoint
            print(f"[warn] Cargills request failed: {exc}")
            continue
        real = [i for i in items if isinstance(i, dict) and not _is_placeholder(i)]
        if real:
            return real
    return []


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


def scrape_basket(client: CargillsClient, *, scrape_date: str, scraped_at: str) -> list[dict]:
    """Search Cargills for every basket item; keep the top results."""
    rows: list[dict] = []
    for item in basket.load_basket():
        try:
            items = _post_category(client, referer=config.CARGILLS_HOME_URL,
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
    scraped_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()
    client = CargillsClient()
    rows: list[dict] = []
    empty: list[str] = []
    try:
        for cat in config.CARGILLS_CATALOG_CATEGORIES:
            items = _post_category(client, referer=cat["referer"], category_id=cat["category_id"])
            if not items:
                empty.append(cat["key"])
            rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                                 category=cat["key"], source_stream="catalog",
                                 source_url=cat["referer"]) for i in items)

        for coll in config.CARGILLS_PROMO_COLLECTIONS:
            items = _post_category(client, referer=coll["referer"],
                                    section_id=coll["section_id"], collection_id=coll["collection_id"])
            if not items:
                empty.append(coll["key"])   # seasonal banner probably rotated: update config.py
            rows.extend(_to_row(i, scrape_date=scrape_date, scraped_at=scraped_at,
                                 category=coll["key"], source_stream="promotion",
                                 source_url=coll["referer"]) for i in items)

        rows.extend(scrape_basket(client, scrape_date=scrape_date, scraped_at=scraped_at))
    finally:
        client.close()

    if empty:
        print(f"[warn] Cargills: no products for {', '.join(empty)}")
    if not rows:
        # Raising makes run_daily log this store as 'failed' instead of 'ok'.
        raise RuntimeError("Cargills returned no real products; see the [info] Cargills lines above")
    return rows


if __name__ == "__main__":
    result = scrape_all()
    print(f"Cargills: {len(result)} rows")
