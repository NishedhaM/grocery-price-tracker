import requests
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# -----------------------------
# 1. GET SESSION (SAME AS YOUR WORKING CODE)
# -----------------------------

options = webdriver.ChromeOptions()
options.add_argument("--headless")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

driver.get("https://www.keellssuper.com/")
time.sleep(6)

cookies_raw = driver.get_cookies()
driver.quit()

cookies = {}
usersessionid = None

for c in cookies_raw:
    cookies[c["name"]] = c["value"]

    if c["name"].startswith("auth_cookie"):
        usersessionid = c["name"].replace("auth_cookie_", "")

print("SESSION:", usersessionid)


# -----------------------------
# 2. API CALL
# -----------------------------

url = "https://zebraliveback.keellssuper.com/2.0/WebV2/GetItemDetails"

headers = {
    "accept": "application/json",
    "origin": "https://www.keellssuper.com",
    "referer": "https://www.keellssuper.com/",
    "user-agent": "Mozilla/5.0",
    "usersessionid": usersessionid
}

params = {
    "pageNo": 1,
    "itemsPerPage": 100,
    "outletCode": "SCDR",
    "departmentId": 16,
    "itemPricefrom": 0,
    "itemPriceTo": 5000,
    "isPromotionOnly": "false"
}

response = requests.get(
    url,
    headers=headers,
    cookies=cookies,
    params=params
)

print("STATUS:", response.status_code)

data = response.json()


# -----------------------------
# 3. EXTRACT ITEMS
# -----------------------------

items = (
    data.get("result", {})
        .get("itemDetailResult", {})
        .get("itemDetails", [])
)

print("ITEMS FOUND:", len(items))


# -----------------------------
# 4. BUILD AI DATASET (PROMOTION CALCULATION)
# -----------------------------

products = []

for item in items:

    price = item.get("amount") or 0

    mrp = item.get("mrp") or item.get("MRP") or 0

    # 🔥 PROMOTION CALCULATION (MOST IMPORTANT PART)
    if mrp and price:
        promo_amount = float(mrp) - float(price)
    else:
        promo_amount = 0

    # optional discount %
    discount_percent = 0
    if mrp and price and mrp > 0:
        discount_percent = round(((mrp - price) / mrp) * 100, 2)

    products.append({

        "Item ID": item.get("itemID"),

        "Code": item.get("itemCode"),

        "Name": item.get("name"),

        "Price": price,

        "MRP": mrp,

        # 🔥 THIS IS YOUR PROMOTION VALUE
        "Promotion Amount": promo_amount,

        "Discount %": discount_percent,

        "Is Promo": item.get("isSponsored") or item.get("isFeatured"),

        "Min Qty": item.get("minQty"),

        "Max Qty": item.get("maxQty"),

        "Image": item.get("imageUrl")

    })


# -----------------------------
# 5. SAVE TO EXCEL
# -----------------------------

df = pd.DataFrame(products)

df.to_excel("keells_with_promotions.xlsx", index=False)

print("DONE ✔")
print("Saved:", len(df), "products")