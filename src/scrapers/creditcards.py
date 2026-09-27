"""
Credit card promotion scraper (OBJ2's Stream C).

Covers four banks now: Seylan (static HTML, no browser needed),
and Commercial Bank / HNB / Sampath (added after checking each
bank's site directly on 6 Sept 2026 — see notes per scraper below).
Not covered: BOC and Peoples' Bank (proposal's other two of five) —
their sites weren't checked yet; add them the same way once you've
looked at their promo pages.

Design: rather than hand-write a bespoke parser per bank (their page
layouts differ), every bank's page text gets fed through one shared
keyword-window scanner (_extract_grocery_promos). It scans for lines
mentioning a grocery chain, then looks a few lines around that mention
for a discount percentage and a "valid ..." date, which matched the
repeating card structure every bank happened to use. It's blunter than
a bespoke per-site parser, but far more resilient to each site's own
markup changing, and it's exactly the technique the original
credit_card.py already used (successfully, just without a real browser
behind it) — this keeps that idea but fixes the two things that made
it only find 2 offers: (1) most of these pages need JS execution to
render their promo cards at all, and (2) Commercial Bank's site 403s a
plain HTTP client but not a real browser session.
"""
from __future__ import annotations

import datetime as dt
import re

import requests
from bs4 import BeautifulSoup

from .. import config

CARD_TYPE_PATTERNS = [
    "Visa Infinite", "Visa Signature", "Visa Platinum", "Visa Gold",
    "World Mastercard", "Mastercard World", "Mastercard Platinum",
    "Mastercard Freedom", "Seylan Premier Credit Cards",
    "Seylan Credit Cards", "All Seylan Credit Cards",
]


# ---------------------------------------------------------------------------
# Seylan: plain HTML, no browser needed
# ---------------------------------------------------------------------------

