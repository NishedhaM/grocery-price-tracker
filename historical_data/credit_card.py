import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------
# BANK URLS
# -------------------------
banks = {
    "DFCC": "https://www.dfcc.lk/cards/dfcc-card-offers/online-promotion",
    "Seylan": "https://www.seylan.lk/promotions",
    "Commercial Bank": "https://www.combank.lk/promotions",
    "HNB": "https://www.hnb.lk/card-promotion",
    "Sampath": "https://www.sampath.lk/personal/cards/promotions"
}

# -------------------------
# KEYWORDS FILTER
# -------------------------
keywords = ["keells", "cargills", "spar", "glomark", "arpico", "supermarket", "food city"]

headers = {"User-Agent": "Mozilla/5.0"}

all_offers = []

# -------------------------
# 1. REQUEST SCRAPER
# -------------------------
def scrape_requests(bank, url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        offers = []

        for tag in soup.find_all(["p", "li", "h2", "h3"]):
            text = tag.get_text(strip=True)
            if text and any(k in text.lower() for k in keywords):
                offers.append({"Bank": bank, "Offer": text})

        return offers

    except Exception as e:
        print(f"Requests failed for {bank}: {e}")
        return []

# -------------------------
# 2. SELENIUM SCRAPER
# -------------------------
def scrape_selenium(bank, url):
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        offers = []
        for tag in soup.find_all(["p", "li", "h2", "h3"]):
            text = tag.get_text(strip=True)
            if text and any(k in text.lower() for k in keywords):
                offers.append({"Bank": bank, "Offer": text})

        driver.quit()
        return offers

    except Exception as e:
        print(f"Selenium failed for {bank}: {e}")
        return []

# -------------------------
# 3. MAIN LOOP
# -------------------------
for bank, url in banks.items():
    print("Scraping:", bank)

    # Step 1: try requests first
    data = scrape_requests(bank, url)

    # Step 2: fallback to selenium if empty
    if not data:
        print("Switching to Selenium for:", bank)
        data = scrape_selenium(bank, url)

    all_offers.extend(data)

# -------------------------
# 4. SAVE TO EXCEL
# -------------------------
df = pd.DataFrame(all_offers)
df.drop_duplicates(inplace=True)

df.to_excel("supermarket_credit_card_offers.xlsx", index=False)

print("DONE ✔ Total Offers Found:", len(df))