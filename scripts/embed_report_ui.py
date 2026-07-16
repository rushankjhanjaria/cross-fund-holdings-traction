#!/usr/bin/env python3
"""Regenerate multi-month HTML from reports json/*_traction.json (+ insights)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mf_screener.report_html import refresh_combined_html_report  # noqa: E402
from mf_screener.reporting.layout import ReportsLayout, migrate_flat_output  # noqa: E402


def main() -> int:
    layout = ReportsLayout.from_any_path(
        Path(sys.argv[1]) if len(sys.argv) > 1 else ReportsLayout.default().root
    )
    layout.ensure()
    # One-shot: relocate legacy flat files if still present
    for line in migrate_flat_output(layout.root):
        print(f"Migrated {line}", file=sys.stderr)

    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else layout.combined_html
    )

    if not layout.root.is_dir():
        print(f"Missing directory {layout.root}", file=sys.stderr)
        return 1

    if not refresh_combined_html_report(layout.root, out_path):
        print(
            f"No *_traction.json reports found under {layout.root}/json. "
            "Run the screener with --out / month_run first.",
            file=sys.stderr,
        )
        return 1

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
