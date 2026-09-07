"""Merchant insights — demand timing, restock urgency, price movers.

Scope ruling (demo-week, qa/reviews/2026-09-07-insights-findings.md): all three
insights are DERIVED from data the ledger already holds — item_lines +
occurred_at + unit_price. Zero new tables, zero migrations, no forecasting
claims, no ML. Patterns are presented AS patterns ("Based on your last N
days"), never predictions; an empty ledger yields exactly three empty lists —
numbers are never invented.

- demand_timing: per top item from `sale` + `udhar_given` item_lines (goods
  OUT, schema.md §1), units by PKT day-of-week and daypart bucket (morning
  <12, afternoon 12-17, evening ≥17) → best day + best window + a weekly unit
  RATE (an average over the observed window, not a forecast).
- restock_now: CONSUMES server/app/inventory.py::compute_inventory — the
  bought/sold/flag stock math is never duplicated here. Items flagged
  low/negative are ranked by recent weekly demand (same goods-OUT lines).
- price_trends: per item from `expense` item_lines (the lines that reliably
  carry unit_price), median unit price in the first half vs the second half of
  the item's observations → pct change + direction.

Item names merge through credit_agent.data_quality._norm_item — the SAME
normalization the §9 stock_coherence indicator (data_quality.py:102) and the
inventory endpoint (inventory.py:104) use, so these cards and the officer
report can never disagree about what an item is.
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

from .data_quality import _norm_item

logger = logging.getLogger("bizro.insights")

# PKT = UTC+5. SQLite rows come back naive-UTC (dispatch.py:255-264 normalizes
# to UTC before storage; aggregates.py:46 reads naive as UTC) — naive input is
# therefore read as UTC and shifted.
PKT = timezone(timedelta(hours=5))

# Goods direction per kind (schema.md §1 — same mapping as inventory.py:42-43).
DEMAND_KINDS = ("sale", "udhar_given")
PRICE_KIND = "expense"

# Demand: top items by units, then a minimum below which a "best day" is
# noise rather than a pattern (a 2-unit item has no meaningful peak).
DEMAND_TOP_ITEMS = 5
DEMAND_MIN_UNITS = 3.0

# Restock: rank flagged items by demand over the trailing month of the window.
RECENT_DAYS = 28
RESTOCK_MAX = 8
RESTOCK_FLAGS = ("low", "negative")
_FLAG_SEVERITY = {"negative": 0, "low": 1}

# Price trends: fewer than 2 observations per half is a receipt flip, not a
# trend; |pct| within ±1% prints as "flat" (rounding noise, no signal).
PRICE_MIN_OBS = 2
PRICE_FLAT_PCT = 1.0
PRICE_MAX = 6

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PARTS = ("morning", "afternoon", "evening")  # morning <12, afternoon 12-17, evening >=17


def _lines(item_lines: Any) -> list:
    return item_lines if isinstance(item_lines, list) else []


def _fpos(v: Any) -> float | None:
    """Positive finite float or None — NaN/inf/≤0 all fail the `> 0` guard
    (same defensive read as data_quality.py:102-105 / inventory.py:105-108)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f < float("inf") else None


def _pkt(dt):
    """occurred_at → PKT-aware datetime; naive reads as UTC (see PKT above).
    The merchant's LOCAL day is the truth: a 20:00 UTC entry is 01:00 PKT —
    the NEXT day's buckets."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PKT)


def _aware_utc(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _span_days(txs: list[Any]) -> int:
    """Inclusive day span of the txs' occurred_at (min 1 when any exist)."""
    times = [_aware_utc(t.occurred_at) for t in txs if getattr(t, "occurred_at", None) is not None]
    if not times:
        return 0
    return max(1, (max(times) - min(times)).days + 1)


def _median(xs: list[float]) -> float:
    """Plain sorted-list median (even count → mean of the middle two). Single
    OCR misreads cannot dominate the way they can a mean."""
    ys = sorted(xs)
    mid = len(ys) // 2
    if len(ys) % 2:
        return ys[mid]
    return (ys[mid - 1] + ys[mid]) / 2.0


