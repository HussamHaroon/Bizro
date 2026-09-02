"""Free-tier spend guard for the OpenRouter-based Bizro pipeline (D6-2).

The pipeline runs on OpenRouter's FREE tier — hard daily caps (~50 requests/day
to `:free` models, 20/min). Retries and demo loops can burn a whole day's
quota in seconds, so every live model call MUST pass through allow() first:

    import llm_guard
    llm_guard.allow(model)   # raises FreeTierBudgetExceeded over the budget
    ... post the chat/completions ...
    llm_guard.record(model, usage=resp.get("usage"))

The ledger is a tiny JSON file (data/openrouter-usage.json, machine-local,
gitignored) holding today's date, the per-day request count, and the last N
calls with token usage — printed by scripts/openrouter_live_test.py.

Provider-agnostic: counts every chat/completions inference call regardless of
which endpoint (OpenRouter now, DashScope if a voucher ever lands).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
LEDGER_PATH = Path(
    os.environ.get("OPENROUTER_LEDGER", str(REPO_ROOT / "data" / "openrouter-usage.json"))
)
BUDGET = int(os.environ.get("OPENROUTER_DAILY_BUDGET", "40"))
KEEP_CALLS = 50


class FreeTierBudgetExceeded(RuntimeError):
    """The daily free-tier request budget is exhausted — no more live calls."""


def _today() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d")


def _load() -> dict[str, Any]:
    if LEDGER_PATH.exists():
        try:
            data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "date" in data and "count" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": _today(), "count": 0, "calls": []}


def _save(data: dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["calls"] = data.get("calls", [])[-KEEP_CALLS:]
    LEDGER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _rolled(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("date") != _today():
        return {"date": _today(), "count": 0, "calls": []}
    return data


def spent_today() -> int:
    """Live inference requests made today (free GET /models calls not counted)."""
    return int(_rolled(_load()).get("count", 0))


def budget() -> int:
    return BUDGET


def allow(model: str) -> None:
    """Raise FreeTierBudgetExceeded when today's budget is spent. Call BEFORE
    every live chat/completions POST."""
    if os.environ.get("LLM_GUARD_OFF") == "1":
        return  # test run — fake transports must not pollute the ledger
    data = _rolled(_load())
    if int(data.get("count", 0)) >= BUDGET:
        raise FreeTierBudgetExceeded(
            f"OpenRouter free-tier budget exhausted for today ({data['count']}/{BUDGET} "
            f"calls). Raise OPENROUTER_DAILY_BUDGET or wait for the daily reset."
        )


def record(model: str, usage: dict[str, Any] | None = None) -> None:
    """Record one live inference call. Call right after a successful POST."""
    if os.environ.get("LLM_GUARD_OFF") == "1":
        return  # test run — fake transports must not pollute the ledger
    data = _rolled(_load())
    data["count"] = int(data.get("count", 0)) + 1
    calls = data.setdefault("calls", [])
    calls.append(
        {
            "ts": _dt.datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "prompt_tokens": (usage or {}).get("prompt_tokens"),
            "completion_tokens": (usage or {}).get("completion_tokens"),
        }
    )
    _save(data)
