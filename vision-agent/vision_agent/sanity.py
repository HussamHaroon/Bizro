"""Price-sanity checks computed from transaction history (schema.md §1 flags).

Three flags, all computable from the transactions table — no new tables:
- price_anomaly     unit price far from the merchant's historical median for a
                    similar item (fuzzy name match, notes.md D-V2)
- total_mismatch    Σ line totals ≠ stated receipt total (beyond tolerance)
- duplicate_suspect same supplier + same amount inside a short time window

Pure functions over plain dicts (the schema.md §1 wire format) so the server
can reuse them and tests need no database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from statistics import median
from typing import Any, Iterable

from vision_agent.schemas import ReceiptExtraction

SIMILARITY_THRESHOLD = 0.8  # difflib ratio for "similar item" matching


def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


@dataclass
class FlagDetail:
    kind: str  # price_anomaly | total_mismatch | duplicate_suspect
    message: str  # English detail for the audit trail / dashboard
    data: dict[str, Any]  # machine-readable evidence


# ------------------------------------------------------------- price anomaly


def historical_unit_prices(item_name: str, history: Iterable[dict[str, Any]]) -> list[float]:
    """Collect historical unit prices for a similar item, most-recent-first."""
    prices: list[float] = []
    for tx in history:
        if tx.get("kind") != "expense":
            continue
        for line in tx.get("item_lines") or []:
            other = line.get("item") or ""
            if not other:
                continue
            if similar(item_name, other) >= SIMILARITY_THRESHOLD:
                price = line.get("unit_price")
                if isinstance(price, (int, float)) and price > 0:
                    prices.append(float(price))
    return prices


def check_price_anomaly(
    item_lines: list[dict[str, Any]],
    history: Iterable[dict[str, Any]],
    ratio_threshold: float,
    min_samples: int,
    window: int,
) -> FlagDetail | None:
    """Flag the first line whose unit price deviates > ratio from history median.

    Requires at least ``min_samples`` historical prices for that item; the
    median is over the last ``window`` prices.
    """
    for line in item_lines:
        name = line.get("item") or ""
        price = line.get("unit_price")
        if not name or not isinstance(price, (int, float)):
            continue
        prices = historical_unit_prices(name, history)[:window]
        if len(prices) < min_samples:
            continue
        hist_median = float(median(prices))
        if hist_median <= 0:
            continue
        deviation = abs(price - hist_median) / hist_median
        if deviation > ratio_threshold:
            return FlagDetail(
                kind="price_anomaly",
                message=(
                    f"unit price for {name!r} is {price:g} PKR vs historical median "
                    f"{hist_median:g} PKR ({deviation:.0%} deviation)"
                ),
                data={
                    "item": name,
                    "unit_price": price,
                    "historical_median": hist_median,
                    "historical_prices": prices,
                    "deviation_ratio": round(deviation, 4),
                },
            )
    return None


# ------------------------------------------------------------ total mismatch


def computed_line_total(line: dict[str, Any]) -> float | None:
    qty, price = line.get("qty"), line.get("unit_price")
    if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
        return round(float(qty) * float(price), 2)
    total = line.get("line_total")
    return round(float(total), 2) if isinstance(total, (int, float)) else None


def check_total_mismatch(
    extraction: ReceiptExtraction, tolerance_pkd: float
) -> FlagDetail | None:
    """Σ(qty × unit_price) vs the stated total, beyond max(tolerance, 0.5%)."""
    computed = round(
        sum(
            (
                computed_line_total(
                    {"qty": item.qty, "unit_price": item.unit_price}
                )
                or 0.0
            )
            for item in extraction.items
        ),
        2,
    )
    stated = extraction.stated_total
    if stated is None or computed <= 0:
        return None
    slack = max(tolerance_pkd, computed * 0.005)
    if abs(stated - computed) > slack + 1e-9:
        return FlagDetail(
            kind="total_mismatch",
            message=(
                f"receipt states total {stated:g} PKR but items sum to "
                f"{computed:g} PKR"
            ),
            data={"stated_total": stated, "computed_total": computed},
        )
    return None


# --------------------------------------------------------- duplicate suspect


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def check_duplicate_suspect(
    supplier: str | None,
    amount_pkr: float,
    occurred_at: Any,
    history: Iterable[dict[str, Any]],
    window_minutes: int,
) -> FlagDetail | None:
    """Same normalized supplier + same amount within the window (any status
    except rejected — a pending duplicate is exactly the double-send case)."""
    when = _parse_dt(occurred_at)
    if when is None:
        return None
    supplier_norm = normalize_name(supplier) if supplier else ""
    for tx in history:
        if tx.get("kind") != "expense" or tx.get("status") == "rejected":
            continue
        other_party = (tx.get("counterparty") or {}).get("name") or ""
        if supplier_norm and normalize_name(other_party) != supplier_norm:
            continue
        other_amount = tx.get("amount_pkr")
        if not isinstance(other_amount, (int, float)) or abs(other_amount - amount_pkr) > 1e-9:
            continue
        other_when = _parse_dt(tx.get("occurred_at"))
        if other_when is None:
            continue
        delta_minutes = abs((when - other_when).total_seconds()) / 60.0
        if delta_minutes <= window_minutes:
            return FlagDetail(
                kind="duplicate_suspect",
                message=(
                    f"same supplier ({supplier or 'unknown'}) + amount "
                    f"{amount_pkr:g} PKR recorded {delta_minutes:.0f} min apart"
                ),
                data={
                    "supplier": supplier,
                    "amount_pkr": amount_pkr,
                    "minutes_apart": round(delta_minutes, 1),
                },
            )
    return None


# ----------------------------------------------------------------- evaluation

# Precedence for the single-valued flag (notes.md D-V2).
PRECEDENCE = ("low_confidence", "total_mismatch", "price_anomaly", "duplicate_suspect")


def evaluate_flags(
    low_confidence: bool,
    extraction: ReceiptExtraction,
    history: list[dict[str, Any]],
    supplier: str | None,
    amount_pkr: float,
    occurred_at: Any,
    *,
    ratio_threshold: float,
    min_samples: int,
    history_window: int,
    total_tolerance_pkd: float,
    duplicate_window_minutes: int,
) -> tuple[str, list[FlagDetail]]:
    """Run all checks; return the winning flag + every detail for the audit trail."""
    details: list[FlagDetail] = []
    if dup := check_duplicate_suspect(
        supplier, amount_pkr, occurred_at, history, duplicate_window_minutes
    ):
        details.append(dup)
    if anomaly := check_price_anomaly(
        [
            {"item": item.item, "unit": item.unit, "qty": item.qty, "unit_price": item.unit_price}
            for item in extraction.items
        ],
        history,
        ratio_threshold,
        min_samples,
        history_window,
    ):
        details.append(anomaly)
    if mismatch := check_total_mismatch(extraction, total_tolerance_pkd):
        details.append(mismatch)

    present = {detail.kind for detail in details}
    if low_confidence:
        present.add("low_confidence")
    flag = next((kind for kind in PRECEDENCE if kind in present), "none")
    return flag, details
