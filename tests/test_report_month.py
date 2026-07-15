from pathlib import Path

import pytest

from mf_screener.report_month import resolve_report_month

ROOT = Path(__file__).resolve().parents[1]


def test_mini_june_resolves_2026_06(mini_june_folder: Path) -> None:
    assert resolve_report_month(mini_june_folder) == "2026-06"


def test_real_june_folder() -> None:
    folder = ROOT / "funds" / "june"
    if not folder.is_dir():
        pytest.skip("funds/june not present")
    assert resolve_report_month(folder) == "2026-06"
