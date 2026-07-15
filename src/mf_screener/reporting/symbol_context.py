"""Loaded name→symbol map (one read per run)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mf_screener.symbol_map import ListedSymbol, load_name_to_nse, resolve_nse


@dataclass(frozen=True)
class NameMapContext:
    mapping: dict[str, ListedSymbol]

    @classmethod
    def load(cls, path: Path | None = None) -> NameMapContext:
        return cls(mapping=load_name_to_nse(path))

    def resolve_ticker(
        self,
        *,
        name: str,
        nse_from_row: str = "",
        entry_estimate: dict | None = None,
    ) -> str:
        nse = (nse_from_row or "").strip().upper()
        if nse:
            return nse
        if entry_estimate and entry_estimate.get("status") == "ok" and entry_estimate.get("nse"):
            return str(entry_estimate["nse"]).strip().upper()
        listed = resolve_nse(name=name, nse_from_row="", name_map=self.mapping)
        return listed.code if listed else ""
