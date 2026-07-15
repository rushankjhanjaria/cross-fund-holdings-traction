"""Self-contained HTML traction report (embedded JSON + filters)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from mf_screener.aggregate import StockAggregate
from mf_screener.reporting.payload import (
    build_stock_payloads_from_aggregates,
    build_stock_payloads_from_csv_rows,
    build_stock_payloads_from_report_json,
)
from mf_screener.reporting.symbol_context import NameMapContext


@dataclass(frozen=True)
class HtmlReportMeta:
    folder: str
    price_month: str | None = None
    rank_mode: str = "composite"
    include_holds: bool = False


def _load_template(name: str) -> str:
    return resources.files("mf_screener.templates").joinpath(name).read_text(encoding="utf-8")


def render_html_document(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")
    shell = _load_template("traction.shell.html")
    styles = _load_template("traction.css")
    script = _load_template("traction.js").replace("__DATA__", data_json)
    html = shell.replace("__STYLES__", styles).replace("__SCRIPT__", script)
    return html


def build_payload_from_stocks(
    stocks: Iterable[StockAggregate],
    *,
    meta: HtmlReportMeta,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    stock_list = build_stock_payloads_from_aggregates(
        stocks, entry_by_stock_key, name_map=name_map
    )
    return {
        "meta": {
            "folder": meta.folder,
            "priceMonth": meta.price_month,
            "rankMode": meta.rank_mode,
            "includeHolds": meta.include_holds,
            "stockCount": len(stock_list),
        },
        "stocks": stock_list,
    }


def build_payload_from_csv_rows(
    rows: list[dict[str, str]],
    *,
    meta: HtmlReportMeta | None = None,
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    """Rebuild HTML payload from flat CSV rows (fallback when JSON unavailable)."""
    stock_list = build_stock_payloads_from_csv_rows(rows, name_map=name_map)
    folder = meta.folder if meta else ""
    return {
        "meta": {
            "folder": folder,
            "priceMonth": meta.price_month if meta else None,
            "rankMode": meta.rank_mode if meta else "composite",
            "includeHolds": meta.include_holds if meta else False,
            "stockCount": len(stock_list),
        },
        "stocks": stock_list,
    }


def build_payload_from_json_report(
    report: dict[str, Any],
    *,
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    stock_list = build_stock_payloads_from_report_json(
        report.get("stocks") or [], name_map=name_map
    )
    return {
        "meta": {
            "folder": report.get("folder") or "",
            "priceMonth": report.get("price_month"),
            "rankMode": report.get("rank_mode") or "composite",
            "includeHolds": bool(report.get("include_holds")),
            "stockCount": len(stock_list),
        },
        "stocks": stock_list,
    }


def month_bundle_from_stocks(
    stocks: Iterable[StockAggregate],
    *,
    meta: HtmlReportMeta,
    month_id: str,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    payload = build_payload_from_stocks(
        stocks,
        meta=meta,
        entry_by_stock_key=entry_by_stock_key,
        name_map=name_map,
    )
    from mf_screener.report_month import format_month_label

    return {
        "id": month_id,
        "label": format_month_label(month_id),
        "meta": payload["meta"],
        "stocks": payload["stocks"],
    }


def build_combined_payload(
    month_bundles: list[dict[str, Any]],
    *,
    default_month_id: str | None = None,
) -> dict[str, Any]:
    ordered = sorted(month_bundles, key=lambda m: str(m.get("id", "")), reverse=True)
    default = default_month_id or (ordered[0]["id"] if ordered else "")
    return {"defaultMonthId": default, "months": ordered}


def _resolve_month_id(report: dict[str, Any], json_path: Path) -> str:
    month_id = (report.get("price_month") or "").strip()
    if not month_id:
        folder = (report.get("folder") or "").strip()
        if folder:
            from mf_screener.report_month import resolve_report_month

            try:
                month_id = resolve_report_month(Path(folder))
            except ValueError:
                month_id = ""
    return month_id


def load_month_bundles_from_output_dir(
    output_dir: Path,
    *,
    name_map: NameMapContext | None = None,
) -> list[dict[str, Any]]:
    """Load one month bundle per output/*_traction.json; CSV fallback only if JSON fails."""
    bundles: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    ctx = name_map or NameMapContext.load()

    for json_path in sorted(output_dir.glob("*_traction.json")):
        try:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        month_id = _resolve_month_id(report, json_path)
        if not month_id or month_id in seen_ids:
            continue
        seen_ids.add(month_id)

        from mf_screener.report_month import format_month_label

        if report.get("stocks"):
            payload = build_payload_from_json_report(report, name_map=ctx)
        else:
            csv_path = json_path.with_suffix(".csv")
            if not csv_path.is_file():
                continue
            with csv_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            payload = build_payload_from_csv_rows(
                rows,
                meta=HtmlReportMeta(
                    folder=report.get("folder") or "",
                    price_month=month_id,
                    rank_mode=report.get("rank_mode") or "composite",
                    include_holds=bool(report.get("include_holds")),
                ),
                name_map=ctx,
            )

        bundles.append(
            {
                "id": month_id,
                "label": format_month_label(month_id),
                "meta": payload["meta"],
                "stocks": payload["stocks"],
            }
        )

    return sorted(bundles, key=lambda m: m["id"], reverse=True)


def refresh_combined_html_report(
    output_dir: Path,
    combined_path: Path,
    *,
    prefer_month_id: str | None = None,
    name_map: NameMapContext | None = None,
) -> bool:
    """Rebuild multi-month HTML from all *_traction.json in output_dir."""
    bundles = load_month_bundles_from_output_dir(output_dir, name_map=name_map)
    if not bundles:
        return False
    default = prefer_month_id
    if default and not any(b["id"] == default for b in bundles):
        default = None
    payload = build_combined_payload(bundles, default_month_id=default)
    write_html_from_payload(combined_path, payload)
    return True


def write_html_report(
    stocks: list[StockAggregate],
    path: Path,
    *,
    meta: HtmlReportMeta,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> None:
    month_id = meta.price_month or "unknown"
    bundle = month_bundle_from_stocks(
        stocks,
        meta=meta,
        month_id=month_id,
        entry_by_stock_key=entry_by_stock_key,
        name_map=name_map,
    )
    payload = build_combined_payload([bundle], default_month_id=month_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_document(payload), encoding="utf-8")


def write_html_from_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_document(payload), encoding="utf-8")
