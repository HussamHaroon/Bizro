"""Readiness scoring rubric — deterministic, documented, auditable.

Full rationale: credit-agent/rubric.md. Thresholds live here as named constants so
tests can assert boundaries mechanically (bizro-testability: threshold tests are
boundary tests). Not a black-box number (idea.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from .aggregates import Aggregates, distinct_customers, span_days

MIN_ENTRIES = 14
MIN_WEEKS = 2
MIN_DAYS = 21

W_CONSISTENCY = 0.40
W_CONFIDENCE = 0.25
W_CASHFLOW = 0.20
W_CLEANLINESS = 0.15

BAND_READY = 75
BAND_NEARLY = 50

BAND_LABELS_UR = {
    "ready": "قرض کے لیے تیار",
    "nearly": "تقریباً تیار",
    "not_yet": "ابھی تیار نہیں",
    "insufficient_data": "معلومات کم ہے",
}


@dataclass
class Scored:
    score: int
    band: str
    label_ur: str
    pillars: dict  # name -> (raw 0..1, weight, note)


def _pillar_consistency(agg: Aggregates) -> tuple[float, str]:
    if agg.weeks_in_span == 0:
        return 0.0, "no weeks"
    regularity = min(1.0, agg.weeks_active / agg.weeks_in_span)
    density = min(1.0, agg.entries_per_week / 5.0)
    confirmed_share = 1.0 - (agg.pending_count / agg.total_entries if agg.total_entries else 0)
    raw = 0.5 * regularity + 0.3 * density + 0.2 * confirmed_share
    note = (
        f"active {agg.weeks_active}/{agg.weeks_in_span} weeks, "
        f"{agg.entries_per_week}/wk, {agg.pending_count} pending"
    )
    return max(0.0, min(1.0, raw)), note


def _pillar_confidence(agg: Aggregates) -> tuple[float, str]:
    if agg.median_confidence is None:
        return 0.0, "no AI-parsed entries"
    med = agg.median_confidence
    low_share = agg.low_confidence_count / agg.total_entries if agg.total_entries else 0
    raw = med - 0.5 * low_share
    note = f"median conf {med:.2f}, low-conf share {low_share:.0%}"
    return max(0.0, min(1.0, raw)), note


def _pillar_cashflow(agg: Aggregates) -> tuple[float, str]:
    positive = 1.0 if agg.net_cashflow > 0 else (0.4 if agg.net_cashflow == 0 else 0.0)
    breadth = min(1.0, distinct_customers(agg) / 5.0)
    raw = 0.6 * positive + 0.4 * breadth
    note = f"net PKR {agg.net_cashflow:,.0f}, {distinct_customers(agg)} udhar customers"
    return max(0.0, min(1.0, raw)), note


def _pillar_cleanliness(agg: Aggregates) -> tuple[float, str]:
    flags = sum(agg.flag_counts.values())
    density = flags / agg.total_entries if agg.total_entries else 0
    raw = 1.0 - min(1.0, density * 2)
    note = f"{flags} flagged of {agg.total_entries}"
    return max(0.0, min(1.0, raw)), note


def score(agg: Aggregates) -> Scored:
    if (
        agg.total_entries < MIN_ENTRIES
        or agg.weeks_active < MIN_WEEKS
        or span_days(agg) < MIN_DAYS
    ):
        return Scored(
            score=0,
            band="insufficient_data",
            label_ur=BAND_LABELS_UR["insufficient_data"],
            pillars={},
        )

    pillars_raw = {
        "consistency": _pillar_consistency(agg),
        "confidence": _pillar_confidence(agg),
        "cashflow": _pillar_cashflow(agg),
        "cleanliness": _pillar_cleanliness(agg),
    }
    weights = {
        "consistency": W_CONSISTENCY,
        "confidence": W_CONFIDENCE,
        "cashflow": W_CASHFLOW,
        "cleanliness": W_CLEANLINESS,
    }
    total = sum(pillars_raw[k][0] * weights[k] for k in weights)
    sc = round(total * 100)
    band = "ready" if sc >= BAND_READY else "nearly" if sc >= BAND_NEARLY else "not_yet"
    return Scored(
        score=sc,
        band=band,
        label_ur=BAND_LABELS_UR[band],
        pillars={k: (round(v[0], 3), weights[k], v[1]) for k, v in pillars_raw.items()},
    )
