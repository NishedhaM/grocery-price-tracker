import requests
import pandas as pd
import time

BASE_URL = "https://glomark.lk/ajax_products_by_department"
DEP_ID = 16  # Vegetables

headers = {
    "x-requested-with": "XMLHttpRequest",
    "user-agent": "Mozilla/5.0"
}

offset = 0
limit = 18

all_products = []
seen_ids = set()

print("🚀 Scraping started...\n")

while True:
    params = {
        "depId": DEP_ID,
        "offset": offset,
        "limit": limit
    }

    try:
        res = requests.get(BASE_URL, params=params, headers=headers)
        data = res.json()

        products = data.get("data", {}).get("products_list", [])

        # 🔥 STOP if API returns nothing
        if not products:
            print("✅ No more products returned. Stopping.")
            break

        new_items = 0

        for item in products:
            pid = item.get("id")

            # 🔥 skip duplicates
            if pid in seen_ids:
                continue

            seen_ids.add(pid)
            new_items += 1

            all_products.append({
                "id": pid,
                "name": item.get("name"),
                "erpCode": item.get("erpCode"),
                "price": item.get("basePrice"),
                "promoPrice": item.get("promoPrice"),
                "hasPromo": item.get("hasPromo"),
                "unit": item.get("unit"),
                "stock": item.get("stock")
            })

        print(f"📦 Offset {offset} → New items: {new_items}")

        # 🔥 MAIN STOP CONDITION
        if new_items == 0:
            print("⚠️ No new items found. Stopping loop.")
            break

        offset += limit
        time.sleep(0.3)

        # 🛑 SAFETY STOP (prevents infinite loops)
        if offset > 50000:
            print("🛑 Safety stop triggered.")
            break

    except Exception as e:
        print("❌ Error:", e)
        break


# =========================
# DATA PROCESSING
# =========================

print("\n📊 Total unique products collected:", len(all_products))

df = pd.DataFrame(all_products)

if df.empty:
    print("❌ No data collected. Excel will not be created.")
    exit()


vegetables_df = df.copy()
promotions_df = df[df["hasPromo"] == True]

# =========================
# SAVE EXCEL
# =========================

output_file = "glomark_vegetables.xlsx"

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    vegetables_df.to_excel(writer, sheet_name="Vegetables", index=False)
    promotions_df.to_excel(writer, sheet_name="Promotions", index=False)

print("\n🎉 DONE!")
print("📁 Excel file saved as:", output_file)