"""Structured reports directory layout.

Source fund CSVs stay in the repo ``funds/{month}/`` tree (or any folder you pass
to ``--folder``). Generated artifacts live under a reports root
(e.g. ``output/`` or ``~/mf-data/reports``)::

    reports/
      json/           # *_traction.json, *_insights.json
      csv/            # *_traction.csv (generated flat exports)
      html/           # *_traction.html, traction.html (combined)
      backtests/      # *_top100_backtest.json, *_summary.json
      cache/          # yfinance price caches
      watchlist.json
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUBDIRS = ("json", "csv", "html", "backtests", "cache")
LAYOUT_DIR_NAMES = frozenset(SUBDIRS)


@dataclass(frozen=True)
class ReportPaths:
    """Concrete paths for one month slug (e.g. ``june``)."""

    slug: str
    root: Path
    traction_json: Path
    traction_csv: Path
    traction_html: Path
    insights_json: Path
    backtest_json: Path
    backtest_summary: Path
    combined_html: Path
    watchlist: Path
    cache_dir: Path


@dataclass(frozen=True)
class ReportsLayout:
    root: Path

    @classmethod
    def default(cls) -> ReportsLayout:
        repo = Path(__file__).resolve().parents[2]
        return cls(root=(repo / "output").resolve())

    @classmethod
    def from_any_path(cls, path: Path) -> ReportsLayout:
        """Infer reports root from a file or directory path.

        File-like paths (existing files or paths with a suffix such as
        ``…/json/july_traction.json``) resolve to the reports root even when
        the file has not been written yet.
        """
        path = path.resolve()
        if path.name in LAYOUT_DIR_NAMES:
            return cls(root=path.parent)
        parent = path.parent
        if parent.name in LAYOUT_DIR_NAMES:
            return cls(root=parent.parent)
        # Existing directory, or path with no suffix → treat as reports root
        if path.is_dir() or not path.suffix:
            return cls(root=path)
        # File-like path (may not exist yet)
        return cls(root=parent)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in SUBDIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @property
    def json_dir(self) -> Path:
        return self.root / "json"

    @property
    def csv_dir(self) -> Path:
        return self.root / "csv"

    @property
    def html_dir(self) -> Path:
        return self.root / "html"

    @property
    def backtests_dir(self) -> Path:
        return self.root / "backtests"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @staticmethod
    def slug_from_traction_json(path: Path) -> str:
        name = path.name
        if name.endswith("_traction.json"):
            return name[: -len("_traction.json")]
        return path.stem

    @property
    def combined_html(self) -> Path:
        return self.html_dir / "traction.html"

    @property
    def watchlist(self) -> Path:
        return self.root / "watchlist.json"

    def for_slug(self, slug: str) -> ReportPaths:
        slug = slug.strip().lower().replace(" ", "_")
        return ReportPaths(
            slug=slug,
            root=self.root,
            traction_json=self.json_dir / f"{slug}_traction.json",
            traction_csv=self.csv_dir / f"{slug}_traction.csv",
            traction_html=self.html_dir / f"{slug}_traction.html",
            insights_json=self.json_dir / f"{slug}_insights.json",
            backtest_json=self.backtests_dir / f"{slug}_top100_backtest.json",
            backtest_summary=self.backtests_dir / f"{slug}_top100_backtest_summary.json",
            combined_html=self.combined_html,
            watchlist=self.watchlist,
            cache_dir=self.cache_dir,
        )

    def iter_traction_json(self) -> list[Path]:
        """Prefer structured json/; fall back to legacy flat root."""
        structured = sorted(self.json_dir.glob("*_traction.json"))
        if structured:
            return structured
        return sorted(self.root.glob("*_traction.json"))

    def iter_insights_json(self) -> list[Path]:
        structured = sorted(self.json_dir.glob("*_insights.json"))
        if structured:
            return structured
        return sorted(self.root.glob("*_insights.json"))

    def resolve_traction_json_for_insights(self, insights_path: Path) -> Path | None:
        stem = insights_path.name.replace("_insights.json", "")
        candidates = [
            self.json_dir / f"{stem}_traction.json",
            self.root / f"{stem}_traction.json",
            insights_path.parent / f"{stem}_traction.json",
        ]
        for path in candidates:
            if path.is_file():
                return path
        return None


def migrate_flat_output(root: Path) -> list[str]:
    """Move legacy flat ``*_traction.*`` / backtest files into the layout. Returns log lines."""
    layout = ReportsLayout(root=root.resolve())
    layout.ensure()
    moved: list[str] = []

    def _move(src: Path, dest: Path) -> None:
        if not src.is_file() or src.resolve() == dest.resolve():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        src.rename(dest)
        moved.append(f"{src.name} → {dest.relative_to(layout.root)}")

    for path in list(root.glob("*_traction.json")):
        _move(path, layout.json_dir / path.name)
    for path in list(root.glob("*_insights.json")):
        _move(path, layout.json_dir / path.name)
    for path in list(root.glob("*_traction.csv")):
        _move(path, layout.csv_dir / path.name)
    for path in list(root.glob("*_traction.html")):
        _move(path, layout.html_dir / path.name)
    combined = root / "traction.html"
    if combined.is_file():
        _move(combined, layout.combined_html)
    for path in list(root.glob("*_top100_backtest*.json")):
        _move(path, layout.backtests_dir / path.name)
    # leave watchlist.json + cache/ at root (cache already correct)
    return moved
