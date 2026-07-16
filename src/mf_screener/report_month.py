"""Derive report calendar month (YYYY-MM) from fund folder path and CSV names."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

MONTH_NUM_TO_NAME: dict[str, str] = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}

MONTH_NAME_TO_NUM: dict[str, str] = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}

_FILENAME_SUFFIX = re.compile(r"_(\d{2})_(\d{2})$")
_YYYY_MM = re.compile(r"^(\d{4})-(\d{2})$")


def month_num_from_folder_name(segment: str) -> str | None:
    return MONTH_NAME_TO_NUM.get(segment.strip().lower())


def year_month_from_csv_stem(stem: str) -> tuple[str, str] | None:
    match = _FILENAME_SUFFIX.search(stem)
    if not match:
        return None
    mm, yy = match.group(1), match.group(2)
    return f"20{yy}", mm


def resolve_report_month(folder: Path) -> str:
    folder = folder.resolve()
    segment = folder.name

    yyyy_mm = _YYYY_MM.match(segment)
    if yyyy_mm:
        return f"{yyyy_mm.group(1)}-{yyyy_mm.group(2)}"

    mm_from_name = month_num_from_folder_name(segment)
    year: str | None = None
    mm_from_file: str | None = None

    for path in sorted(folder.glob("*.csv")):
        parsed = year_month_from_csv_stem(path.stem)
        if parsed:
            year, mm_from_file = parsed
            break

    if mm_from_name and year:
        if mm_from_file and mm_from_file != mm_from_name:
            raise ValueError(
                f"Folder month '{segment}' ({mm_from_name}) does not match "
                f"CSV suffix month {mm_from_file} in {folder}"
            )
        return f"{year}-{mm_from_name}"

    if year and mm_from_file:
        return f"{year}-{mm_from_file}"

    if mm_from_name:
        raise ValueError(
            f"Cannot infer year for folder '{folder}'. "
            "Use CSV names like *_06_26.csv or folder name YYYY-MM."
        )

    raise ValueError(
        f"Cannot resolve report month from folder '{folder}'. "
        "Use funds/june with *_MM_YY.csv files or funds/2026-06."
    )


def format_month_label(year_month: str) -> str:
    """Turn YYYY-MM into e.g. June 2026."""
    match = _YYYY_MM.match((year_month or "").strip())
    if not match:
        return year_month or "Unknown"
    yyyy, mm = match.group(1), match.group(2)
    name = MONTH_NUM_TO_NAME.get(mm, mm)
    return f"{name} {yyyy}"


def month_bounds(month: str) -> tuple[date, date]:
    """Inclusive start / exclusive end calendar dates for YYYY-MM."""
    year, mm = month.split("-")
    y, m = int(year), int(mm)
    start = date(y, m, 1)
    if m == 12:
        end = date(y + 1, 1, 1)
    else:
        end = date(y, m + 1, 1)
    return start, end


def month_id_from_report(report: dict[str, Any], *, fallback_path: Path | None = None) -> str:
    """Prefer price_month on the report JSON; else resolve from folder field."""
    month_id = str(report.get("price_month") or "").strip()
    if month_id:
        return month_id[:7] if len(month_id) >= 7 else month_id
    folder = str(report.get("folder") or "").strip()
    if folder:
        try:
            return resolve_report_month(Path(folder))
        except ValueError:
            pass
    _ = fallback_path
    return ""