def _demand_timing(txs: list[Any], span_days: int) -> list[dict[str, Any]]:
    if span_days <= 0:
        return []
    recs: dict[str, dict[str, Any]] = {}
    for t in txs:
        if getattr(t, "kind", "") not in DEMAND_KINDS:
            continue
        when = getattr(t, "occurred_at", None)
        if when is None:
            continue
        pkt = _pkt(when)
        dow = pkt.weekday()
        part = PARTS[0] if pkt.hour < 12 else PARTS[1] if pkt.hour < 17 else PARTS[2]
        for line in _lines(getattr(t, "item_lines", None)):
            if not isinstance(line, dict):
                continue
            name = _norm_item(str(line.get("item") or ""))
            qty = _fpos(line.get("qty"))
            if not name or qty is None:
                continue
            rec = recs.setdefault(name, {"dow": {}, "part": {}, "units": 0.0})
            rec["dow"][dow] = rec["dow"].get(dow, 0.0) + qty
            rec["part"][part] = rec["part"].get(part, 0.0) + qty
            rec["units"] += qty

    out: list[dict[str, Any]] = []
    top = sorted(recs.items(), key=lambda kv: (-kv[1]["units"], kv[0]))[:DEMAND_TOP_ITEMS]
    for name, rec in top:
        if rec["units"] < DEMAND_MIN_UNITS:
            continue
        best_dow = min(rec["dow"].items(), key=lambda kv: (-kv[1], kv[0]))[0]
        best_part = min(rec["part"].items(), key=lambda kv: (-kv[1], PARTS.index(kv[0])))[0]
        out.append(
            {
                "item": name,
                "best_day": DAY_NAMES[best_dow],
                "best_window": best_part,
                # A rate over the observed window — presented as a pattern of
                # the past, never a forecast of the future.
                "weekly_units": round(rec["units"] * 7.0 / span_days, 1),
                "note": f"Based on your last {span_days} days",
            }
        )
    return out


def _load_compute_inventory():
    """server.app.inventory.compute_inventory, lazily — the restock list must
    CONSUME the inventory math, never duplicate it. Tolerant in the same spirit
    as inventory.py's _load_norm_item (inventory.py:46-60): the repo root is
    added to sys.path if needed; if the server package is unreachable anyway,
    None → the restock list degrades to [] (never a 500 over a helper)."""
    try:
        from server.app.inventory import compute_inventory  # type: ignore

        return compute_inventory
    except ImportError:
        pass
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from server.app.inventory import compute_inventory  # type: ignore

        return compute_inventory
    except ImportError as exc:  # pragma: no cover - depends on layout
        logger.info("server.app.inventory not importable (%s) — restock list degrades to empty.", exc)
        return None


def insights_inventory_items(session: Any, merchant_id: Any) -> list[dict[str, Any]] | None:
    """compute_inventory(session, merchant_id)["items"] through the lazy loader.
    None when the server package is unreachable → restock_now degrades to []
    while demand timing and price trends still compute. The caller's session
    (mirror or server) is bound to the same DB compute_inventory reads."""
    fn = _load_compute_inventory()
    if fn is None:
        return None
    return fn(session, merchant_id).get("items")


