import requests
import pandas as pd

url = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"

headers = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://cargillsonline.com",
    "referer": "https://cargillsonline.com/Product/Vegetables?IC=MjM=&NC=VmVnZXRhYmxlcw==",
    "user-agent": "Mozilla/5.0",
}

cookies = {
    "ASP.NET_SessionId": "vma3gsxqq3kkbo3wdpqmuciq",
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
}

payload = {
    "CategoryId": "MjM=",
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
    json=payload
)

print("STATUS:", response.status_code)

data = response.json()

# ---------------------------
# normalize response
# ---------------------------
if isinstance(data, dict):
    items = data.get("Data", [])
elif isinstance(data, list):
    items = data
else:
    items = []

products = []

for item in items:
    products.append({
        "Name": item.get("ItemName"),
        "Price": item.get("Price"),
        "SKU": item.get("SKUCODE"),
        "Unit": item.get("UnitSize"),
        "UOM": item.get("UOM")
    })

df = pd.DataFrame(products)

df.to_excel("keells_products.xlsx", index=False)

print("DONE - Rows:", len(df))