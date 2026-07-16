# MF holdings traction screener

**Personal project** for a practical day-to-day workflow: scan **recent mutual fund portfolio activity** across many schemes, **spot names where institutions are moving together (or disagreeing)**, and check whether price has already run vs a **month-end 30d SMA**—not as a buy/sell signal, but as a sanity check against chasing after funds have built positions.

In practice it helps you:

- **Prioritize reading** — rank stocks by cross-fund share/weight changes and continued ownership instead of opening dozens of factsheets.
- **See consensus vs debate** — filters for adds-only, reduces-only, new entries, and **mixed** signals.
- **Breadth vs intensity** — sort by traction score or by **how many funds** touch the same name.
- **Link to research** — NSE tickers open [Screener.in](https://www.screener.in) consolidated pages when mapped.
- **Price context** — month high/low, **30d SMA**, current close, and **% vs SMA** (primary UI metric).
- **Monthly triage** — grounded insights + top-traction shortlist (rules offline; optional Gemini wordsmithing).

Anyone tracking **Indian equity MF holdings** can reuse the same pipeline: ingest from RupeeVest, point the CLI at a local data folder, regenerate JSON/CSV/HTML.

### Snapshot: top-100 backtest (Apr–Jun 2026)

Equal-weight return of the **top 100 by traction score**, buying at **month-end Close** (when disclosures land) and marking to **latest Close** (refresh 2026-07-16):

| Month | Priced | Equal-weight | Median | Win rate |
|-------|--------|--------------|--------|----------|
| April 2026 | 96/100 | **+9.7%** | +5.1% | 68.8% |
| May 2026 | 98/100 | **+6.5%** | +5.8% | 74.5% |
| June 2026 | 99/100 | **+1.7%** | +1.3% | 61.6% |

April score↔return correlation **+0.25**. June’s smaller move is expected (shorter hold from month-end to the refresh date). Full write-up, rank buckets, and winners: [`docs/backtest-apr-may-june-2026.md`](docs/backtest-apr-may-june-2026.md).

---

## Data stays outside the repo

This repository is **code + config only**. Fund CSVs and generated reports are **not** committed.

Use a separate directory on your machine (example: `~/mf-data`):

```text
~/mf-data/
  funds/                           # source fund CSVs (one folder per month)
    june/
      helios_small_cap_06_26.csv
      ...
  reports/                         # generated artifacts (typed subfolders)
    json/
      june_traction.json
      june_insights.json
    csv/
      june_traction.csv
    html/
      june_traction.html
      traction.html                # combined multi-month UI
    backtests/
      june_top100_backtest.json
      june_top100_backtest_summary.json
    watchlist.json
    cache/
      prices_2026-06.json
```

Local repo runs use the same layout under `output/` (`output/json/`, `output/html/`, …). Source fund CSVs stay in `funds/`.

The JSON/HTML `meta.folder` field records the **absolute path** to the fund folder used for that run.

---

## Ingest fund reports (RupeeVest)

Holdings CSVs match RupeeVest’s [MF Portfolio Tracker](https://www.rupeevest.com/Mutual-Fund-Portfolio-Tracker) **Download** format. Ingestion uses the site’s JSON API—no browser automation.

```bash
python3 scripts/download_rupeevest_funds.py --dry-run \
  --funds-file config/rupeevest_funds.example.txt

python3 scripts/download_rupeevest_funds.py \
  --funds-file config/rupeevest_funds.example.txt \
  --out-dir ~/mf-data/funds/june \
  --delay 1.0 \
  --overwrite
```

Existing CSVs in ``--out-dir`` are skipped unless ``--overwrite`` is set (no unnecessary tracker calls).

**CSV formats**

- **Equity Holdings** (RupeeVest): multi-month `% of AUM` and `No. of Shares`; **first month = current**, **second = previous**.
- **Trendlyne** (legacy): `Invested In`, `NSE Code`, `% of Total Holding`, `Month Change in Shares %`, etc.

---

## Install

```bash
cd /path/to/cross-fund-holdings-traction
pip install -e .
# or: pip install -e ".[dev]"  for pytest
```

Or without install:

```bash
pip install yfinance pandas
export PYTHONPATH=src
```

Entry points: `mf-screener` (screen) and `mf-screener-month` (full month pipeline).

---

## GitHub Actions → GitHub Pages

Workflow: [`.github/workflows/monthly-report.yml`](.github/workflows/monthly-report.yml)

Automates **RupeeVest ingest → `month_run` → HTML**, then publishes `_site/` (with `index.html` = `traction.html`) to the **`gh-pages`** branch.

### One-time setup

1. **Pages:** Repo **Settings → Pages → Build and deployment**
   - **Source:** Deploy from a branch  
   - **Branch:** `gh-pages` / `(root)`  
   - Do **not** use `/docs` on `main` (that folder is for markdown notes only and has no `index.html`).
2. **Visibility:** Pages is free for **public** repos. Private repos need GitHub Pro/Team (or make the repo public).
3. **Optional Gemini:** **Settings → Secrets and variables → Actions** → add `GEMINI_API_KEY`. Omit for rules-only insights.

### Run it

1. **Actions → Monthly traction report → Run workflow**
2. Choose the branch (feature branch is fine for a first test; merge to `main` for the monthly schedule).
3. Inputs:

| Input | Default | Meaning |
|-------|---------|---------|
| `month` | *(previous UTC month)* | Folder slug, e.g. `june`. Empty → prior month (disclosure lag). |
| `overwrite_funds` | on | Re-download CSVs from RupeeVest |
| `refresh_prices` | on | Refresh yfinance prices |
| **Deploy HTML to GitHub Pages** | **on** | Push built HTML to `gh-pages` |

4. Leave deploy checked. For a known month, set **month** explicitly (e.g. `june`).

**Schedule:** `03:00 UTC` on the **5th** of each month (always deploys). Cron only runs from the default branch (`main`).

**Site URL:** `https://rushankjhanjaria.github.io/cross-fund-holdings-traction/` (`index.html` = combined `traction.html`).

### If you see “File not found” / no index.html

1. Confirm Pages branch is **`gh-pages` / (root)** — not `main` `/docs`.
2. Open the latest **Monthly traction report** run and confirm the **Deploy to gh-pages branch** step is green.
3. In the repo, open the **`gh-pages`** branch and check that `index.html` exists at the root.
4. Hard-refresh the site URL (CDN can lag 1–2 minutes).

---

## Recommended: one-shot month pipeline

Builds scores, enriches prices, writes JSON/CSV/HTML, generates insights, and refreshes combined `traction.html`:

```bash
PYTHONPATH=src python3 -m mf_screener.month_run \
  --folder ~/mf-data/funds/june \
  --out-dir ~/mf-data/reports \
  --refresh-prices
```

Omit `--refresh-prices` to reuse the price cache. Use `--no-gemini` for rules-only insights, or set `GEMINI_API_KEY` for optional narration.

---

## Screen only (CLI)

```bash
python -m mf_screener \
  --folder ~/mf-data/funds/june \
  --enrich-prices \
  --out ~/mf-data/reports/json/june_traction.json \
  --top 50
```

`--out` also writes **CSV** under `csv/` and **HTML** under `html/`, and refreshes combined `html/traction.html` in the same reports root (a flat `…/june_traction.json` path is accepted and remapped into this layout).

```bash
open ~/mf-data/reports/html/traction.html
```

### Report rules

Only stocks where at least one fund **bought, sold, closed, or newly entered**. Hold-only names are excluded unless `--include-holds`.

| Filter | Shows stocks where… |
|--------|---------------------|
| All | Entire report set |
| Added only | Adds/new, **no** fund reduced |
| Reduced only | Trims/closed, **no** fund added |
| New only | At least one `New` position |
| Mixed | ≥2 of adding / reducing / unchanged |
| Still adding | MoM: adding again after prior adds (≥2 months) |
| Reversed | MoM: flipped add↔reduce vs prior month |
| New this month | Not in the prior month report |
| Watchlist | Pinned names (file + browser pins) |

Sort by traction score (default) or **Most funds**. Cards show **30d SMA** and **vs 30d SMA %**.

### Persistence & watchlist

Two or more `json/*_traction.json` files under the same reports root enable MoM badges. Combined HTML auto-merges a watchlist (manual pins preserved).

```bash
python3 scripts/manage_watchlist.py --reports-dir ~/mf-data/reports list
```

### Grounded insights

Monthly **triage** from report fields only: **Top traction** shortlist plus narrative cards (**still early** = multi-fund adds while price ≤ ~5% vs SMA, **exit pressure**, **debate**, **watchlist deltas**). Rules-only works offline; Gemini is optional.

```bash
python3 -m mf_screener.insights --report ~/mf-data/reports/json/june_traction.json --no-gemini
# optional rebuild if you ran insights outside month_run:
python3 scripts/embed_report_ui.py ~/mf-data/reports
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for module layout.

---

## Name → NSE map

Runtime: **[`config/name_to_nse.csv`](config/name_to_nse.csv)** (generated). Exceptions: **[`config/nse_manual_overrides.csv`](config/nse_manual_overrides.csv)**.

```bash
python3 scripts/build_name_to_nse.py --funds ~/mf-data/funds --report-unmapped
```

---

## Price enrichment fields

Report month from folder (`june` → `06`) + filenames (`*_06_26.csv` → `2026-06`).

| Field | Meaning |
|--------|---------|
| `month_high` / `month_low` | Month range (context) |
| `month_end_close` | Last Close of the report month |
| `sma_30` | 30d SMA as of month-end |
| `close_latest` | Latest Close |
| `pct_vs_sma` | **Primary UI** — current vs 30d SMA |
| `estimated_entry_mid` / `pct_vs_entry_mid` | Band mid (legacy / analysis) |

Cache: `{reports}/cache/prices_YYYY-MM.json` (or repo `output/cache/` when using local `month_run`).

---

## Top-100 backtest

```bash
PYTHONPATH=src python3 scripts/top100_backtest.py --report ~/mf-data/reports/json/june_traction.json
```

- **Buy** = last trading-day Close of the disclosure month  
- **Exit** = latest Close in the Yahoo history  
- Writes `backtests/{month}_top100_backtest.json` + `_summary.json`

Results for Apr–Jun 2026: [`docs/backtest-apr-may-june-2026.md`](docs/backtest-apr-may-june-2026.md).

---

## Metrics (composite score)

| Signal | Meaning |
|--------|---------|
| **Share change %** | Primary activity (adds/trims); `New` = first-time holding |
| **Weight delta (pp)** | Allocation vs fund NAV (conviction) |
| **Hold breadth** | Funds still holding with unchanged shares |

```text
(breadth_active × breadth_bonus)
+ (breadth_active × log1p(median_share_change_pct) × share_weight)   # positive share only
+ (breadth_weight_up × median_weight_delta_pp × weight_scale)
+ (new_entry_count × new_boost)
+ (breadth_hold × hold_bonus)
− (breadth_exit × exit_penalty)
```

Defaults: `breadth_bonus=5`, `share_weight=0.5`, `weight_scale=15`, `new_boost=5`, `hold_bonus=1`, `exit_penalty=20`.  
Priors are structural (not fitted to one or two months). Tunable via CLI (`--hold-bonus`, etc.).

---

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Fixtures under `tests/fixtures/`; real fund folders are gitignored.

---

## Assumptions

- Disclosed equity lines may not sum to 100% of NAV; weight delta is approximate.
- Stocks merge on NSE, then BSE, then normalized name (`Ltd` / `Limited`, etc.).
- Blank share change is **hold** for that fund in the month.
- Backtest returns are not investment advice; past months are not a guarantee of future results.
