import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, /",
    "accept-language": "en-US,en;q=0.9,nb;q=0.8,sv;q=0.7",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": (
        "https://cargillsonline.com/Product/Super-Baby-Shop?"
        "CI=MzQ0NQ==&CN=U3VwZXIgQmFieSBTaG9w&SI=MTA4MQ=="
        "&ST=QmFubmVy&DT=Q29sbGVjdGlvbg=="
    ),
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
    ),
}

# Only the ASP.NET cookies are usually necessary.
# Update ASP.NET_SessionId if it expires.
cookies = {
    "ASP.NET_SessionId": "sag03fnwvtx2rrg0ioejofiz",
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
}

# Payload copied from the Super Baby Shop cURL request
payload = {
    "CategoryId": "",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 10000,
    "BannerId": "",
    "SectionId": "MTA4MQ==",
    "CollectionId": "MzQ0NQ==",
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

print("RESPONSE TYPE:", type(data))

if isinstance(data, dict):
    print("TOP-LEVEL KEYS:", list(data.keys()))

# Extract product array safely
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

    # Handle nested API response structures
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
    print("Could not find product list. Full response:")
    print(data)
    items = []

print("ITEMS FOUND:", len(items))

# Convert API items into Excel rows
products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name") or item.get("ProductName"),
        "SKU": item.get("SKUCODE") or item.get("Sku") or item.get("SKU"),
        "Price": (
            item.get("Price")
            or item.get("SellingPrice")
            or item.get("SalePrice")
            or item.get("MRP")
        ),
        "Unit": item.get("UnitSize") or item.get("Size"),
        "UOM": item.get("UOM") or item.get("UnitOfMeasure"),
        "Brand": item.get("BrandName") or item.get("Brand"),
        "Available": item.get("IsAvailable") or item.get("Available"),
        "Image": item.get("ImageUrl") or item.get("Image")
    })

df = pd.DataFrame(products)

output_file = "cargills_super_baby_shop.xlsx"
df.to_excel(output_file, index=False)

print(f"DONE ✔️ Rows exported: {len(df)}")
print(f"Saved file: {output_file}")

# Helpful for identifying the correct product keys
if items:
    print("\nFIRST ITEM KEYS:")
    print(list(items[0].keys()))

    print("\nFIRST ITEM:")
    print(items[0])