"""Trust tiers & corroboration tests (schema.md §12).

Offline, deterministic. Corroboration share = (customer_confirmed +
third_party revenue) / total revenue over sale + udhar_settlement entries —
the same two kinds aggregates.py sums into cash_in, so the headline always
describes the same revenue the report shows. NULL/unknown tiers read as
self_reported — never silently upgraded.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.db_view import Base, get_sessionmaker
from credit_agent.report import generate_report
from credit_agent.render import render_report_html
from credit_agent.seed import seed_demo
from credit_agent.trust import (
    CUSTOMER_CONFIRMED,
    SELF_REPORTED,
    THIRD_PARTY,
    compute_trust,
    normalize_tier,
)


def _tx(kind="sale", amount=1000.0, tier=None, status="confirmed"):
    return SimpleNamespace(
        kind=kind, amount_pkr=amount, trust_tier=tier, status=status
    )


def test_corroboration_pct_is_corroborated_revenue_over_total():
    txs = [
        _tx("sale", 1000.0, tier=SELF_REPORTED),
        _tx("sale", 1000.0, tier=None),                       # NULL = self_reported
        _tx("sale", 1000.0, tier=CUSTOMER_CONFIRMED),
        _tx("udhar_settlement", 1000.0, tier=THIRD_PARTY),
        _tx("expense", 5000.0, tier=THIRD_PARTY),             # not revenue — ignored
        _tx("udhar_given", 5000.0, tier=CUSTOMER_CONFIRMED),  # not revenue — ignored
    ]
    trust = compute_trust(txs)
    assert trust["revenue_by_tier"][SELF_REPORTED] == 2000.0
    assert trust["revenue_by_tier"][CUSTOMER_CONFIRMED] == 1000.0
    assert trust["revenue_by_tier"][THIRD_PARTY] == 1000.0
    assert trust["total_revenue_pkr"] == 4000.0
    assert trust["corroboration_pct"] == 50.0
    assert trust["note"] == (
        "self-reported entries are merchant statements; "
        "confirmed/third-party entries are corroborated"
    )


def test_empty_and_rejected_ledgers_report_honest_zero():
    assert compute_trust([])["corroboration_pct"] == 0.0
    assert compute_trust([_tx("sale", 1000.0, status="rejected")])[
        "corroboration_pct"
    ] == 0.0
    assert compute_trust([_tx("sale", 1000.0)])["revenue_by_tier"][SELF_REPORTED] == 1000.0


def test_unknown_tier_never_upgraded():
    assert normalize_tier(None) == SELF_REPORTED
    assert normalize_tier("boss_said_so") == SELF_REPORTED
    assert normalize_tier(THIRD_PARTY) == THIRD_PARTY
    trust = compute_trust([_tx("sale", 1000.0, tier="boss_said_so")])
    assert trust["corroboration_pct"] == 0.0
    assert trust["revenue_by_tier"][SELF_REPORTED] == 1000.0


def _db(tmp_path, name="t.db"):
    url = f"sqlite:///{tmp_path / name}"
    from sqlalchemy import create_engine

    Base.metadata.create_all(create_engine(url))
    return url


def _mk_merchant(session, name="Trust Store"):
    from credit_agent.db_view import Merchant

    m = Merchant(id=uuid.uuid4(), wa_id="wa", display_name=name)
    session.add(m)
    session.commit()
    return m.id


def _tx_row(session, mid, kind="sale", amount=1000.0, tier=None, days_ago=1):
    from credit_agent.db_view import Transaction

    session.add(Transaction(
        id=uuid.uuid4(), merchant_id=mid, kind=kind, amount_pkr=amount,
        description=f"{kind}", occurred_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        source_type="voice", source_media_id=uuid.uuid4(), source_model="qwen-flash",
        confidence=0.9, flag="none", status="confirmed", trust_tier=tier,
    ))


def test_report_carries_trust_block_and_trust_tier_survives_db(tmp_path):
    """The mirror round-trips trust_tier and report_json.trust reflects it —
    the column is mirrored NOW, ahead of the server merge (context contract)."""
    url = _db(tmp_path)
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _tx_row(s, mid, "sale", 3000.0, tier=None)
        _tx_row(s, mid, "sale", 3000.0, tier=SELF_REPORTED)
        _tx_row(s, mid, "udhar_settlement", 4000.0, tier=CUSTOMER_CONFIRMED, days_ago=2)
        s.commit()
    report = generate_report(mid, db_url=url)
    trust = report["trust"]
    assert trust["total_revenue_pkr"] == 10000.0
    assert trust["corroborated_pkr"] == 4000.0
    assert trust["corroboration_pct"] == 40.0

    html = render_report_html(report)
    assert "Corroborated revenue:" in html
    assert "40.0%" in html
    assert "merchant statements" in html


def test_headline_shows_honest_zero_when_all_self_reported(tmp_path):
    url = _db(tmp_path, "zero.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _tx_row(s, mid, "sale", 1500.0, tier=SELF_REPORTED)
        _tx_row(s, mid, "sale", 2500.0, tier=None)
        s.commit()
    html = render_report_html(generate_report(mid, db_url=url))
    assert "Corroborated revenue:" in html
    assert "0.0%" in html  # low is fine — shown, never hidden


def test_headline_absent_on_legacy_payload_without_trust_block():
    report = {
        "merchant": {"name": "Legacy"},
        "period": {"label": "Jun 6, 2026 - Sep 1, 2026"},
        "readiness": {"band": "nearly", "score": 60},
        "red_flags": [], "line_items": [], "metrics": [],
        "model": "m", "model_provider": "OpenRouter",
        "generated_at_display": "Sep 3, 2026, 7:51 pm",
    }
    assert "Corroborated revenue" not in render_report_html(report)


def test_seed_emits_realistic_tier_mix(tmp_path):
    """Seeded demo history must show real states: mostly self_reported, some
    customer_confirmed, at least one third_party entry (deterministic mix)."""
    mid = seed_demo(f"sqlite:///{tmp_path / 'seed.db'}")
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    Session = get_sessionmaker(url)
    with Session() as s:
        from sqlalchemy import func, select

        from credit_agent.db_view import Transaction

        counts = dict(s.execute(
            select(Transaction.trust_tier, func.count())
            .where(Transaction.merchant_id == uuid.UUID(mid))
            .group_by(Transaction.trust_tier)
        ).all())
    report = generate_report(mid, db_url=url)
    assert counts.get(None, 0) + counts.get(SELF_REPORTED, 0) > counts.get(
        CUSTOMER_CONFIRMED, 0
    ), "mostly self-reported"
    assert counts.get(CUSTOMER_CONFIRMED, 0) >= 3, "some customer-confirmed"
    assert counts.get(THIRD_PARTY, 0) >= 1, "a few third-party (supplier handshake)"
    # and the report's corroboration share sits strictly inside (0, 100)
    assert 0.0 < report["trust"]["corroboration_pct"] < 100.0
