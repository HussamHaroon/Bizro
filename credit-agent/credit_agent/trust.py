"""Trust tiers & corroboration — who vouches for each entry (schema.md §12).

Server contract (§11): transactions carry nullable trust_tier —
'self_reported' | 'customer_confirmed' | 'third_party'; NULL reads as
self_reported. A tier is set by the merchant confirming in person
(customer_confirmed) or an out-of-band anchor such as the supplier
verification handshake (third_party) — never invented by this package.

What the report shows: the share of REVENUE (sale + udhar_settlement, the
kinds that make up cash_in in aggregates.py) that is corroborated, i.e.
vouched by someone other than the merchant. This is DISCLOSURE for the loan
officer — "how much of the stated revenue has a second voice behind it" —
NOT a truth score and NOT (yet) a scoring input (rubric.md documents how it
COULD weight into readiness later; the scoring math is unchanged).

Low corroboration is an honest, expected state for a fresh ledger, not an
accusation — the headline shows the number exactly as computed.
"""

from __future__ import annotations

from typing import Any

from .aggregates import CONFIRMED_STATUSES

SELF_REPORTED = "self_reported"
CUSTOMER_CONFIRMED = "customer_confirmed"
THIRD_PARTY = "third_party"

TIERS = (SELF_REPORTED, CUSTOMER_CONFIRMED, THIRD_PARTY)
CORROBORATING_TIERS = (CUSTOMER_CONFIRMED, THIRD_PARTY)

# Revenue kinds = the same two kinds aggregates.py sums into cash_in, so the
# corroboration share always describes the SAME revenue the report headlines.
REVENUE_KINDS = ("sale", "udhar_settlement")

NOTE = (
    "self-reported entries are merchant statements; "
    "confirmed/third-party entries are corroborated"
)


def normalize_tier(value: Any) -> str:
    """Unknown/NULL tiers read as self_reported — never silently upgraded."""
    return value if value in CORROBORATING_TIERS else SELF_REPORTED


def compute_trust(txs: list[Any]) -> dict:
    """Corroborated-revenue share over one reporting period. Deterministic;
    empty ledger → 0.0 (an honest zero, never a fabricated one)."""
    txs = [t for t in txs if getattr(t, "status", "") in CONFIRMED_STATUSES]
    revenue_by_tier = {tier: 0.0 for tier in TIERS}
    for t in txs:
        if t.kind not in REVENUE_KINDS:
            continue
        tier = normalize_tier(getattr(t, "trust_tier", None))
        revenue_by_tier[tier] += float(t.amount_pkr)

    revenue_by_tier = {tier: round(v, 2) for tier, v in revenue_by_tier.items()}
    total = round(sum(revenue_by_tier.values()), 2)
    corroborated = round(
        revenue_by_tier[CUSTOMER_CONFIRMED] + revenue_by_tier[THIRD_PARTY], 2
    )
    pct = round(corroborated / total * 100, 1) if total > 0 else 0.0
    return {
        "corroboration_pct": pct,
        "revenue_by_tier": revenue_by_tier,
        "corroborated_pkr": corroborated,
        "total_revenue_pkr": total,
        "note": NOTE,
    }
