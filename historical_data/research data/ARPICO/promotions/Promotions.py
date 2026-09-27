import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://myarpico.com/index.php"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

session = requests.Session()

# Set your store cookies (optional but recommended)
session.cookies.update({
    "selectedStoreId": "2",
    "selectedStoreName": "Kadawatha Super Centre",
    "currency": "LKR"
})

all_products = []

for page in range(1, 5):

    print(f"Scraping page {page}...")

    params = {
        "route": "product/special",
        "language": "en-gb",
        "limit": "100",
        "page": page
    }

    response = session.get(BASE_URL, params=params, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find product cards
    cards = soup.select(".product-thumb")

    print(f"Found {len(cards)} products")

    for card in cards:

        # Product name
        name = ""

        name_tag = (
            card.select_one(".caption h4 a")
            or card.select_one("h4 a")
            or card.select_one(".product-title a")
        )

        if name_tag:
            name = name_tag.get_text(strip=True)

        # Regular price
        regular_price = ""

        old_price = card.select_one(".price-old")
        if old_price:
            regular_price = old_price.get_text(" ", strip=True)

        # Promotion price
        promo_price = ""

        new_price = card.select_one(".price-new")
        if new_price:
            promo_price = new_price.get_text(" ", strip=True)
        else:
            price = card.select_one(".price")
            if price:
                promo_price = price.get_text(" ", strip=True)

        # Discount label
        discount = ""
        badge = card.select_one(".sale, .badge, .discount")
        if badge:
            discount = badge.get_text(strip=True)

        all_products.append({
            "Product Name": name,
            "Regular Price": regular_price,
            "Promotion Price": promo_price,
            "Discount": discount,
            "Page": page
        })

    time.sleep(1)

df = pd.DataFrame(all_products)

print(f"\nTotal products: {len(df)}")

df.to_excel("arpico_promotions.xlsx", index=False)

print("Done!")