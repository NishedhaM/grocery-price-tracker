import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, /",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": "https://cargillsonline.com/Product/Fruits?IC=OQ==&NC=RnJ1aXRz",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

# Use your CURRENT browser cookies.
# AuthToken and ASP.NET_SessionId may expire, so replace them when needed.
cookies = {
    "ASP.NET_SessionId": "dn1xrw4rvokya4lodobyowzs",
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
    "AuthToken": "ff825d06-7837-4586-b065-969fc2fc862e",
}

# Payload copied from your provided cURL request
payload = {
    "CategoryId": "OQ==",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 10000,
    "BannerId": "",
    "SectionId": "",
    "CollectionId": "",
    "SectionType": "",
    "DataType": "",
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

# Show response text if API returns an error page or invalid JSON
if response.status_code != 200:
    print("ERROR RESPONSE:")
    print(response.text[:1000])
    response.raise_for_status()

try:
    data = response.json()
except ValueError:
    print("Response is not JSON:")
    print(response.text[:1000])
    raise

print("RESPONSE TYPE:", type(data))

# Inspect API structure
if isinstance(data, dict):
    print("TOP-LEVEL KEYS:", data.keys())

# Extract item list from likely API response formats
items = []

if isinstance(data, list):
    items = data

elif isinstance(data, dict):
    # Common wrapper possibilities
    items = (
        data.get("Data")
        or data.get("data")
        or data.get("Result")
        or data.get("result")
        or data.get("Items")
        or data.get("items")
        or []
    )

    # Sometimes Data itself is another object containing items
    if isinstance(items, dict):
        items = (
            items.get("Items")
            or items.get("items")
            or items.get("Data")
            or items.get("data")
            or []
        )

if not isinstance(items, list):
    print("Could not find a product list. Raw response:")
    print(data)
    items = []

print("ITEMS FOUND:", len(items))

# Convert product records into Excel-friendly format
products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name") or item.get("ProductName"),
        "Price": (
            item.get("Price")
            or item.get("SellingPrice")
            or item.get("SalePrice")
            or item.get("MRP")
        ),
        "SKU": item.get("SKUCODE") or item.get("Sku") or item.get("SKU"),
        "Unit": item.get("UnitSize") or item.get("Size"),
        "UOM": item.get("UOM") or item.get("UnitOfMeasure"),
        "Brand": item.get("BrandName") or item.get("Brand"),
        "Available": item.get("IsAvailable") or item.get("Available")
    })

df = pd.DataFrame(products)

output_file = "cargills_fruits_products.xlsx"
df.to_excel(output_file, index=False)

print(f"DONE ✔️ Rows exported: {len(df)}")
print(f"Saved as: {output_file}")

# Optional: see all fields returned by the first product
if items:
    print("\nFIRST PRODUCT RAW DATA:")
    print(items[0])