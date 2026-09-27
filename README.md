# Grocery Price Tracker — Automation Kit

Turns the six one-off scraper scripts from your original research project
into one daily job that writes into a single SQLite database with a
consistent schema, satisfying OBJ1's "systematically collect... daily
promotional pricing data" without you running anything by hand.

**Scope for now:** Keells, Cargills/Food City, Arpico for pricing (the
three chains recommended in the revised plan), plus **six** banks for
credit card promos — Seylan, Commercial Bank, HNB, Sampath, BOC, and
People's Bank (see Section 2 for how the last two were added).
Glomark and SPAR pricing data you already collected is imported as
historical rows, but their scrapers aren't wired into the daily job
yet — add them the same way if you decide to bring them back in.

Getting the bank promos required a real rendered browser, not a plain
HTTP request: Commercial Bank's site returns a 403 to a plain fetch
(its own bot-protection), and HNB's promo cards only exist after its
React app runs — a bare `requests.get()` gets nothing for either.
All three (ComBank/HNB/Sampath) run headless Chrome via Selenium for
this reason — the same technique already needed for Keells — which
makes them slower and slightly more fragile than Seylan's plain-HTML
scrape, so treat their output as best-effort and spot check it against
the bank's page occasionally.

## What's inside

```
db/schema.sql            unified table definitions (see comments in the file)
src/config.py             category IDs / endpoints per store — edit here, not in the scraper code
src/scrapers/             one module per store, each returning normalized rows
src/db.py                 SQLite connection + idempotent upsert logic
src/run_daily.py          orchestrator — this is what actually runs each day
scripts/import_historical.py   one-time import of your June–July 2026 snapshots
.github/workflows/daily-scrape.yml   the GitHub Actions schedule
```

## 1. One-time setup

1. Create a **private** GitHub repository and push this folder to it.
   (Private matters — the database will contain your scraped pricing
   data; there's no reason to make it public.)
2. Under the repo's **Settings → Actions → General → Workflow
   permissions**, select "Read and write permissions" — the workflow
   needs to commit the database file back into the repo after each run.
3. `db/grocery_prices.db` already ships pre-populated with your
   20 June – 10 July 2026 snapshots (2,179 price rows + 4 credit-card
   rows — verified against your original files). `historical_data/`
   contains the source files that produced it, kept for
   reproducibility. If you ever need to redo the import (e.g. after
   fixing a mapping), it's:
   ```bash
   pip install -r requirements.txt
   python scripts/import_historical.py
   ```
4. Push the repo. The workflow in `.github/workflows/daily-scrape.yml`
   will start running automatically at 04:00 Asia/Colombo every day.
   You can also trigger it immediately from the repo's **Actions** tab
   → "Daily grocery price scrape" → **Run workflow**, which is the
   fastest way to check it actually works before waiting for the
   overnight run.

## 2. Things that will need attention (read this before you trust the data)

- **Cargills promo collection IDs rotate.** `mega_discount`,
  `super_cart_savings`, `super_baby_shop` and `football_fever` in
  `src/config.py` are seasonal campaigns — Cargills swaps them out every
  few weeks. When one starts returning 0 items, open the live banner on
  cargillsonline.com, check your browser's Network tab, and copy the new
  CI/SI/CN values into `config.py` the same way the original scripts
  captured them.
- **Keells needs a live browser cookie.** `src/scrapers/keells.py` spins
  up headless Chrome once per run to mint a session cookie before
  calling the JSON API. GitHub's `ubuntu-latest` runners ship Chrome
  pre-installed, so this should work out of the box — but run it once
  via **Actions → Run workflow** and check the log before assuming it's
  reliable long-term.
- **All six banks are automated now (Seylan, Commercial Bank, HNB,
  Sampath, BOC, People's Bank).** The original generic scraper
  (`credit_card.py` in your old project) tried five banks with a plain
  HTTP client and found just 2 offers total — this kit gets real,
  structured supermarket-specific promos from all of them by using a
  real browser for the three that need JS to render (ComBank/HNB/Sampath)
  and finding each bank's *current* promotions URL, since two of the
  URLs in the old script were stale (`combank.lk/promotions` 404s now —
  the live page moved to `combank.lk/rewards-promotions`;
  `sampath.lk/personal/cards/promotions` 404s too — Sampath's promos
  live in its homepage carousel instead, which is what
  `scrape_sampath()` reads). BOC and People's Bank were added 27 Sept
  2026 — both have a dedicated supermarket-offers page that's plain
  server-rendered HTML, so their scrapers use `requests` directly
  rather than Selenium (`config.BOC_SUPERMARKETS_URL`,
  `config.PEOPLESBANK_SUPERMARKETS_URL`). `log_manual_promo()` in
  `src/scrapers/creditcards.py` is still there if you ever need to log
  a promo by hand for a bank not in this list. To add another Seylan
  merchant page, find its URL under
  seylan.lk/promotions/cards/supermarket/ and add it to
  `SEYLAN_PROMO_PAGES` in `config.py`.
- **The Commercial Bank / HNB / Sampath parser is a generic keyword
  scanner, not a bespoke parser per site** (`_extract_grocery_promos`
  in `creditcards.py`): it looks for lines mentioning a grocery chain
  and pulls the nearest discount % and "valid..." date from the
  surrounding lines. This is deliberately blunter than parsing each
  site's exact HTML structure, so it survives markup changes better,
  but it means `card_types` isn't populated for these three banks
  (only for Seylan) — only discount, a rough valid-date string, and
  the promo's description line. If a row looks wrong, check it
  against the live page before trusting it in analysis.
- **HNB's scraper depends on a category tab click that could break.**
  `scrape_hnb()` clicks the tab labelled "Shopping" before reading the
  page, because that's where every grocery-chain promo showed up when
  this was checked manually — if HNB renames or reorders that tab, the
  click silently no-ops and you'll get whatever's on the default view
  instead (check `run_log` for a suspiciously low row count).
- **Arpico's item catalog (non-promo prices) isn't scraped yet** — only
  its promotions page was ever captured in the original project. See
  the docstring in `src/scrapers/arpico.py` for how to add it once
  you've found the equivalent catalog endpoint.
- **A mislabeling bug in the old data, now fixed:** the original
  `keells_scraper.py` (project root) actually called
  `cargillsonline.com`, not `keellssuper.com` — it was Cargills data
  saved under a Keells filename. Likewise
  `research data/ARPICO/Veg/Veg.py` called `spar2u.lk`, not Arpico. Both
  are correctly attributed in `import_historical.py` and in the new
  scrapers; just don't reuse the old filenames as a guide to what
  store they actually contain.

## 3. Running it locally instead of / in addition to GitHub Actions

```bash
python -m src.run_daily                       # scrape all three stores for today
python -m src.run_daily --stores keells        # just one store
python -m src.run_daily --date 2026-09-10      # backfill a specific date, e.g. after a missed run
```

Every run — success or failure, per store — is recorded in the
`run_log` table, so you can check for gaps in your daily series with:

```sql
SELECT scrape_date, store, COUNT(*) FROM price_snapshots GROUP BY scrape_date, store ORDER BY scrape_date;
```

## 4. What's deliberately NOT in this kit

Cross-store product matching (the same "Anchor Full Cream Milk 1L" vs
"Anchor Milk 1 Litre" problem the proposal describes) and the ILP
optimization model are Phase B work in the revised plan, not part of
daily collection — build those against the data this kit accumulates,
once a few weeks of history exist.
