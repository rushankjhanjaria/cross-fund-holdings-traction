import csv
from collections import defaultdict
from pathlib import Path

import pytest

from mf_screener.symbol_map import normalize_company_name

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "config" / "name_to_nse.csv"


@pytest.mark.skipif(not MAP_PATH.is_file(), reason="name_to_nse.csv not present")
def test_name_to_nse_unique_normalized_keys() -> None:
    rows = list(csv.DictReader(MAP_PATH.open(encoding="utf-8")))
    by_norm: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_norm[normalize_company_name(row["company_name"])].append(row["company_name"])
    dup_groups = {k: v for k, v in by_norm.items() if len(v) > 1}
    assert not dup_groups, f"duplicate norm keys: {list(dup_groups.items())[:3]}"
