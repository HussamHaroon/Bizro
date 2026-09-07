"""Derived inventory — stock per item, computed from EXISTING transactions.

Scope ruling (demo-week, inventory findings doc server/app/INVENTORY_FINDINGS.md):
inventory is DERIVED, not stored. Zero new tables, zero migrations. Per item:

    in_stock = Σ qty over `expense` item_lines          (goods IN  — supplier receipts)
             − Σ qty over `sale` + `udhar_given` lines  (goods OUT — schema.md §1:
               udhar_settlement is money-only, the goods already left at
               udhar_given time, so it never enters the math)

Item names merge through credit_agent.data_quality._norm_item (NFC → casefold →
Urdu-digit folding → whitespace collapse → punctuation strip) — the SAME
normalization the credit report's stock_coherence indicator uses (schema.md §9),
so this card and the officer report can never disagree about what an item is.

Honesty framing (§9 disclosure rule): a NEGATIVE in_stock is surfaced as data —
sold exceeding bought is usually just sales logged without item lines (schema.md
§1: item_lines ship on OCR expenses, often not on voice sales) — disclosed with
a flag word, never hidden and never "corrected".
"""

from __future__ import annotations

import importlib
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ensure_repo_root_on_path
from .db import Transaction

logger = logging.getLogger("bizro.inventory")

# "low" threshold: in_stock ≤ max(LOW_STOCK_FLOOR, LOW_STOCK_SHARE × bought).
LOW_STOCK_FLOOR = 2.0
LOW_STOCK_SHARE = 0.10

# Goods direction per kind (schema.md §1 — see module docstring).
GOODS_IN_KINDS = ("expense",)
GOODS_OUT_KINDS = ("sale", "udhar_given")


def _load_norm_item() -> Any:
    """credit_agent.data_quality._norm_item, lazily — mirrors dispatch.py's
    _load_pipeline_fn tolerance: the hyphenated credit-agent/ dir is added to
    sys.path by ensure_repo_root_on_path(); if the package is missing anyway,
    an identical local fallback keeps the endpoint alive (never a 500 over a
    normalization helper)."""
    try:
        ensure_repo_root_on_path()
        mod = importlib.import_module("credit_agent.data_quality")
        fn = getattr(mod, "_norm_item", None)
        if fn is not None:
            return fn
    except ImportError as exc:  # pragma: no cover - depends on layout
        logger.info("credit_agent.data_quality not importable (%s) — local _norm_item fallback.", exc)
    return _norm_item_local


def _norm_item_local(name: str) -> str:
    """Fallback twin of credit_agent.data_quality._norm_item (data_quality.py:39)."""
    import re
    import unicodedata

    s = unicodedata.normalize("NFC", name or "").casefold().translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    )
    return re.sub(r"[^\w\s]", "", re.sub(r"\s+", " ", s)).strip()


_norm_item = _load_norm_item()


def _lines(item_lines: Any) -> list:
    return item_lines if isinstance(item_lines, list) else []


def compute_inventory(session: Session, merchant_id: uuid.UUID) -> dict[str, Any]:
    """Per-item stock over one merchant's live (non-rejected) transactions.

    Returns {"merchant_id", "items": [...], "note"} — items sorted most-urgent
    first (negative, then low, then ok; alphabetical within a group) so the
    dashboard card reads top-down in decision order. Deterministic.
    """
    rows = session.execute(
        select(Transaction.kind, Transaction.item_lines).where(
            Transaction.merchant_id == merchant_id,
            Transaction.status != "rejected",
            Transaction.kind.in_([*GOODS_IN_KINDS, *GOODS_OUT_KINDS]),
        )
    ).all()

    bought: dict[str, float] = {}
    sold: dict[str, float] = {}
    units: dict[str, str | None] = {}
    for kind, item_lines in rows:
        bucket = bought if kind in GOODS_IN_KINDS else sold
        for line in _lines(item_lines):
            if not isinstance(line, dict):
                continue
            name = _norm_item(str(line.get("item") or ""))
            try:
                qty = float(line.get("qty") or 0)
            except (TypeError, ValueError):
                continue
            if not name or qty <= 0:
                continue
            bucket[name] = bucket.get(name, 0.0) + qty
            if name not in units:  # first-seen unit wins; may be None
                unit = line.get("unit")
                units[name] = str(unit) if unit else None

    _severity = {"negative": 0, "low": 1, "ok": 2}
    items: list[dict[str, Any]] = []
    for name in set(bought) | set(sold):
        b = bought.get(name, 0.0)
        s = sold.get(name, 0.0)
        in_stock = round(b - s, 2)
        if in_stock < 0:
            flag = "negative"
        elif in_stock <= max(LOW_STOCK_FLOOR, LOW_STOCK_SHARE * b):
            flag = "low"
        else:
            flag = "ok"
        items.append(
            {
                "item": name,
                "unit": units.get(name),
                "bought": round(b, 2),
                "sold": round(s, 2),
                "in_stock": in_stock,
                "flag": flag,
            }
        )
    items.sort(key=lambda it: (_severity[it["flag"]], it["item"]))

    return {
        "merchant_id": str(merchant_id),
        "items": items,
        "note": (
            "Derived from logged item lines: receipts add stock, sales and udhar "
            "remove it. 'negative' means more logged sold than bought — usually "
            "sales recorded without item lines, shown as a data-quality "
            "disclosure, not an accusation."
        ),
    }
