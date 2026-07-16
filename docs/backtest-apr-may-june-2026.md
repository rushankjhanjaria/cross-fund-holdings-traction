# April–June 2026 top-100 backtest report

**Buy:** last trading-day Close of the report month (actionable as-of disclosure)  
**Exit:** latest Close as of price refresh (2026-07-16)  
**Universe:** top 100 by composite score (incl. `hold_bonus=1`)  
**Insights:** rules-only (no `GEMINI_API_KEY` in CI/local run)

## Summary

| Month | Priced | EW return | Median | Win rate | Score↔return r |
|-------|--------|-----------|--------|----------|----------------|
| April 2026 | 96/100 | **+9.68%** | +5.08% | 68.8% | +0.25 |
| May 2026 | 98/100 | **+6.49%** | +5.81% | 74.5% | +0.00 |
| June 2026 | 99/100 | **+1.74%** | +1.30% | 61.6% | −0.09 |

June’s smaller absolute move is expected (shorter hold from month-end to refresh date).

## Avg return by score rank bucket

| Bucket | April | May | June |
|--------|-------|-----|------|
| 1–25 | 13.08% | 7.48% | 0.37% |
| 26–50 | 7.35% | 5.09% | 3.48% |
| 51–75 | 10.37% | 7.43% | 2.06% |
| 76–100 | 7.58% | 5.90% | 1.02% |

## Top winners (by return)

**April:** Cemindia +97%, HFCL +93%, Rategain +61%, Grindwell +53%, Cyient DLM +49%  
**May:** CarTrade +62%, Cemindia +50%, Aditya Infotech +31%, Grindwell +31%, ACME Solar +27%  
**June:** Info Edge +23%, Paytm +19%, MphasiS +12%, Divi’s +11%, Bluestone +11%

## Artifacts

- `output/{month}_traction.json` / `.html` / `_insights.json`
- `output/{month}_top100_backtest.json` + `_summary.json`
- Combined UI: `output/traction.html`
- Interactive canvas (local IDE): `apr-may-june-backtest.canvas.tsx`

## Score formula (current defaults)

```text
(breadth_active × 5)
+ (breadth_active × log1p(median_share) × 0.5)
+ (breadth_weight_up × median_weight_delta × 15)
+ (new_entry_count × 5)
+ (breadth_hold × 1)
− (breadth_exit × 20)
```

UI compares current price to **30d SMA** (not entry mid). Backtest buy uses **month-end Close**.
