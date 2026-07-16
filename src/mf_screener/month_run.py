"""One-command month pipeline: screen → prices → insights → HTML.

Usage:
  PYTHONPATH=src python3 -m mf_screener.month_run --folder funds/june
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mf_screener.insights.__main__ import run_insights
from mf_screener.pipeline import run
from mf_screener.report_html import refresh_combined_html_report
from mf_screener.reporting.symbol_context import NameMapContext
from mf_screener.reporting.terminal import print_tree
from mf_screener.reporting.write_outputs import write_traction_reports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Full month pipeline: load fund CSVs, enrich prices, write reports, "
            "generate Gemini insights (if GEMINI_API_KEY set), refresh combined HTML."
        ),
    )
    p.add_argument(
        "--folder",
        type=Path,
        required=True,
        help="Fund CSV folder for one month (e.g. funds/june)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Reports directory (default: <repo>/output)",
    )
    p.add_argument(
        "--slug",
        type=str,
        default=None,
        help="Output basename prefix (default: folder name → june_traction.json)",
    )
    p.add_argument("--top", type=int, default=30)
    p.add_argument(
        "--rank",
        default="composite",
        choices=("composite", "share_activity", "mean_weight_delta", "new_entries"),
    )
    p.add_argument("--include-holds", action="store_true")
    p.add_argument("--no-prices", action="store_true", help="Skip yfinance enrichment")
    p.add_argument("--refresh-prices", action="store_true")
    p.add_argument("--no-gemini", action="store_true", help="Rules-only insights")
    p.add_argument("--no-insights", action="store_true", help="Skip insights")
    return p.parse_args(argv)


def _default_out_dir() -> Path:
    repo = Path(__file__).resolve().parents[2]
    out = repo / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_month(
    folder: Path,
    *,
    out_dir: Path | None = None,
    slug: str | None = None,
    enrich_prices: bool = True,
    refresh_prices: bool = False,
    use_gemini: bool = True,
    make_insights: bool = True,
    rank: str = "composite",
    include_holds: bool = False,
    top: int = 30,
) -> dict:
    folder = folder.resolve()
    out_dir = (out_dir or _default_out_dir()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = (slug or folder.name).strip().lower().replace(" ", "_")
    out_json = out_dir / f"{slug}_traction.json"
    combined = out_dir / "traction.html"

    result = run(
        folder,
        rank_mode=rank,  # type: ignore[arg-type]
        include_holds=include_holds,
        enrich_prices=enrich_prices,
        refresh_prices=refresh_prices,
    )
    name_map = NameMapContext.load()

    print_tree(result.stocks, top=top)

    # Write month artifacts once; refresh combined HTML after insights so MoM
    # persistence + insights embed in a single rebuild.
    write_traction_reports(
        result,
        folder=folder,
        out_json=out_json,
        rank=rank,
        include_holds=include_holds,
        name_map=name_map,
        combined_html=combined,
        refresh_combined=False,
    )

    insights_doc = None
    if make_insights:
        insights_doc = run_insights(
            out_json,
            reports_dir=out_dir,
            use_gemini=use_gemini,
        )
        print(
            f"Wrote insights to {insights_doc['_out']} "
            f"({len(insights_doc['insights'])} insights, "
            f"{len(insights_doc.get('topTraction') or [])} topTraction, "
            f"source={insights_doc['source']})",
            file=sys.stderr,
        )

    if refresh_combined_html_report(
        out_dir,
        combined,
        prefer_month_id=result.price_month,
        name_map=name_map,
    ):
        print(f"Wrote combined HTML report to {combined}", file=sys.stderr)

    return {
        "folder": str(folder),
        "out_json": str(out_json),
        "combined_html": str(combined),
        "price_month": result.price_month,
        "stock_count": len(result.stocks),
        "insights": insights_doc,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.folder.is_dir():
        print(f"Folder not found: {args.folder}", file=sys.stderr)
        return 1
    try:
        run_month(
            args.folder,
            out_dir=args.out_dir,
            slug=args.slug,
            enrich_prices=not args.no_prices,
            refresh_prices=args.refresh_prices,
            use_gemini=not args.no_gemini,
            make_insights=not args.no_insights,
            rank=args.rank,
            include_holds=args.include_holds,
            top=args.top,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