def _parse_seylan_page(html: str, *, merchant: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["header", "footer", "nav", "script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    if not text:
        return None

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    discount_match = re.search(r"(\d+\s?%)", text)
    discount = discount_match.group(1) if discount_match else ""

    cards = [p for p in CARD_TYPE_PATTERNS if re.search(p, text, re.IGNORECASE)]

    valid_until = ""
    m = re.search(r"Valid\s+(?:until|till)\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        valid_until = m.group(1).strip()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    description = "\n".join(p for p in paragraphs if len(p) > 30)

    if not title and not discount and not cards:
        return None  # page probably didn't load a real promo (dead link, redirect, etc.)

    return {
        "bank": "Seylan",
        "merchant": merchant,
        "title": title or f"{merchant} - Seylan Credit Cards",
        "card_types": ", ".join(cards),
        "discount": discount,
        "valid_until": valid_until,
        "description": description,
        "url": url,
    }


def scrape_seylan(logged_date: str | None = None) -> list[dict]:
    logged_date = logged_date or dt.date.today().isoformat()
    headers = {"User-Agent": "Mozilla/5.0"}
    rows = []
    seen_titles = set()

    for page in config.SEYLAN_PROMO_PAGES:
        try:
            resp = requests.get(page["url"], headers=headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"[warn] Seylan page failed ({page['url']}): {exc}")
            continue

        parsed = _parse_seylan_page(resp.text, merchant=page["merchant"], url=page["url"])
        if parsed and parsed["title"] not in seen_titles:
            parsed["logged_date"] = logged_date
            rows.append(parsed)
            seen_titles.add(parsed["title"])

    return rows


# ---------------------------------------------------------------------------
# Commercial Bank / HNB / Sampath: all three needed a real rendered browser
# to see (ComBank 403s a plain HTTP client's fetch entirely; HNB is a React
# app whose promo cards only exist after JS runs; Sampath's homepage
# carousel likewise). Selenium is already a dependency for Keells, so it's
# reused here rather than adding a second browser-automation library.
# ---------------------------------------------------------------------------

# Common cookie/consent-banner button labels seen on Sri Lankan bank
# sites. A banner sitting on top of the page can block the promo grid
# from ever being visible in body.text even after the JS has otherwise
# rendered it, and a fresh (no saved-cookie) headless session sees this
# banner every single run — unlike a human's browser, which usually has
# it dismissed already. Clicking is best-effort: if none of these match,
# we just proceed with whatever's on the page.
CONSENT_BUTTON_TEXTS = [
    "Accept All", "Accept all", "Accept All Cookies", "I Accept", "I Agree",
    "Allow All", "Allow all", "Got it", "Accept", "OK", "Ok",
]


def _dismiss_consent_banner(driver) -> None:
    from selenium.webdriver.common.by import By

    for label in CONSENT_BUTTON_TEXTS:
        try:
            el = driver.find_element(By.XPATH, f"//*[normalize-space(text())='{label}']")
            el.click()
            return
        except Exception:  # noqa: BLE001 - try the next label
            continue


def _get_rendered_text(url: str, *, click_text: str | None = None, load_more_clicks: int = 0,
                        wait_seconds: int = 10) -> str:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    import time

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,2000")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(3)  # let the page start rendering before we look for a consent banner
        _dismiss_consent_banner(driver)
        time.sleep(wait_seconds)

        if click_text:
            try:
                el = driver.find_element(By.XPATH, f"//*[normalize-space(text())='{click_text}']")
                el.click()
                time.sleep(3)
            except Exception as exc:  # noqa: BLE001 - best-effort; fall through to unfiltered text
                print(f"[warn] could not click '{click_text}' on {url}: {exc}")

        for _ in range(load_more_clicks):
            try:
                btn = driver.find_element(By.XPATH, "//*[normalize-space(text())='Load More']")
                btn.click()
                time.sleep(2)
            except Exception:
                break  # no more "Load More" button, or it's not there this run

        body_text = driver.find_element(By.TAG_NAME, "body").text
        # Printed to the Actions log (not stored in the DB) so a future
        # 0-row run is easy to tell apart from "page genuinely had no
        # grocery promos today" vs. "page never actually rendered".
        print(f"[info] {url}: rendered body text is {len(body_text)} chars")
        return body_text
    finally:
        driver.quit()


def _extract_grocery_promos(text: str, *, bank: str, url: str) -> list[dict]:
    """Scan rendered page text for lines mentioning a grocery chain, and
    pull a discount % / valid-date from the surrounding lines. Generic
    across banks because every one of them renders promos as a repeating
    block of (discount, category, description, valid-date) lines."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows = []
    seen = set()

    for i, line in enumerate(lines):
        low = line.lower()
        merchant = next((kw for kw in config.GROCERY_KEYWORDS if kw in low), None)
        if not merchant:
            continue

        window = lines[max(0, i - 4): i + 3]
        window_text = " | ".join(window)

        discount_match = re.search(r"(\d+\s?%)", window_text)
        discount = discount_match.group(1) if discount_match else ""

        valid_match = re.search(
            r"(offer\s+valid[^|]*|valid\s+(?:on|until|till|from)[^|]*|book(?:ing)?\s+valid[^|]*)",
            window_text, re.IGNORECASE,
        )
        valid_until = valid_match.group(1).strip() if valid_match else ""

        key = (merchant, line)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "bank": bank,
            "merchant": merchant.title(),
            "title": line,
            "card_types": "",
            "discount": discount,
            "valid_until": valid_until,
            "description": line,
            "url": url,
        })

    return rows


def scrape_combank(logged_date: str | None = None) -> list[dict]:
    logged_date = logged_date or dt.date.today().isoformat()
    text = _get_rendered_text(config.COMBANK_PROMOTIONS_URL, wait_seconds=10)
    rows = _extract_grocery_promos(text, bank="Commercial Bank", url=config.COMBANK_PROMOTIONS_URL)
    for r in rows:
        r["logged_date"] = logged_date
    return rows


def scrape_hnb(logged_date: str | None = None) -> list[dict]:
    logged_date = logged_date or dt.date.today().isoformat()
    # "Shopping" is the category tab that held every grocery-chain promo
    # when this was checked manually; if HNB renames/reorders their tabs
    # this click just silently no-ops and we fall back to whatever's on
    # the default "All Offers" view.
    text = _get_rendered_text(config.HNB_PROMOTIONS_URL, click_text="Shopping",
                               load_more_clicks=3, wait_seconds=10)
    rows = _extract_grocery_promos(text, bank="HNB", url=config.HNB_PROMOTIONS_URL)
    for r in rows:
        r["logged_date"] = logged_date
    return rows


def scrape_sampath(logged_date: str | None = None) -> list[dict]:
    logged_date = logged_date or dt.date.today().isoformat()
    text = _get_rendered_text(config.SAMPATH_URL, wait_seconds=10)
    rows = _extract_grocery_promos(text, bank="Sampath", url=config.SAMPATH_URL)
    for r in rows:
        r["logged_date"] = logged_date
    return rows


def log_manual_promo(*, bank: str, merchant: str, title: str, card_types: str = "",
                      discount: str = "", valid_until: str = "", description: str = "",
                      url: str = "", logged_date: str | None = None) -> dict:
    """Helper for logging a bank promo by hand (e.g. BOC / Peoples' Bank,
    which aren't automated yet — see this module's docstring).

    Example:
        from src.scrapers.creditcards import log_manual_promo
        from src import db
        conn = db.get_connection(); db.init_db(conn)
        db.upsert_credit_card_promo(conn, log_manual_promo(
            bank="BOC", merchant="Cargills",
            title="5% cashback weekdays over Rs 3,000",
            discount="5%", valid_until="2026-12-31",
        ))
    """
    return {
        "logged_date": logged_date or dt.date.today().isoformat(),
        "bank": bank, "merchant": merchant, "title": title,
        "card_types": card_types, "discount": discount,
        "valid_until": valid_until, "description": description, "url": url,
    }


def scrape_all(logged_date: str | None = None) -> list[dict]:
    """Kept for backwards compatibility; run_daily.py now calls each bank
    scraper separately (see CREDIT_CARD_SCRAPERS) so one bank's page
    breaking doesn't take the others down with it."""
    return scrape_seylan(logged_date)


if __name__ == "__main__":
    for name, fn in [("Seylan", scrape_seylan), ("Commercial Bank", scrape_combank),
                     ("HNB", scrape_hnb), ("Sampath", scrape_sampath)]:
        result = fn()
        print(f"{name}: {len(result)} rows")
