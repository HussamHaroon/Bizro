"""Two-way toggle — rubric + report semantics (owner ruling 2026-09-07).

A per-merchant `two_way_confirmation_required` flag (DEFAULT OFF, flipped by
the OFFICER) turns customer corroboration into a scored readiness pillar:

- OFF: EXACTLY the pre-toggle rubric — score, pillars and readiness.note are
  byte-identical; corroboration_pct stays an informational headline.
- ON: +0.15 CORROBORATION pillar (raw = corroboration share of revenue),
  standing pillars x 0.85; bands and the insufficient-data gate unchanged.

Demo-eve contract tested here: the OFF path never moves a demo number.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.aggregates import compute_aggregates
from credit_agent.db_view import Base, Customer, Merchant, Transaction, get_sessionmaker
from credit_agent.report import generate_report
from credit_agent.rubric import (
    INDICATOR_NOTE,
    INDICATOR_NOTE_UR,
    TWO_WAY_NOTE_CLAUSE,
    TWO_WAY_NOTE_CLAUSE_UR,
    W_CLEANLINESS,
    W_CONFIDENCE,
    W_CONSISTENCY,
    W_CORROBORATION,
    W_CASHFLOW,
    _pillar_cleanliness,
    _pillar_confidence,
    _pillar_consistency,
    _pillar_cashflow,
    score,
)


def _db(db_file, with_settings=False):
    url = f"sqlite:///{db_file}"
    Base.metadata.create_all(create_engine(url))
    if with_settings:
        # Minimal settings table (server §8 shape reduced to what the flag
        # reader touches) — the server's full model lives in server/app/db.py.
        with create_engine(url).begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE merchant_settings ("
                    "merchant_id TEXT PRIMARY KEY, "
                    "two_way_confirmation_required BOOLEAN NOT NULL DEFAULT 0)"
                )
            )
    return url


def _mk_merchant(session, name="Test Store"):
    m = Merchant(id=uuid.uuid4(), wa_id="wa", display_name=name)
    session.add(m)
    session.commit()
    return m.id


def _seed_healthy_ledger(session, mid):
    """Deterministic 12-week ledger mirroring test_report.py's healthy shape —
    a mid-band score where corroboration movement is unambiguous."""
    cust = Customer(id=uuid.uuid4(), merchant_id=mid, name="Ahmad")
    session.add(cust)
    session.commit()
    for day in range(84, 0, -2):  # 42 entries over 12 weeks
        session.add(Transaction(
            id=uuid.uuid4(), merchant_id=mid, kind="sale", amount_pkr=2000 + day,
            description=f"sale {day}",
            occurred_at=datetime.now(timezone.utc) - timedelta(days=day),
            source_type="voice", source_media_id=uuid.uuid4(),
            source_model="qwen3.5-omni-plus", confidence=0.9, status="confirmed",
        ))
    for day in range(80, 0, -7):
        session.add(Transaction(
            id=uuid.uuid4(), merchant_id=mid, customer_id=cust.id, kind="udhar_given",
            amount_pkr=1500, description=f"udhar {day}",
            occurred_at=datetime.now(timezone.utc) - timedelta(days=day),
            source_type="voice", source_media_id=uuid.uuid4(),
            source_model="qwen3.5-omni-plus", confidence=0.9, status="confirmed",
        ))
    for day in range(76, 0, -7):
        session.add(Transaction(
            id=uuid.uuid4(), merchant_id=mid, customer_id=cust.id, kind="udhar_settlement",
            amount_pkr=700, description=f"settle {day}",
            occurred_at=datetime.now(timezone.utc) - timedelta(days=day),
            source_type="voice", source_media_id=uuid.uuid4(),
            source_model="qwen3.5-omni-plus", confidence=0.9, status="confirmed",
        ))
    session.commit()


def _agg_from_db(url, mid):
    Session = get_sessionmaker(url)
    with Session() as s:
        txs = s.scalars(
            select(Transaction).where(Transaction.merchant_id == mid)
        ).all()
        cust_ids = {t.customer_id for t in txs if t.customer_id}
        customers = {
            c.id: c for c in s.scalars(select(Customer).where(Customer.id.in_(cust_ids)))
        }
        return compute_aggregates(list(txs), customers, now=datetime.now(timezone.utc))


@pytest.fixture()
def scored_agg(tmp_path):
    url = _db(tmp_path / "agg.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _seed_healthy_ledger(s, mid)
    return _agg_from_db(url, mid)


# ===================== rubric: OFF is byte-identical =========================


def test_off_flag_score_is_exactly_the_pre_toggle_rubric(scored_agg):
    """Default args AND an explicit False with a pct present must both return
    the untouched four-pillar result — corroboration is ignored when OFF."""
    pre_toggle = score(scored_agg)
    assert pre_toggle.score > 0, "fixture must produce a scorable ledger"
    assert score(scored_agg, corroboration_pct=87.5, two_way_required=False) == pre_toggle
    assert score(scored_agg, corroboration_pct=0.0, two_way_required=False) == pre_toggle

    # hand-computed with the original constants over the UNROUNDED pillar
    # values — no weight drift slipped in
    raws = {
        "consistency": _pillar_consistency(scored_agg)[0],
        "confidence": _pillar_confidence(scored_agg)[0],
        "cashflow": _pillar_cashflow(scored_agg)[0],
        "cleanliness": _pillar_cleanliness(scored_agg)[0],
    }
    expected = round(100 * (
        raws["consistency"] * W_CONSISTENCY
        + raws["confidence"] * W_CONFIDENCE
        + raws["cashflow"] * W_CASHFLOW
        + raws["cleanliness"] * W_CLEANLINESS
    ))
    assert pre_toggle.score == expected
    assert set(pre_toggle.pillars) == {"consistency", "confidence", "cashflow", "cleanliness"}
    assert pre_toggle.pillars["consistency"][1] == W_CONSISTENCY  # unscaled


# ===================== rubric: ON adds the pillar ============================


def test_on_adds_corroboration_pillar_and_renormalizes(scored_agg):
    s_on = score(scored_agg, corroboration_pct=80.0, two_way_required=True)
    assert "corroboration" in s_on.pillars
    raw, weight, note = s_on.pillars["corroboration"]
    assert raw == 0.8 and weight == W_CORROBORATION
    assert "80%" in note

    assert s_on.pillars["consistency"][1] == W_CONSISTENCY * 0.85
    assert s_on.pillars["confidence"][1] == W_CONFIDENCE * 0.85
    assert s_on.pillars["cashflow"][1] == W_CASHFLOW * 0.85
    assert s_on.pillars["cleanliness"][1] == W_CLEANLINESS * 0.85
    assert abs(sum(w for _, w, _ in s_on.pillars.values()) - 1.0) < 1e-9

    # the raw pillar values of the standing pillars are untouched
    pre = score(scored_agg)
    for name in ("consistency", "confidence", "cashflow", "cleanliness"):
        assert s_on.pillars[name][0] == pre.pillars[name][0]


def test_on_score_semantics_across_corroboration_levels(scored_agg):
    """The owner table: OFF vs ON x corroboration 0 / 50 / 100."""
    off = score(scored_agg).score
    on_0 = score(scored_agg, 0.0, True).score
    on_50 = score(scored_agg, 50.0, True).score
    on_100 = score(scored_agg, 100.0, True).score
    assert on_0 < off, "an unconfirmed ledger must score lower under two-way"
    assert on_100 >= off, "full corroboration must never score below OFF"
    assert on_0 < on_50 < on_100


def test_corroboration_pct_clamped_0_to_1(scored_agg):
    high = score(scored_agg, 150.0, True)
    assert high.pillars["corroboration"][0] == 1.0
    low = score(scored_agg, -5.0, True)
    assert low.pillars["corroboration"][0] == 0.0
    assert low.score == score(scored_agg, 0.0, True).score


def test_insufficient_data_gate_unchanged_under_two_way(tmp_path):
    url = _db(tmp_path / "thin.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        now = datetime.now(timezone.utc)
        for i in range(3):  # far below MIN_ENTRIES
            s.add(Transaction(
                id=uuid.uuid4(), merchant_id=mid, kind="sale", amount_pkr=100,
                occurred_at=now - timedelta(days=i * 2), source_type="voice",
                source_media_id=uuid.uuid4(), source_model="m", confidence=0.9,
                status="confirmed",
            ))
        s.commit()
    s_on = score(_agg_from_db(url, mid), corroboration_pct=100.0, two_way_required=True)
    assert s_on.band == "insufficient_data"
    assert s_on.score == 0 and s_on.pillars == {}


# ===================== report: flag read + payload contract ==================


def test_report_off_path_is_byte_identical(tmp_path):
    """THE demo-safety proof: with the flag OFF (no settings row at all), the
    readiness block is the pre-toggle payload plus exactly one additive
    boolean — note string byte-equal to INDICATOR_NOTE, no note_ur, four
    pillars, score equal to the plain rubric."""
    url = _db(tmp_path / "off.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _seed_healthy_ledger(s, mid)

    report = generate_report(mid, period="last_90_days", db_url=url)
    readiness = report["readiness"]
    # byte-equal note (== on str is byte equality) + exact key delta
    assert readiness["note"] == INDICATOR_NOTE
    assert readiness == {
        "score": readiness["score"],
        "band": readiness["band"],
        "label_ur": readiness["label_ur"],
        "note": INDICATOR_NOTE,
        "two_way_required": False,
    }
    assert "note_ur" not in readiness
    assert set(report["pillars"]) == {"consistency", "confidence", "cashflow", "cleanliness"}
    assert report["trust"]["corroboration_pct"] == 0.0
    assert readiness["score"] == score(_agg_from_db(url, mid)).score


def test_report_flag_on_lowers_score_and_appends_one_clause(tmp_path):
    """Same ledger, same DB: flag 0 → today's report; flag 1 → readiness.note
    appends ONE short clause (Urdu alongside), corroboration pillar appears,
    the score drops. Nothing else in the payload exposes the flag."""
    url = _db(tmp_path / "on.db", with_settings=True)
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _seed_healthy_ledger(s, mid)

    off = generate_report(mid, period="last_90_days", db_url=url)["readiness"]
    with create_engine(url).begin() as conn:
        conn.execute(
            text("INSERT INTO merchant_settings VALUES (:m, 1)"), {"m": mid.hex}
        )
    payload = generate_report(mid, period="last_90_days", db_url=url)
    on = payload["readiness"]

    assert on["two_way_required"] is True
    assert on["note"] == INDICATOR_NOTE + TWO_WAY_NOTE_CLAUSE  # exactly one clause
    assert on["note_ur"] == INDICATOR_NOTE_UR + TWO_WAY_NOTE_CLAUSE_UR
    assert "corroboration" in payload["pillars"]
    assert on["score"] < off["score"], "unconfirmed revenue must lower the score"
    assert on["band"] in ("ready", "nearly", "not_yet"), "band gates unchanged"

    # the ONLY flag exposure in the whole payload
    def _flag_hits(obj, path=""):
        hits = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "two_way_required":
                    hits.append(path + k)
                hits.extend(_flag_hits(v, path + k + "."))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                hits.extend(_flag_hits(v, path + f"{i}."))
        return hits

    assert _flag_hits(payload) == ["readiness.two_way_required"]

    # flipping back off restores the pre-toggle report byte-for-byte (readiness)
    with create_engine(url).begin() as conn:
        conn.execute(
            text("UPDATE merchant_settings SET two_way_confirmation_required = 0")
        )
    again = generate_report(mid, period="last_90_days", db_url=url)["readiness"]
    assert again == off


def test_report_settings_row_absent_means_off(tmp_path):
    """Settings table exists but the merchant has no row (never saved) → OFF."""
    url = _db(tmp_path / "norow.db", with_settings=True)
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _seed_healthy_ledger(s, mid)
    report = generate_report(mid, period="last_90_days", db_url=url)
    assert report["readiness"]["two_way_required"] is False
    assert report["readiness"]["note"] == INDICATOR_NOTE


def test_report_flag_survives_a_broken_settings_table(tmp_path):
    """A merchant_settings table without the flag column (pre-migration DB)
    degrades to OFF — report generation must never fail on the read."""
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    Base.metadata.create_all(create_engine(url))
    with create_engine(url).begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE merchant_settings ("
                "merchant_id TEXT PRIMARY KEY, language TEXT)"  # no flag column
            )
        )
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        _seed_healthy_ledger(s, mid)
    report = generate_report(mid, period="last_90_days", db_url=url)
    assert report["readiness"]["two_way_required"] is False
    assert report["readiness"]["note"] == INDICATOR_NOTE
