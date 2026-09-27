import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

URL = "https://www.seylan.lk/promotions/cards/supermarket/keells"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Remove unwanted sections
for tag in soup.find_all(["header", "footer", "nav", "script", "style"]):
    tag.decompose()

text = soup.get_text("\n", strip=True)

# -------------------------
# Merchant
# -------------------------
merchant = "Keells"

# -------------------------
# Title
# -------------------------
title = ""

h1 = soup.find("h1")
if h1:
    title = h1.get_text(strip=True)

# -------------------------
# Discount
# -------------------------
discount = ""

m = re.search(r'(\d+\s?%)', text)
if m:
    discount = m.group(1)

# -------------------------
# Card Types
# -------------------------
patterns = [
    "Visa Infinite",
    "Visa Signature",
    "Visa Platinum",
    "Visa Gold",
    "World Mastercard",
    "Mastercard World",
    "Mastercard Platinum",
    "Mastercard Freedom",
    "Seylan Premier Credit Cards",
    "Seylan Credit Cards",
    "All Seylan Credit Cards"
]

cards = []

for p in patterns:
    if re.search(p, text, re.IGNORECASE):
        cards.append(p)

cards = list(dict.fromkeys(cards))

# -------------------------
# Valid Until
# -------------------------
valid_until = ""

m = re.search(
    r'Valid\s+(?:until|till)\s*([^\n]+)',
    text,
    re.IGNORECASE
)

if m:
    valid_until = m.group(1).strip()

# -------------------------
# Description
# -------------------------
description = ""

paragraphs = []

for p in soup.find_all("p"):
    txt = p.get_text(" ", strip=True)

    if len(txt) > 30:
        paragraphs.append(txt)

description = "\n".join(paragraphs)

# -------------------------
# DataFrame
# -------------------------
df = pd.DataFrame([{
    "Merchant": merchant,
    "Title": title,
    "Discount": discount,
    "Card Types": ", ".join(cards),
    "Valid Until": valid_until,
    "Description": description,
    "URL": URL
}])

print(df)

# Save to Excel
df.to_excel("keells_promotion.xlsx", index=False)

print("Excel saved as keells_promotion.xlsx")