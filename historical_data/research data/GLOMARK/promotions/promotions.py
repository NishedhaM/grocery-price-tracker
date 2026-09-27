import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

URL = "https://glomark.lk/deal-page"

headers = {
    "user-agent": "Mozilla/5.0",
    "accept": "text/html,application/xhtml+xml"
}

res = requests.get(URL, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

products = []

# each product block
items = soup.select("div.product-box")

print(f"Found {len(items)} products")

for item in items:
    try:
        # product link
        a_tag = item.select_one("a[href*='/p/']")
        if not a_tag:
            continue

        product_url = "https://glomark.lk" + a_tag["href"]

        # product id from URL
        match = re.search(r"/p/(\d+)", product_url)
        product_id = match.group(1) if match else None

        # name
        name_tag = item.select_one("span.light-font")
        name = name_tag.text.strip() if name_tag else None

        # image
        img_tag = item.select_one("img.prod-img")
        image = img_tag["src"] if img_tag else None

        # price
        price_tag = item.select_one("strong.clr-txt")
        price = price_tag.text.strip() if price_tag else None

        # old price
        old_price_tag = item.select_one("strike.promo-price")
        old_price = old_price_tag.text.strip() if old_price_tag else None

        # discount
        discount_tag = item.select_one(".topleft-discount-rate span")
        discount = discount_tag.text.strip() if discount_tag else None

        products.append({
            "id": product_id,
            "name": name,
            "price": price,
            "old_price": old_price,
            "discount": discount,
            "image": image,
            "url": product_url
        })

    except Exception as e:
        print("Error:", e)

# save to Excel
df = pd.DataFrame(products)
df.to_excel("glomark_deals.xlsx", index=False)

print("✅ Excel saved: glomark_deals.xlsx")