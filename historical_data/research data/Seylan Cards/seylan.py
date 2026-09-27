import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

url = "https://www.seylan.lk/promotions/cards/supermarket/keells-seylan-premier-credit-cards"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

# Get page text
text = soup.get_text("\n", strip=True)

# ---------------- Discount ----------------
discount = ""

m = re.search(r'(\d+\s?%)', text)
if m:
    discount = m.group(1)

# ---------------- Card Type ----------------
patterns = [
    "Visa Infinite",
    "Visa Signature",
    "Visa Platinum",
    "Visa Gold",
    "World Mastercard",
    "Mastercard Platinum",
    "Mastercard Freedom",
    "Seylan Premier Credit Cards",
    "All Seylan Credit Cards"
]

cards = []

for p in patterns:
    if re.search(p, text, re.IGNORECASE):
        cards.append(p)

# remove duplicates
cards = list(dict.fromkeys(cards))

# ---------------- Date ----------------
date = ""

m = re.search(r'Valid until\s*(.*)', text, re.IGNORECASE)
if m:
    date = m.group(1).split("\n")[0].strip()

# ---------------- Description ----------------
description = ""

m = re.search(
    r'Enjoy.*?Cards?(.*?)(?=Valid until)',
    text,
    re.IGNORECASE | re.DOTALL
)

if m:
    description = m.group(0).replace("\n"," ")

# ---------------- Merchant ----------------
merchant = "Keells"

# ---------------- Title ----------------
title = "Keells - Seylan Premier Credit Cards"

# Create dataframe
df = pd.DataFrame([{
    "Merchant": merchant,
    "Title": title,
    "Card Type": ", ".join(cards),
    "Discount": discount,
    "Valid Until": date,
    "Description": description,
    "URL": url
}])

# Save to Excel
df.to_excel("seylan_promotion.xlsx", index=False)

print(df)
print("Excel created successfully!")