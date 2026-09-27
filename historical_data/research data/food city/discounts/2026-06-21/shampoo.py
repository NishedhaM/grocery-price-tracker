import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, /",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": (
        "https://cargillsonline.com/Product/Mega-Discount?"
        "CI=MzQzNQ==&CN=TWVnYSBEaXNjb3VudA==&SI=MTA4MQ=="
        "&ST=QmFubmVy&DT=Q29sbGVjdGlvbg=="
    ),
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

cookies = {
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
    "ASP.NET_SessionId": "f2vzsq3dm3e5uozimmbmsw2g",
    "AuthToken": "aab83676-88bd-459b-a754-211583c98afc",
    "WSTAPWS": "WSTAPWS=1",
}

payload = {
    "CategoryId": "",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 10000,
    "BannerId": "",
    "SectionId": "MTA4MQ==",
    "CollectionId": "MzQzNQ==",
    "SectionType": "QmFubmVy",
    "DataType": "Q29sbGVjdGlvbg==",
    "SubCatId": "-1",
    "PromoId": ""
}

response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=30)

print("STATUS:", response.status_code)
print("CONTENT-TYPE:", response.headers.get("Content-Type"))

response.raise_for_status()

data = response.json()

# -----------------------------
# Extract items safely
# -----------------------------
items = []

if isinstance(data, dict):
    items = data.get("Data") or data.get("data") or data.get("Result") or []

    if isinstance(items, dict):
        items = (
            items.get("Items")
            or items.get("Products")
            or items.get("data")
            or []
        )

elif isinstance(data, list):
    items = data

print("ITEMS FOUND:", len(items))

# Debug first item structure
if items:
    print("\nFIRST ITEM KEYS:")
    print(items[0].keys() if isinstance(items[0], dict) else items[0])

# Convert to dataframe
products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name") or item.get("ProductName"),
        "SKU": item.get("SKUCODE") or item.get("SKU"),
        "Price": item.get("Price") or item.get("SellingPrice"),
        "MRP": item.get("MRP") or item.get("Mrp"),
        "Discount": item.get("DiscountAmount"),
        "Unit": item.get("UnitSize"),
        "UOM": item.get("UOM"),
        "Brand": item.get("BrandName"),
        "Image": item.get("ImageUrl") or item.get("Image"),
        "Available": item.get("IsAvailable")
    })

df = pd.DataFrame(products)

output_file = "cargills_mega_discount.xlsx"
df.to_excel(output_file, index=False)

print(f"DONE ✔️ Exported {len(df)} products")
print(f"Saved as: {output_file}")