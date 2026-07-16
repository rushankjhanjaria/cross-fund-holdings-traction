"""CLI: build grounded insights for a traction JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mf_screener.insights.evidence import build_evidence_pack
from mf_screener.insights.gemini import narrate
from mf_screener.insights.rules import rule_candidates
from mf_screener.insights.verify import verify_insights
from mf_screener.report_html import (
    build_payload_from_json_report,
    load_month_bundles_from_output_dir,
)
from mf_screener.reporting.persistence import attach_persistence_to_bundles
from mf_screener.reporting.watchlist import load_watchlist


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate grounded insights from a traction report (rules + optional Gemini).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to *_traction.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write insights JSON (default: sibling *_insights.json)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Directory for watchlist + prior months (default: report parent)",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Force rules-only (ignore GEMINI_API_KEY)",
    )
    return parser.parse_args(argv)


def _stocks_for_report(report_path: Path, reports_dir: Path) -> tuple[str, list[dict]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    month_id = (report.get("price_month") or "").strip()
    bundles = load_month_bundles_from_output_dir(reports_dir)
    if bundles:
        attach_persistence_to_bundles(bundles)
        match = next((b for b in bundles if b["id"] == month_id), None)
        if match is None and month_id:
            # fall back to newest
            match = bundles[0]
            month_id = str(match["id"])
        elif match is None:
            match = bundles[0]
            month_id = str(match["id"])
        return month_id, list(match.get("stocks") or [])

    payload = build_payload_from_json_report(report)
    stocks = list(payload.get("stocks") or [])
    attach_persistence_to_bundles(
        [{"id": month_id or "unknown", "stocks": stocks}]
    )
    return month_id or "unknown", stocks


def run_insights(
    report_path: Path,
    *,
    out_path: Path | None = None,
    reports_dir: Path | None = None,
    use_gemini: bool = True,
) -> dict:
    from mf_screener.reporting.layout import ReportsLayout

    layout = ReportsLayout.from_any_path(reports_dir or report_path)
    reports_dir = layout.root
    month_id, stocks = _stocks_for_report(report_path, reports_dir)
    wl = load_watchlist(reports_dir)
    pack = build_evidence_pack(
        stocks,
        month_id=month_id,
        watchlist_items=list(wl.get("items") or []),
    )
    candidates = rule_candidates(pack)
    narrated = None
    if use_gemini:
        # Prefer decisionBoard + facts-only candidates; model writes headline/body
        narrated = narrate(pack, candidates, prefer_decision_board=True)
    source = "gemini" if narrated else "rules"
    raw_insights = narrated if narrated else candidates
    verified = verify_insights(raw_insights, pack)
    # Always ensure rules path yields verified output if Gemini fails / verify empties
    if not verified and candidates:
        verified = verify_insights(candidates, pack)
        source = "rules"

    doc = {
        "monthId": month_id,
        "source": source,
        "report": str(report_path.resolve()),
        "topTraction": list(pack.get("topTraction") or []),
        "insights": verified,
    }
    if out_path is None:
        slug = ReportsLayout.slug_from_traction_json(report_path)
        out = layout.for_slug(slug).insights_json
    else:
        out = out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["_out"] = str(out)
    return doc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.report.is_file():
        print(f"Report not found: {args.report}", file=sys.stderr)
        return 1
    doc = run_insights(
        args.report,
        out_path=args.out,
        reports_dir=args.reports_dir,
        use_gemini=not args.no_gemini,
    )
    print(
        f"Wrote {doc['_out']} "
        f"({len(doc['insights'])} insights, {len(doc.get('topTraction') or [])} topTraction, "
        f"source={doc['source']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
