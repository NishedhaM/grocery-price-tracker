import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com", 
    "referer": "https://cargillsonline.com/Product/Fruits?IC=OQ==&NC=RnJ1aXRz",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}

cookies = {
    "ASP.NET_SessionId": "dn1xrw4rvokya4lodobyowzs",
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
}

payload = {
    "CategoryId": "MjM=",
    "Search": "",
    "Filter": "Wwzpa2LygAJqAK1uM94i8A==",
    "PageIndex": 1,
    "PageSize": 100,
    "BannerId": "",
    "SectionId": "",
    "CollectionId": "",
    "SectionType": "",
    "DataType": "",
    "SubCatId": "-1",
    "PromoId": ""
}

response = requests.post(url, headers=headers, cookies=cookies, json=payload)

print("STATUS:", response.status_code)
print("CONTENT-TYPE:", response.headers.get("Content-Type"))

data = response.json()

# -----------------------------
# DEBUG STRUCTURE
# -----------------------------
print(type(data))
# print(data.keys())  # uncomment if needed

# -----------------------------
# HANDLE RESPONSE
# -----------------------------
items = []

# most APIs wrap data like this:
if isinstance(data, dict):
    items = data.get("Data") or data.get("data") or data.get("Result") or []
elif isinstance(data, list):
    items = data

print("ITEMS FOUND:", len(items))

# -----------------------------
# PARSE PRODUCTS (adjust keys if needed)
# -----------------------------
products = []

for item in items:
    products.append({
        "Name": item.get("ItemName") or item.get("Name"),
        "Price": item.get("Price") or item.get("SellingPrice"),
        "SKU": item.get("SKUCODE") or item.get("Sku"),
        "Unit": item.get("UnitSize"),
        "UOM": item.get("UOM")
    })

df = pd.DataFrame(products)
df.to_excel("cargills_products.xlsx", index=False)

print("DONE ✔ Rows:", len(df))