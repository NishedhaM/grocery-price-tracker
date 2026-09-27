import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, /",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": (
        "https://cargillsonline.com/Product/FOOTBALL-FEVER?"
        "CI=MzQ0MA==&CN=Rk9PVEJBTEwgIEZFVkVS&SI=MTA4MQ=="
        "&ST=QmFubmVy&DT=Q29sbGVjdGlvbg=="
    ),
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

# Replace these with the latest values from your browser if the request expires.
cookies = {
    "ASP.NET_SessionId": "YOUR_SESSION_ID",
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
}

# FOOTBALL FEVER collection payload
payload = {
    "CategoryId": "",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 10000,
    "BannerId": "",
    "SectionId": "MTA4MQ==",
    "CollectionId": "MzQ0MA==",
    "SectionType": "QmFubmVy",
    "DataType": "Q29sbGVjdGlvbg==",
    "SubCatId": "-1",
    "PromoId": ""
}

response = requests.post(
    url,
    headers=headers,
    cookies=cookies,
    json=payload,
    timeout=30
)

print("STATUS:", response.status_code)
print("CONTENT-TYPE:", response.headers.get("Content-Type"))

response.raise_for_status()

try:
    data = response.json()
except ValueError:
    print("Response is not JSON:")
    print(response.text[:2000])
    raise

# Find the product list
items = []

if isinstance(data, list):
    items = data

elif isinstance(data, dict):
    items = (
        data.get("Data")
        or data.get("data")
        or data.get("Result")
        or data.get("result")
        or data.get("Items")
        or data.get("items")
        or []
    )

    # Some Cargills API responses have another nested object
    if isinstance(items, dict):
        items = (
            items.get("Items")
            or items.get("items")
            or items.get("Products")
            or items.get("products")
            or items.get("Data")
            or items.get("data")
            or []
        )

if not isinstance(items, list):
    print("Could not identify product list.")
    print(data)
    items = []

print("ITEMS FOUND:", len(items))

# Convert products to Excel rows
products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name") or item.get("ProductName"),
        "SKU": item.get("SKUCODE") or item.get("SKU") or item.get("Sku"),
        "Price": (
            item.get("Price")
            or item.get("SellingPrice")
            or item.get("SalePrice")
            or item.get("MRP")
        ),
        "MRP": item.get("Mrp") or item.get("MRP"),
        "Discount": item.get("DiscountAmount"),
        "Unit": item.get("UnitSize") or item.get("Size"),
        "UOM": item.get("UOM") or item.get("UnitOfMeasure"),
        "Brand": item.get("BrandName") or item.get("Brand"),
        "Available": item.get("IsAvailable") or item.get("Available"),
        "Image": item.get("ImageUrl") or item.get("Image")
    })

df = pd.DataFrame(products)

output_file = "cargills_football_fever.xlsx"
df.to_excel(output_file, index=False)

print(f"DONE ✔️ Exported rows: {len(df)}")
print(f"Saved as: {output_file}")

# Useful for checking exact field names returned by the API
if items:
    print("\nFIRST PRODUCT KEYS:")
    print(list(items[0].keys()))

    print("\nFIRST PRODUCT:")
    print(items[0])