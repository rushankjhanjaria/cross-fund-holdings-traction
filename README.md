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

Sort by traction score (default) or **Most funds**. Search by name or NSE symbol. Ticker badges link to Screener.in when mapped.

Rebuild combined HTML from existing JSON only:

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

## MF entry estimate (`--enrich-prices`)

Report month is inferred from the folder (`june` → `06`) and filenames (`*_06_26.csv` → `2026-06`).

| Field | Meaning |
|--------|---------|
| `month_high` / `month_low` | Heuristic entry **band** for the report month |
| `estimated_entry_mid` | Mid of band |
| `close_latest` | Last daily close (yfinance) |
| `pct_vs_entry_mid` | Move vs mid |

Cached under `reports/cache/prices_YYYY-MM.json`. Not actual MF execution prices.

---

## Metrics (composite score)

| Signal | Meaning |
|--------|---------|
| **Share change %** | Primary activity (adds/trims); `New` = first-time holding |
| **Weight delta (pp)** | Allocation vs fund NAV (conviction) |

Default composite (tunable via CLI):

```text
(breadth_active × median_share_change_pct)
+ (breadth_weight_up × median_weight_delta_pp × weight_scale)
+ (new_entry_count × new_boost)
```

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
