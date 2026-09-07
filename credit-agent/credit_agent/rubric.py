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

# Two-way toggle (owner ruling 2026-09-07): when the OFFICER requires customer
# confirmation for a merchant, corroboration joins the rubric as a scored
# pillar and the four standing weights scale by 0.85 to renormalize
# (0.34 + 0.2125 + 0.17 + 0.1275 + 0.15 = 1.0). Default OFF = the four
# original weights, byte-identical scoring.
W_CORROBORATION = 0.15
_PILLAR_SCALE = 1.0 - W_CORROBORATION  # 0.85

# The ONE clause the ON readiness note appends (demo-eve constraint: short,
# no banner — the flag's only payload exposure is readiness.two_way_required).
TWO_WAY_NOTE_CLAUSE = (
    " · two-way confirmation required: unconfirmed revenue lowers this score"
)
TWO_WAY_NOTE_CLAUSE_UR = (
    " · دو طرفہ تصدیق لازمی ہے: بغیر تصدیق آمدنی اس سکور کو کم کرتی ہے"
)

BAND_READY = 75
BAND_NEARLY = 50

BAND_LABELS_UR = {
    "ready": "قرض کے لیے تیار",
    "nearly": "تقریباً تیار",
    "not_yet": "ابھی تیار نہیں",
    "insufficient_data": "معلومات کم ہے",
}

# Honest labeling (schema.md §12): EVERY surface that renders the score also
# renders this. The weights above are documented judgment, not validated
# against repayment outcomes — the label says so wherever the number appears.
INDICATOR_NOTE = "readiness indicator (not a validated repayment predictor)"
# Urdu alongside the English note (report readiness.note_ur, two-way ON only).
INDICATOR_NOTE_UR = "قرض کے لیے تیاری کا اشارہ (تصدیق شدہ ادائیگی کے رجحان کا پیمانہ نہیں)"

# The four limitations every consumer of a Bizro report must see (§12):
# self-reported inputs, no outcome validation, Urdu-centric parsing,
# heuristics not forensics. Single source of truth — report.py stores them
# in report_json.limitations and the committee one-pager renders them.
LIMITATIONS = [
    "All ledger inputs are merchant-self-reported; corroboration covers only "
    "the share vouched by a customer or third party.",
    "No outcome validation: the readiness score has never been checked "
    "against actual repayment data — treat it as a triage signal only.",
    "Parsing is Urdu/roman-Urdu-centric; entry quality varies with script, "
    "dialect and how the merchant speaks or types.",
    "Red flags and forensics are heuristics over ledger internals — patterns, "
    "not forensic verification.",
]


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


def score(
    agg: Aggregates,
    corroboration_pct: float | None = None,
    two_way_required: bool = False,
) -> Scored:
    """Readiness score. Default args keep every pre-toggle caller
    byte-identical: OFF (or no pct passed) is exactly the four-pillar rubric.

    When two_way_required and corroboration_pct is not None, a CORROBORATION
    pillar joins at weight 0.15 (raw = corroboration share of disbursement-
    eligible revenue, clamped 0..1) and the standing pillars scale by 0.85 —
    an unconfirmed ledger scores lower until customers confirm. Bands and the
    insufficient-data gate are unchanged."""
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
    if two_way_required and corroboration_pct is not None:
        raw = max(0.0, min(1.0, corroboration_pct / 100.0))
        pillars_raw["corroboration"] = (
            raw,
            f"corroborated revenue share {max(0.0, min(100.0, corroboration_pct)):.0f}%",
        )
        weights = {
            **{k: w * _PILLAR_SCALE for k, w in weights.items()},
            "corroboration": W_CORROBORATION,
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