def _restock(
    txs: list[Any],
    inventory_items: list[dict[str, Any]] | None,
    span_days: int,
) -> list[dict[str, Any]]:
    """Flagged (low/negative) inventory items ranked by recent weekly demand.
    Stock levels ride in VERBATIM from compute_inventory — no duplicated math."""
    if not inventory_items:
        return []

    ends = [_aware_utc(t.occurred_at) for t in txs if getattr(t, "occurred_at", None) is not None]
    if not ends:
        return []
    cutoff = max(ends) - timedelta(days=RECENT_DAYS)

    recent: dict[str, float] = {}
    for t in txs:
        if getattr(t, "kind", "") not in DEMAND_KINDS:
            continue
        when = getattr(t, "occurred_at", None)
        if when is None or _aware_utc(when) < cutoff:
            continue
        for line in _lines(getattr(t, "item_lines", None)):
            if not isinstance(line, dict):
                continue
            name = _norm_item(str(line.get("item") or ""))
            qty = _fpos(line.get("qty"))
            if not name or qty is None:
                continue
            recent[name] = recent.get(name, 0.0) + qty

    weeks = max(1.0, min(RECENT_DAYS, span_days) / 7.0)
    rows: list[dict[str, Any]] = []
    for it in inventory_items:
        if not isinstance(it, dict) or it.get("flag") not in RESTOCK_FLAGS:
            continue
        name = str(it.get("item") or "")
        if not name:
            continue
        rows.append(
            {
                "item": name,
                "unit": it.get("unit"),
                "in_stock": it.get("in_stock"),
                "flag": it.get("flag"),
                "weekly_demand": round(recent.get(name, 0.0) / weeks, 1),
                "note": f"Based on your last {span_days} days",
            }
        )
    # Spec ranking: recent weekly demand first; a negative flag breaks ties
    # (already oversold beats merely low); name last for determinism.
    rows.sort(key=lambda r: (-r["weekly_demand"], _FLAG_SEVERITY.get(r["flag"], 9), r["item"]))
    return rows[:RESTOCK_MAX]


def _price_trends(txs: list[Any], span_days: int) -> list[dict[str, Any]]:
    obs: dict[str, list[tuple[Any, float, Any]]] = {}
    for t in txs:
        if getattr(t, "kind", "") != PRICE_KIND:
            continue
        when = getattr(t, "occurred_at", None)
        if when is None:
            continue
        w = _aware_utc(when)
        for line in _lines(getattr(t, "item_lines", None)):
            if not isinstance(line, dict):
                continue
            name = _norm_item(str(line.get("item") or ""))
            price = _fpos(line.get("unit_price"))
            if not name or price is None:
                continue
            obs.setdefault(name, []).append((w, price, line.get("unit")))

    rows: list[dict[str, Any]] = []
    for name, points in obs.items():
        points.sort(key=lambda p: p[0])
        half = len(points) // 2
        first = [p[1] for p in points[:half]]
        second = [p[1] for p in points[half:]]
        if len(first) < PRICE_MIN_OBS or len(second) < PRICE_MIN_OBS:
            continue
        m1, m2 = _median(first), _median(second)
        if m1 <= 0:
            continue
        pct = round((m2 - m1) / m1 * 100.0, 1)
        direction = "up" if pct >= PRICE_FLAT_PCT else "down" if pct <= -PRICE_FLAT_PCT else "flat"
        rows.append(
            {
                "item": name,
                "unit": points[0][2],  # first-seen unit wins (inventory.py:112-114 convention)
                "first_median": round(m1, 2),
                "second_median": round(m2, 2),
                "pct_change": pct,
                "direction": direction,
                "note": f"Based on your last {span_days} days",
            }
        )
    rows.sort(key=lambda r: (-abs(r["pct_change"]), r["item"]))
    return rows[:PRICE_MAX]


def compute_insights(
    txs: list[Any],
    inventory_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """All three insights over one merchant's transactions.

    `txs` are the window's rows (endpoint: last 90 days; report: its period).
    `inventory_items` is compute_inventory's ["items"] — pass it when the
    server package is importable so restock can rank REAL stock flags; without
    it restock_now is [] (never approximated here). Deterministic; an empty
    ledger returns exactly {"demand_timing": [], "restock_now": [],
    "price_trends": []} — never invented numbers."""
    active = [t for t in txs if getattr(t, "status", "") != "rejected"]
    span = _span_days(active)
    return {
        "demand_timing": _demand_timing(active, span),
        "restock_now": _restock(active, inventory_items, span),
        "price_trends": _price_trends(active, span),
    }
