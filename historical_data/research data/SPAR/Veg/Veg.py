import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

headers = {
    "User-Agent": "Mozilla/5.0"
}

base_url = "https://spar2u.lk/collections/vegetables?page="

products = []

for page in range(1, 4):  # pages 1 to 3
    print(f"Scraping page {page}...")

    url = base_url + str(page)
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed page {page}")
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.select("li.grid__item")

    for card in cards:
        name_tag = card.select_one(".card__heading a")
        name = name_tag.get_text(strip=True) if name_tag else None

        price_tag = card.select_one(".price-item--regular") or card.select_one(".price-item")
        price = None

        if price_tag:
            price = re.sub(r"\s+", " ", price_tag.get_text(strip=True))

        if name and price:
            products.append({
                "Name": name,
                "Price": price,
                "Page": page
            })

# Save to Excel
df = pd.DataFrame(products)
df.to_excel("spar2u_vegetables_all_pages.xlsx", index=False)

print("Done ✔")
print("Total products:", len(df))