import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, /",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": (
        "https://cargillsonline.com/Product/SUPER-CART-SAVINGS?"
        "CI=MzQ0Mg==&CN=U1VQRVIgQ0FSVCBTQVZJTkdT&SI=MTA4MQ=="
        "&ST=QmFubmVy&DT=Q29sbGVjdGlvbg=="
    ),
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

# Copy fresh cookie values from your browser when the session expires.
cookies = {
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
    "ASP.NET_SessionId": "f2vzsq3dm3e5uozimmbmsw2g",
    "WSTAPWS": "WSTAPWS=1",
    "AuthToken": "aab83676-88bd-459b-a754-211583c98afc",
}

payload = {
    "CategoryId": "",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 10000,
    "BannerId": "",
    "SectionId": "MTA4MQ==",
    "CollectionId": "MzQ0Mg==",
    "SectionType": "QmFubmVy",
    "DataType": "Q29sbGVjdGlvbg==",
    "SubCatId": "-1",
    "PromoId": ""
}

with requests.Session() as session:
    session.headers.update(headers)
    session.cookies.update(cookies)

    response = session.post(url, json=payload, timeout=30)

print("STATUS:", response.status_code)
print("CONTENT-TYPE:", response.headers.get("Content-Type"))

# Print the server response before raising an exception
if not response.ok:
    print("ERROR RESPONSE:")
    print(response.text[:3000])
    response.raise_for_status()

try:
    data = response.json()
except ValueError:
    print("Response is not JSON:")
    print(response.text[:3000])
    raise

print("RESPONSE TYPE:", type(data))

if isinstance(data, dict):
    print("TOP-LEVEL KEYS:", list(data.keys()))

# Cargills API commonly returns the products under Data
items = []

if isinstance(data, dict):
    items = data.get("Data", [])

    # If Data is an object, locate its actual item list
    if isinstance(items, dict):
        items = (
            items.get("Items")
            or items.get("Products")
            or items.get("ItemList")
            or []
        )

elif isinstance(data, list):
    items = data

if not isinstance(items, list):
    print("Unexpected response structure:")
    print(data)
    items = []

print("ITEMS FOUND:", len(items))

# Print one raw item first, so you can confirm the API's field names
if items:
    print("\nFIRST RAW ITEM:")
    print(items[0])

products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name"),
        "SKU": item.get("SKUCODE") or item.get("SKU"),
        "Price": item.get("Price") or item.get("SellingPrice"),
        "MRP": item.get("MRP") or item.get("Mrp"),
        "Discount": item.get("DiscountAmount"),
        "Unit": item.get("UnitSize"),
        "UOM": item.get("UOM"),
        "Brand": item.get("BrandName"),
        "Available": item.get("IsAvailable"),
        "Image": item.get("ImageUrl") or item.get("Image")
    })

df = pd.DataFrame(products)

output_file = "cargills_super_cart_savings.xlsx"
df.to_excel(output_file, index=False)

print(f"\nDONE ✔️ Exported {len(df)} products")
print(f"Saved as: {output_file}")