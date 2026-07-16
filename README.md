# MF holdings traction screener

**Personal project** built for a practical day-to-day workflow: scan **recent mutual fund portfolio activity** across many schemes, **spot names where institutions are moving together (or disagreeing)**, and get a rough **entry context** from price action around the disclosure month—not as a buy/sell signal, but as a sanity check against “chasing” after funds have already built positions.

In practice it helps you:

- **Prioritize reading** — rank stocks by cross-fund share and weight changes instead of opening dozens of fund factsheets one by one.
- **See consensus vs debate** — filters for adds-only, reduces-only, new entries, and **mixed** signals (e.g. one fund adding while another trims or holds).
- **Breadth vs intensity** — sort by traction score or by **how many funds** touch the same name.
- **Link to research** — NSE tickers in the HTML report open [Screener.in](https://www.screener.in) consolidated pages when mapped.
- **Optional price band** — with `--enrich-prices`, a heuristic month high/low band and last close vs estimated “entry mid” (yfinance; not actual MF trade prices).

Anyone tracking **Indian equity MF holdings** (researchers, DIY investors, PMs doing peer comparison) can reuse the same pipeline: ingest from RupeeVest, point the CLI at a local data folder, regenerate JSON/CSV/HTML.

---

## Data stays outside the repo

This repository is **code + config only**. Fund CSVs and generated reports are **not** committed.

Use a separate directory on your machine (example: `~/mf-data`):

```text
~/mf-data/
  funds/
    june/                          # one CSV per fund (ingested)
      helios_small_cap_06_26.csv
      abakkus_small_cap_06_26.csv
      ...
    july/
      ...
  reports/
    june_traction.json             # ranked universe + metadata
    june_traction.csv
    june_traction.html
    traction.html                  # combined multi-month UI
    cache/
      prices_2026-06.json          # yfinance cache when using --enrich-prices
```

The JSON/HTML `meta.folder` field records the **absolute path** to the fund folder used for that run so you know which ingest batch produced the report.

---

## Ingest fund reports (RupeeVest)

Holdings CSVs match RupeeVest’s [MF Portfolio Tracker](https://www.rupeevest.com/Mutual-Fund-Portfolio-Tracker) **Download** format (equity block). Ingestion uses the site’s JSON API—no browser automation.

```bash
# Check fund names resolve (RupeeVest autocomplete spelling)
python3 scripts/download_rupeevest_funds.py --dry-run \
  --funds-file config/rupeevest_funds.example.txt

# Download into your external funds folder
python3 scripts/download_rupeevest_funds.py \
  --funds-file config/rupeevest_funds.example.txt \
  --out-dir ~/mf-data/funds/june \
  --delay 1.0 \
  --overwrite
```

Add funds with `--fund "Helios Small Cap Fund-Reg(G)"` or maintain a private list file (copy from `config/rupeevest_funds.example.txt`). Filenames default to `abakkus_small_cap_06_26.csv` from fund name + latest month in the export.

**CSV formats**

- **Equity Holdings** (RupeeVest): multi-month `% of AUM` and `No. of Shares`; the screener uses the **first month as current** and the **second as previous**.
- **Trendlyne** (legacy): `Invested In`, `NSE Code`, `% of Total Holding`, `Month Change in Shares %`, etc.

---

## Install

```bash
cd /path/to/mf-screener
pip install -e .
```

Dependencies: `yfinance`, `pandas` (for optional price enrichment).

Or without install:

```bash
pip install yfinance pandas
export PYTHONPATH=src
```

---

## Run the screener

```bash
python -m mf_screener \
  --folder ~/mf-data/funds/june \
  --enrich-prices \
  --out ~/mf-data/reports/june_traction.json \
  --top 50
```

`--out` also writes **CSV** and **HTML** next to the JSON (`june_traction.csv`, `june_traction.html`). Override with `--csv` or `--html`.

Combined dashboard (all `*_traction.json` under the reports directory):

```bash
python -m mf_screener \
  --folder ~/mf-data/funds/june \
  --out ~/mf-data/reports/june_traction.json \
  --combined-html ~/mf-data/reports/traction.html
```

Repeat for `july`, etc.; each run refreshes `traction.html` when `--combined-html` points at the same `reports/` folder.

```bash
open ~/mf-data/reports/traction.html
```

### Report rules

Only stocks where at least one fund **bought, sold, closed, or newly entered** (share activity). Names where every fund only **held** unchanged shares are excluded unless you pass `--include-holds`.

| Filter | Shows stocks where… |
|--------|---------------------|
| All | Entire report set |
| Added only | Adds/new, **no** fund reduced |
| Reduced only | Trims/closed, **no** fund added |
| New only | At least one `New` position |
| Mixed | ≥2 of adding / reducing / unchanged |
| Still adding | MoM: adding again after prior adds (needs ≥2 month JSONs) |
| Reversed | MoM: flipped add↔reduce vs prior month |
| New this month | Not present in the prior month report |
| Watchlist | Pinned names (file + browser pins) |

Sort by traction score (default) or **Most funds**. Search by name or NSE symbol. Ticker badges link to Screener.in when mapped.

### Persistence (month-over-month)

Put at least two `*_traction.json` files in the same reports directory (e.g. May + June). Combined HTML joins stocks on `stockKey` and badges each name: still adding, reversed, new this month, etc.

### Watchlist

On each combined HTML refresh, top 20 adds/mixed names are auto-merged into `{reports}/watchlist.json` (manual pins are never overwritten). In the UI: ★ pin, **Watchlist** filter, and **Download watchlist.json**.

```bash
python3 scripts/manage_watchlist.py --reports-dir ~/mf-data/reports list
python3 scripts/manage_watchlist.py --reports-dir ~/mf-data/reports add --key NSE:MEESHO --name "Meesho Ltd." --nse MEESHO
```

### Grounded AI insights

Monthly **triage** from report fields only (no web browsing): a **Top traction** shortlist plus narrative cards for **still early** (adds while price near the band), **exit pressure**, **debate**, and **watchlist deltas**. **Rules-only** works offline; optional **Gemini** wordsmithing if `GEMINI_API_KEY` is set (default model `gemini-2.0-flash`, override with `GEMINI_MODEL`). A verifier drops invented tickers, wrong numbers, or unknown insight types.

```bash
# Rules only
python3 -m mf_screener.insights --report ~/mf-data/reports/june_traction.json --no-gemini

# With Gemini (optional)
export GEMINI_API_KEY=your_key
python3 -m mf_screener.insights --report ~/mf-data/reports/june_traction.json
```

Writes `june_insights.json` (`topTraction` + `insights`). Rebuild `traction.html` to embed the Insights panel (and persistence/watchlist):

```bash
python3 scripts/embed_report_ui.py ~/mf-data/reports ~/mf-data/reports/traction.html
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for module layout.

---

## Name → NSE map (`--enrich-prices`)

Runtime lookup: **[`config/name_to_nse.csv`](config/name_to_nse.csv)** (generated; do not hand-edit). Exceptions: **[`config/nse_manual_overrides.csv`](config/nse_manual_overrides.csv)**.

Rebuild from **your** fund tree (all month subfolders):

```bash
python3 scripts/build_name_to_nse.py --funds ~/mf-data/funds --report-unmapped
```

One deduplicated row per company (canonical spelling). US names and some BSE-only lines may stay unmapped—expected.

---

## MF price enrichment (`--enrich-prices` / `month_run`)

Report month is inferred from the folder (`june` → `06`) and filenames (`*_06_26.csv` → `2026-06`).

| Field | Meaning |
|--------|---------|
| `month_high` / `month_low` | Month range (context) |
| `estimated_entry_mid` | Mid of that range (legacy / analysis) |
| `month_end_close` | Last Close of the report month |
| `sma_30` | 30d SMA as of month-end |
| `close_latest` | Latest Close |
| `pct_vs_sma` | **Primary UI metric** — current vs 30d SMA |
| `pct_vs_entry_mid` | Current vs band mid (kept for analysis) |

Cached under `output/cache/prices_YYYY-MM.json` (repo-local when using `month_run`). Not actual MF execution prices.

### One-shot month workflow

```bash
PYTHONPATH=src python3 -m mf_screener.month_run --folder funds/june --refresh-prices
```

Writes `*_traction.json/csv/html`, insights, and refreshes combined `traction.html`.

### Top-100 backtest

```bash
PYTHONPATH=src python3 scripts/top100_backtest.py --report output/june_traction.json
```

Buy = **month-end Close**; exit = latest Close. See [`docs/backtest-apr-may-june-2026.md`](docs/backtest-apr-may-june-2026.md).

---

## Metrics (composite score)

| Signal | Meaning |
|--------|---------|
| **Share change %** | Primary activity (adds/trims); `New` = first-time holding |
| **Weight delta (pp)** | Allocation vs fund NAV (conviction) |

Default composite (tunable via CLI; priors kept simple — avoid fitting to one or two months):

```text
(breadth_active × breadth_bonus)
+ (breadth_active × log1p(median_share_change_pct) × share_weight)   # positive share only
+ (breadth_weight_up × median_weight_delta_pp × weight_scale)
+ (new_entry_count × new_boost)
+ (breadth_hold × hold_bonus)   # funds still holding unchanged shares
− (breadth_exit × exit_penalty)
```

Defaults: `breadth_bonus=5`, `share_weight=0.5`, `weight_scale=15`, `new_boost=5`, `hold_bonus=1`, `exit_penalty=20`.
Raw share-% spikes are log-compressed so one extreme median (e.g. tiny float/new listing) cannot dominate. Mixed add/reduce is penalized via `breadth_exit`. Continued ownership (`hold`) adds a light footprint so widely held names are not ignored versus flashy one-fund spikes.

---

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Fixtures under `tests/fixtures/`; real `funds/june` is optional and gitignored.

---

## Assumptions

- Disclosed equity lines may not sum to 100% of NAV; weight delta is approximate.
- Stocks merge on NSE, then BSE, then normalized name (`Ltd` / `Limited`, etc.).
- Blank share change is **hold** for that fund in the month.
