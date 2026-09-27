import requests
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# -----------------------------
# 1. GET SESSION
# -----------------------------
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")
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

if not usersessionid:
    raise RuntimeError("Could not extract usersessionid from cookies.")

headers = {
    "accept": "application/json",
    "origin": "https://www.keellssuper.com",
    "referer": "https://www.keellssuper.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "usersessionid": usersessionid
}

url = "https://zebraliveback.keellssuper.com/2.0/Web/GetItemDetails"

# -----------------------------
# 2. PAGINATE VIA fromCount / toCount
# -----------------------------
all_items = []
chunk_size = 50          # how many items to request per call
from_count = 0
max_iterations = 200     # safety valve

for i in range(max_iterations):
    to_count = from_count + chunk_size

    params = {
        "fromCount": from_count,
        "toCount": to_count,
        "outletCode": "SCDR        ",   # site sends trailing spaces — keeping as-is in case API is picky
        "departmentId": "",
        "subDepartmentId": "",
        "categoryId": "",
        "itemDescription": "        ",
        "itemPricefrom": 0,
        "itemPriceTo": 5000,
        "isFeatured": 0,
        "isPromotionOnly": "true        ",
        "promotionCategory": 1,
        "sortBy": "default",
        "BrandId": "",
        "storeName": "        ",
        "subDeaprtmentCode": "ALL",
        "stockStatus": "true",
        "brandName": ""
    }

    resp = requests.get(url, headers=headers, cookies=cookies, params=params)

    if resp.status_code != 200:
        print(f"Stopped at fromCount={from_count}: HTTP {resp.status_code}")
        break

    data = resp.json()
    items = (
        data.get("result", {}).get("itemDetailsList")
        or data.get("result", {}).get("itemDetailResult", {}).get("itemDetails")
        or data.get("result", {}).get("dealsProductsList")
        or []
    )

    print(f"fromCount={from_count} toCount={to_count} -> {len(items)} items")

    if not items:
        print("No more items returned, stopping.")
        break

    all_items.extend(items)
    from_count = to_count
    time.sleep(0.5)  # polite delay

print("\nTOTAL RAW ITEMS COLLECTED:", len(all_items))

# -----------------------------
# 3. BUILD DATASET (de-duplicated)
# -----------------------------
products = []
seen_ids = set()

for item in all_items:
    item_id = item.get("itemID")
    if item_id in seen_ids:
        continue
    seen_ids.add(item_id)

    price = item.get("amount") or 0
    promo_discount = item.get("promotionDiscountValue") or 0
    mrp = price + promo_discount if promo_discount else price
    discount_percent = round((promo_discount / mrp) * 100, 2) if mrp else 0

    products.append({
        "Item ID": item_id,
        "Code": item.get("itemCode"),
        "Name": item.get("name"),
        "Price": price,
        "MRP (est.)": mrp,
        "Promotion Discount Value": promo_discount,
        "Discount %": discount_percent,
        "Is Promotion Applied": item.get("isPromotionApplied"),
        "Department": item.get("departmentCode"),
        "Sub-Department": item.get("subDepartmentCode"),
        "Category": item.get("categoryCode"),
        "Stock In Hand": item.get("stockInHand"),
        "Min Qty": item.get("minQty"),
        "Max Qty": item.get("maxQty"),
        "Available": item.get("isAvailable"),
        "Image": item.get("imageUrl")
    })

df = pd.DataFrame(products)
df.to_excel("keells_promotions_full.xlsx", index=False)
print("DONE ✔")
print(f"Saved {len(df)} unique products to keells_promotions_full.xlsx")