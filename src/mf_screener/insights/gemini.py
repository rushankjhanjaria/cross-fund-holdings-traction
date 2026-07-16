"""Optional Gemini narration over closed-world evidence + rule candidates."""

from __future__ import annotations

import json
import os
import re
from typing import Any


DEFAULT_MODEL = "gemini-2.0-flash"


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("insights"), list):
            return [x for x in data["insights"] if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _candidate_facts(candidate: dict[str, Any]) -> dict[str, Any]:
    """Strip pre-written headline/body so the model must write its own copy."""
    citations = candidate.get("citations") or []
    fact_cites: list[dict[str, Any]] = []
    for cite in citations:
        if not isinstance(cite, dict):
            continue
        fact_cites.append(
            {
                "stockKey": str(cite.get("stockKey") or ""),
                "fields": dict(cite.get("fields") or {}),
            }
        )
    return {
        "stockKey": (candidate.get("stockKeys") or [None])[0],
        "stockKeys": list(candidate.get("stockKeys") or []),
        "type": str(candidate.get("type") or ""),
        "actionSuggestion": str(candidate.get("action") or ""),
        "citationFields": fact_cites,
    }


def _stock_fact(snap: dict[str, Any]) -> dict[str, Any]:
    return {
        "stockKey": snap.get("stockKey"),
        "name": snap.get("name"),
        "fundCount": snap.get("fundCount"),
        "fundDelta": snap.get("fundDelta"),
        "scoreDelta": snap.get("scoreDelta"),
        "addCount": snap.get("addCount"),
        "reduceCount": snap.get("reduceCount"),
        "newCount": snap.get("newCount"),
        "mixedSignal": snap.get("mixedSignal"),
        "breadth": snap.get("breadth"),
        "fundNames": snap.get("fundNames") or [],
        "persistence": snap.get("persistence") or {},
        "pctVsMid": snap.get("pctVsSma") or snap.get("pctVsMid") or "",
        "pctVsSma": snap.get("pctVsSma") or snap.get("pctVsMid") or "",
        "sma30": snap.get("sma30") or "",
        "score": snap.get("score"),
    }


def _focused_evidence(
    evidence: dict[str, Any],
    *,
    prefer_decision_board: bool = True,
) -> dict[str, Any]:
    """Shrink evidence for the prompt: decision board + allowlists, not full stocksByKey."""
    focused: dict[str, Any] = {
        "monthId": evidence.get("monthId"),
        "allowedStockKeys": evidence.get("allowedStockKeys") or [],
        "allowedNames": evidence.get("allowedNames") or [],
        "allowedFundNames": evidence.get("allowedFundNames") or [],
    }
    if prefer_decision_board and evidence.get("decisionBoard"):
        focused["decisionBoard"] = evidence["decisionBoard"]
    else:
        for key in ("topAdds", "topReduces", "topMixed", "stillReducing", "reversed", "watchlist"):
            if evidence.get(key):
                focused[key] = evidence[key]
    by_key = evidence.get("stocksByKey") or {}
    keys_needed: set[str] = set()
    for row in focused.get("decisionBoard") or []:
        if isinstance(row, dict) and row.get("stockKey"):
            keys_needed.add(str(row["stockKey"]))
    stock_facts = {}
    for k in keys_needed:
        snap = by_key.get(k)
        if snap:
            stock_facts[k] = _stock_fact(snap)
    focused["stockFacts"] = stock_facts
    return focused


def narrate(
    evidence: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    prefer_decision_board: bool = True,
) -> list[dict[str, Any]] | None:
    """Call Gemini to wordsmith candidates. Returns None if unavailable."""
    key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    model_name = (model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()

    fact_candidates = [_candidate_facts(c) for c in candidates]
    focused = _focused_evidence(evidence, prefer_decision_board=prefer_decision_board)
    by_key = evidence.get("stocksByKey") or {}
    stock_facts = dict(focused.get("stockFacts") or {})
    for fact in fact_candidates:
        for sk in fact.get("stockKeys") or []:
            if sk in stock_facts or sk not in by_key:
                continue
            stock_facts[sk] = _stock_fact(by_key[sk])
    focused["stockFacts"] = stock_facts

    prompt = f"""You are an assistant for an Indian mutual-fund holdings traction screener.
Your job: wordsmith a short monthly triage list for a DIY investor from CANDIDATE_FACTS + STOCK_FACTS (+ decisionBoard context).

## Hard rules (anti-hallucination)
- Use ONLY stockKey, names, fundNames, and numbers that appear in the evidence below.
- citations[].fields MUST copy those numbers exactly (fundCount, priorFundCount, fundDelta, score, scoreDelta, pctVsSma, pctVsMid, sma30, persistence.status, addCount, reduceCount, etc.).
- Forbidden: valuation, news, earnings, management quality, price targets, sector narratives, inventing funds/tickers, buy/sell advice.
- Do NOT invent topTraction rows or new tickers. Do NOT copy pre-written headline/body — write original wording from the numbers.
- For EACH output object you MUST echo type, action, stockKeys, and citations from the matching CANDIDATE_FACTS row (type and action are not free-form).

## Allowed types (exactly these)
- still_early → action research
- exit_pressure → action caution
- debate → action caution
- watchlist_delta → action monitor or caution (as in the candidate)

## Variety
- Keep at most one insight per stockKey.
- Prefer mixing types when candidates exist: still_early, exit_pressure, debate, watchlist_delta.
- Do not invent types outside the allowed list.
- At most 8 insights total.

## Output format
Return ONLY a JSON array (no markdown) of at most 8 objects with keys:
id, type, headline, action, stockKeys, body, citations

- type: one of still_early | exit_pressure | debate | watchlist_delta (must match candidate)
- action: one of research | monitor | caution (must match candidate actionSuggestion)
- headline: ≤12 words, names the stock and triage bucket (e.g. "Still early: Meesho")
- body: EXACTLY 2 sentences:
  1) What changed — concrete numbers (+ at most two fund names from fundNames)
  2) One report-native next step (vary by type; do not repeat the same next-step sentence)
- stockKeys / citations: from the candidate

## EVIDENCE
{json.dumps(focused, ensure_ascii=False)}

## CANDIDATE_FACTS
{json.dumps(fact_candidates, ensure_ascii=False)}
"""

    try:
        try:
            from google import genai

            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"temperature": 0.55},
            )
            text = getattr(response, "text", None) or str(response)
        except Exception:
            import google.generativeai as genai_old

            genai_old.configure(api_key=key)
            gm = genai_old.GenerativeModel(model_name)
            response = gm.generate_content(
                prompt,
                generation_config={"temperature": 0.55},
            )
            text = getattr(response, "text", None) or ""
    except Exception:
        return None

    return _extract_json_array(text)
