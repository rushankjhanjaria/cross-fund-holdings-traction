"""Tests for structured reports layout."""

from __future__ import annotations

from pathlib import Path

from mf_screener.reporting.layout import ReportsLayout, migrate_flat_output


def test_for_slug_paths(tmp_path: Path) -> None:
    layout = ReportsLayout(root=tmp_path)
    layout.ensure()
    paths = layout.for_slug("June")
    assert paths.slug == "june"
    assert paths.traction_json == tmp_path / "json" / "june_traction.json"
    assert paths.traction_csv == tmp_path / "csv" / "june_traction.csv"
    assert paths.traction_html == tmp_path / "html" / "june_traction.html"
    assert paths.insights_json == tmp_path / "json" / "june_insights.json"
    assert paths.backtest_json == tmp_path / "backtests" / "june_top100_backtest.json"
    assert paths.combined_html == tmp_path / "html" / "traction.html"
    assert paths.watchlist == tmp_path / "watchlist.json"


def test_from_any_path_resolves_layout_subdir(tmp_path: Path) -> None:
    layout = ReportsLayout(root=tmp_path)
    layout.ensure()
    json_file = layout.for_slug("may").traction_json
    json_file.write_text("{}", encoding="utf-8")
    assert ReportsLayout.from_any_path(json_file).root == tmp_path.resolve()
    assert ReportsLayout.from_any_path(layout.json_dir).root == tmp_path.resolve()


def test_from_any_path_before_file_exists(tmp_path: Path) -> None:
    """Regression: GHA wrote into …/july_traction.json/json/ when path was missing."""
    layout = ReportsLayout(root=tmp_path)
    layout.ensure()
    missing = tmp_path / "json" / "july_traction.json"
    assert not missing.exists()
    assert ReportsLayout.from_any_path(missing).root == tmp_path.resolve()
    paths = ReportsLayout.from_any_path(missing).for_slug("july")
    assert paths.traction_json == missing
    assert paths.traction_csv == tmp_path / "csv" / "july_traction.csv"


def test_migrate_flat_output(tmp_path: Path) -> None:
    (tmp_path / "april_traction.json").write_text("{}", encoding="utf-8")
    (tmp_path / "april_insights.json").write_text("{}", encoding="utf-8")
    (tmp_path / "april_traction.csv").write_text("a\n", encoding="utf-8")
    (tmp_path / "april_traction.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "traction.html").write_text("<html>combined</html>", encoding="utf-8")
    (tmp_path / "april_top100_backtest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "april_top100_backtest_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "watchlist.json").write_text('{"version":1,"items":[]}', encoding="utf-8")

    moved = migrate_flat_output(tmp_path)
    assert moved
    layout = ReportsLayout(root=tmp_path)
    assert (layout.json_dir / "april_traction.json").is_file()
    assert (layout.json_dir / "april_insights.json").is_file()
    assert (layout.csv_dir / "april_traction.csv").is_file()
    assert (layout.html_dir / "april_traction.html").is_file()
    assert layout.combined_html.is_file()
    assert (layout.backtests_dir / "april_top100_backtest.json").is_file()
    assert (tmp_path / "watchlist.json").is_file()
    assert layout.iter_traction_json() == [layout.json_dir / "april_traction.json"]
