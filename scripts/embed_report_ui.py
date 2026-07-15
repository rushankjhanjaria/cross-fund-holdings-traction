#!/usr/bin/env python3
"""Regenerate multi-month HTML from existing output/*_traction.json + CSV."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mf_screener.report_html import refresh_combined_html_report  # noqa: E402

DEFAULT_OUT = ROOT / "output" / "traction.html"
DEFAULT_DIR = ROOT / "output"


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

    if not out_dir.is_dir():
        print(f"Missing directory {out_dir}", file=sys.stderr)
        return 1

    if not refresh_combined_html_report(out_dir, out_path):
        print(
            f"No *_traction.json reports found in {out_dir}. Run the screener with --out first.",
            file=sys.stderr,
        )
        return 1

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
