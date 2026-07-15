# Architecture

## Pipeline

```
load.py          → HoldingRow[] per fund CSV
metrics.py       → FundStockMetrics (share %, weight delta, activity)
aggregate.py     → StockAggregate[] (scores, direction, fund contributions)
pipeline.py      → run(): filter + optional price enrichment
reporting/*      → JSON / CSV / HTML payloads
cli.py           → argparse + write outputs
```

Entry point: `python -m mf_screener` → [`cli.main`](src/mf_screener/cli.py) → [`pipeline.run`](src/mf_screener/pipeline.py).

## Product rules (single source)

| Rule | Module |
|------|--------|
| Fund activity labels (`increase`, `new`, `decrease`, `closed`, `hold`) | [`reporting/activity.py`](src/mf_screener/reporting/activity.py) |
| Display strings (share %, direction, price fields) | [`reporting/format.py`](src/mf_screener/reporting/format.py) |
| Stocks in reports (exclude hold-only across all funds) | [`reporting/filters.py`](src/mf_screener/reporting/filters.py) |
| HTML **Mixed** filter | `mixedSignal` on each stock in [`reporting/payload.py`](src/mf_screener/reporting/payload.py) (`is_mixed_signal`); UI reads `mixedSignal` with JS fallback |
| Card **score · direction** | Aggregate composite direction — not the same as Mixed filter |
| Stock identity (`Ltd` / `Limited`) | [`load.stock_key`](src/mf_screener/load.py) + [`symbol_map.normalize_company_name`](src/mf_screener/symbol_map.py) |

## Symbol map (two files)

| File | Role |
|------|------|
| [`config/nse_manual_overrides.csv`](config/nse_manual_overrides.csv) | Hand-curated exceptions (BSE, SME, renames). **Edit this.** |
| [`config/name_to_nse.csv`](config/name_to_nse.csv) | Generated runtime map. **Do not hand-edit** — run `scripts/build_name_to_nse.py`. One row per normalized company name. |

## HTML report

- Source templates: [`src/mf_screener/templates/`](src/mf_screener/templates/) (`traction.shell.html`, `traction.css`, `traction.js`).
- [`report_html.render_html_document`](src/mf_screener/report_html.py) inlines CSS/JS into one `.html` file for `file://` viewing.
- Combined `traction.html` (path you pass via `--combined-html`) loads months from `reports/*_traction.json` **first** (preserves scores and `entry_estimate`), CSV fallback only if JSON has no `stocks`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Fixtures: [`tests/fixtures/mini_june/`](tests/fixtures/mini_june/) (two small fund CSVs).

## Removed

The legacy Vite app under `ui/` was removed; use CLI-generated HTML only.
