"""
Store-specific configuration, pulled out of code so you can add or
refresh categories without touching the scraper logic.

IMPORTANT — two different kinds of Cargills IDs:

* CARGILLS_CATALOG_CATEGORIES are stable product departments
  (Vegetables, Fruits, ...). These rarely change.
* CARGILLS_PROMO_COLLECTIONS are seasonal marketing banners
  (Mega Discount, Super Cart Savings, ...). Cargills rotates these
  every few weeks, so the CollectionId values below WILL go stale.
  When a collection stops returning items, open the corresponding
  banner on cargillsonline.com, open your browser's dev tools
  Network tab, click the banner, and copy the fresh CI/SI/CN values
  out of the request URL the same way the original research scripts
  did (see Figure 1 / Figure 3 style captures in the proposal).
"""

CARGILLS_BASE_URL = "https://cargillsonline.com/Web/GetMenuCategoryItemsPagingV3/"
CARGILLS_HOME_URL = "https://cargillsonline.com/"

CARGILLS_CATALOG_CATEGORIES = [
    {
        "key": "vegetables",
        "category_id": "MjM=",
        "referer": "https://cargillsonline.com/Product/Vegetables?IC=MjM=&NC=VmVnZXRhYmxlcw==",
    },
    {
        "key": "fruits",
        "category_id": "OQ==",
        "referer": "https://cargillsonline.com/Product/Fruits?IC=OQ==&NC=RnJ1aXRz",
    },
]

# section_id "MTA4MQ==" is the generic banner section; collection_id
# identifies the specific promotional campaign.
CARGILLS_PROMO_COLLECTIONS = [
    {
        "key": "mega_discount",
        "section_id": "MTA4MQ==",
        "collection_id": "MzQzNQ==",
        "referer": "https://cargillsonline.com/Product/Mega-Discount?CI=MzQzNQ==&CN=TWVnYSBEaXNjb3VudA==&SI=MTA4MQ==&ST=QmFubmVy&DT=Q29sbGVjdGlvbg==",
    },
    {
        "key": "super_cart_savings",
        "section_id": "MTA4MQ==",
        "collection_id": "MzQ0Mg==",
        "referer": "https://cargillsonline.com/Product/SUPER-CART-SAVINGS?CI=MzQ0Mg==&CN=U1VQRVIgQ0FSVCBTQVZJTkdT&SI=MTA4MQ==&ST=QmFubmVy&DT=Q29sbGVjdGlvbg==",
    },
    {
        "key": "super_baby_shop",
        "section_id": "MTA4MQ==",
        "collection_id": "MzQ0NQ==",
        "referer": "https://cargillsonline.com/Product/Super-Baby-Shop?CI=MzQ0NQ==&CN=U3VwZXIgQmFieSBTaG9w&SI=MTA4MQ==&ST=QmFubmVy&DT=Q29sbGVjdGlvbg==",
    },
    {
        # NOTE: the file in the original zip was named "fathers day.xlsx"
        # but its own referer URL is FOOTBALL-FEVER — the two campaigns
        # got mixed up when the script was saved. Rename/verify against
        # the live site before trusting this one.
        "key": "football_fever",
        "section_id": "MTA4MQ==",
        "collection_id": "MzQ0MA==",
        "referer": "https://cargillsonline.com/Product/FOOTBALL-FEVER?CI=MzQ0MA==&CN=Rk9PVEJBTEwgIEZFVkVS&SI=MTA4MQ==&ST=QmFubmVy&DT=Q29sbGVjdGlvbg==",
    },
]

# Non-secret store/location settings Cargills expects as cookies.
CARGILLS_STATIC_COOKIES = {
    "ASP.NET_Pincode": "Colombo",
    "ASP.NET_WebStoreType": "1",
    "Asp.Net_WebStoreId": "1031",
}

KEELLS_HOME_URL = "https://www.keellssuper.com/"
KEELLS_API_URL = "https://zebraliveback.keellssuper.com/2.0/WebV2/GetItemDetails"
# Department IDs seen in the original scripts; add more as you identify them
# from the site's own category menu.
KEELLS_DEPARTMENTS = [
    {"key": "vegetables_fruits", "department_id": 16},
]
KEELLS_OUTLET_CODE = "SCDR"

ARPICO_PROMOTIONS_URL = "https://myarpico.com/index.php"
ARPICO_STORE_COOKIES = {
    "selectedStoreId": "2",
    "selectedStoreName": "Kadawatha Super Centre",
    "currency": "LKR",
}
ARPICO_PROMO_PAGES = 5  # how many result pages of route=product/special to walk

# --- Credit card promotions (OBJ2) ---
#
# Seylan publishes one static page per merchant under
# /promotions/cards/supermarket/<slug> — this is the only bank whose
# promo pages the original project actually got usable data from
# (Commercial Bank, HNB, Sampath, BOC, DFCC are mostly JS-rendered or
# login-gated; see src/scrapers/creditcards.py's docstring). Only the
# Keells page is confirmed working below. To add Cargills/Arpico
# coverage, find their equivalent URL on seylan.lk the same way — visit
# the bank's supermarket promotions section and copy the merchant slug.
SEYLAN_PROMO_PAGES = [
    {"merchant": "Keells", "url": "https://www.seylan.lk/promotions/cards/supermarket/keells"},
    {"merchant": "Keells", "url": "https://www.seylan.lk/promotions/cards/supermarket/keells-seylan-premier-credit-cards"},
]

# Confirmed live 6 Sept 2026 by loading each page in a real browser.
# The URLs in the original credit_card.py (project root) were stale —
# combank.lk/promotions and sampath.lk/.../promotions both 404/403'd;
# these are the current ones.
COMBANK_PROMOTIONS_URL = "https://www.combank.lk/rewards-promotions"
HNB_PROMOTIONS_URL = "https://www.hnb.lk/card-promotion"
SAMPATH_URL = "https://www.sampath.lk"  # promos are in the homepage's "Latest Card Promotions" carousel

# Confirmed live 27 Sept 2026 by loading each page in a real browser.
# Both of these are plain server-rendered pages (no JS needed to see the
# offer cards), unlike ComBank/HNB/Sampath above, so their scrapers use
# a plain requests.get() rather than Selenium.
BOC_SUPERMARKETS_URL = "https://www.boc.lk/personal-banking/card-offers/supermarkets"
# ?cardType=credit_card filters out the separate debit-card list on the same page.
PEOPLESBANK_SUPERMARKETS_URL = "https://www.peoplesbank.lk/promotion-category/supermarkets/?cardType=credit_card"

GROCERY_KEYWORDS = ["cargills", "food city", "keells", "arpico", "glomark", "spar", "laugfs"]
