# Architecture

## Pipeline

```
load.py              → HoldingRow[] per fund CSV
metrics.py           → FundStockMetrics (share %, weight delta, activity)
aggregate.py         → StockAggregate[] (scores, direction, fund contributions)
pipeline.py          → run(): filter + optional price enrichment
reporting/write_outputs.py → JSON / CSV / HTML (+ optional combined refresh)
month_run.py         → one-shot: pipeline → reports → insights → combined HTML
insights/            → evidence → rules → optional Gemini → verify + topTraction
cli.py               → argparse entry for screening only
```

Recommended month workflow: `python -m mf_screener.month_run --folder funds/june`.

Entry point: `python -m mf_screener` → [`cli.main`](src/mf_screener/cli.py) → [`pipeline.run`](src/mf_screener/pipeline.py).

## Product rules (single source)

| Rule | Module |
|------|--------|
| Fund activity labels (`increase`, `new`, `decrease`, `closed`, `hold`) | [`reporting/activity.py`](src/mf_screener/reporting/activity.py) |
| Display strings (share %, direction, price fields) | [`reporting/format.py`](src/mf_screener/reporting/format.py) |
| Stocks in reports (exclude hold-only across all funds) | [`reporting/filters.py`](src/mf_screener/reporting/filters.py) |
| HTML **Mixed** filter | `mixedSignal` on each stock in [`reporting/payload.py`](src/mf_screener/reporting/payload.py) |
| Card **score · direction** | Aggregate composite direction — not the same as Mixed filter |
| Composite score defaults | Structural priors: log1p(share), weight conviction, modest `new_boost`, `exit_penalty`, light `hold_bonus` — [`aggregate.composite_score`](src/mf_screener/aggregate.py) |
| Price display / still_early | **pct vs 30d SMA** (`pctVsSma`); band mid kept for analysis only |
| Top-100 month-end Close backtest | [`scripts/top100_backtest.py`](scripts/top100_backtest.py) |
| Stock identity (`Ltd` / `Limited`) | [`load.stock_key`](src/mf_screener/load.py) + [`symbol_map`](src/mf_screener/symbol_map.py) |
| MoM persistence | [`reporting/persistence.py`](src/mf_screener/reporting/persistence.py) |
| Watchlist | [`reporting/watchlist.py`](src/mf_screener/reporting/watchlist.py) |
| Grounded insights | [`insights/`](src/mf_screener/insights/) — triage + `topTraction` leaderboard |

## Symbol map (two files)

| File | Role |
|------|------|
| [`config/nse_manual_overrides.csv`](config/nse_manual_overrides.csv) | Hand-curated exceptions. **Edit this.** |
| [`config/name_to_nse.csv`](config/name_to_nse.csv) | Generated runtime map. **Do not hand-edit.** |

## HTML report

- Templates: [`src/mf_screener/templates/`](src/mf_screener/templates/).
- Combined `traction.html` embeds months, watchlist, `insightsByMonth`, `topTractionByMonth`.
- Optional rebuild: `scripts/embed_report_ui.py` (also done by `month_run` / CLI `--out`).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Fixtures: [`tests/fixtures/mini_june/`](tests/fixtures/mini_june/).

## Removed

The legacy Vite app under `ui/` was removed; use CLI-generated HTML only.
