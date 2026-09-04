"""Report generation tests — the four SKILL.md scenarios + rubric boundaries.

Offline, deterministic, no keys (bizro-testability). Empty history must NEVER
invent numbers; healthy/red-flag/all-pending paths assert metric correctness.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.db_view import Base, Customer, Merchant, Transaction, get_sessionmaker
from credit_agent.report import generate_report
from credit_agent.rubric import BAND_NEARLY, BAND_READY, MIN_ENTRIES
from credit_agent.seed import seed_demo
from credit_agent.render import render_report_html


def _db(db_file):
    url = f"sqlite:///{db_file}"
    from sqlalchemy import create_engine
    Base.metadata.create_all(create_engine(url))
    return url


def _mk_merchant(session, name="Test Store"):
    m = Merchant(id=uuid.uuid4(), wa_id="wa", display_name=name)
    session.add(m)
    session.commit()
    return m.id


def _tx(session, mid, day, kind="sale", amount=1000.0, source="voice", conf=0.9,
        flag="none", status="confirmed", customer=None):
    session.add(Transaction(
        id=uuid.uuid4(), merchant_id=mid, customer_id=customer, kind=kind,
        amount_pkr=amount, description=f"{kind} {day}",
        occurred_at=datetime.now(timezone.utc) - timedelta(days=day),
        source_type=source, source_media_id=uuid.uuid4() if source != "manual" else None,
        source_model="qwen3.5-omni-plus" if source == "voice" else "qwen-vl-ocr",
        confidence=conf if source != "manual" else None,
        flag=flag, status=status,
    ))


def test_empty_history_is_insufficient_and_invents_nothing(tmp_path):
    url = _db(tmp_path / "t.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
    report = generate_report(mid, db_url=url)
    assert report["readiness"]["band"] == "insufficient_data"
    assert report["readiness"]["score"] == 0
    assert report["line_items"] == []
    assert report["metrics"][0]["display"] == "0"
    assert report["mock"] is True  # no key -> narrative templated + marked
    html = render_report_html(report)
    assert "MOCK DATA" in html
    assert "insufficient" in html


def test_healthy_history_scores_and_carries_audit_fields(tmp_path):
    url = _db(tmp_path / "t.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        cust = Customer(id=uuid.uuid4(), merchant_id=mid, name="Ahmad")
        s.add(cust)
        s.commit()
        for day in range(84, 0, -2):  # 42 entries over 12 weeks
            _tx(s, mid, day, kind="sale", amount=2000 + day, conf=0.9 + (day % 7) / 100)
        for day in range(80, 0, -7):
            _tx(s, mid, day, kind="udhar_given", amount=1500, customer=cust.id)
        for day in range(76, 0, -7):
            _tx(s, mid, day, kind="udhar_settlement", amount=700, customer=cust.id)
        s.commit()
    report = generate_report(mid, period="last_90_days", db_url=url)
    assert report["readiness"]["band"] in ("ready", "nearly")
    assert report["readiness"]["score"] >= BAND_NEARLY
    li = report["line_items"][0]
    for field in ("source_type", "source_media_id", "source_model", "confidence"):
        assert field in li, f"audit field missing: {field}"
    assert report["criteria_basis"] == "general-microfinance-pending-mawakhat"
    assert report["narrative_ur"].strip()


def test_red_flag_history_penalized_vs_clean(tmp_path):
    def build(flagged: bool):
        url = _db(tmp_path / f"{'f' if flagged else 'c'}.db")
        Session = get_sessionmaker(url)
        with Session() as s:
            mid = _mk_merchant(s)
            for day in range(84, 0, -2):
                _tx(s, mid, day, kind="sale", amount=2000,
                    flag="price_anomaly" if (flagged and day % 4 == 0) else "none",
                    conf=0.6 if (flagged and day % 4 == 0) else 0.93)
            s.commit()
        return generate_report(mid, period="last_90_days", db_url=url)["readiness"]["score"]
    assert build(False) > build(True)


def test_all_pending_history_reports_pending_share(tmp_path):
    url = _db(tmp_path / "t.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        for day in range(84, 0, -2):
            _tx(s, mid, day, status="pending")
        s.commit()
    report = generate_report(mid, period="last_90_days", db_url=url)
    assert report["metrics"][0]["display"] == "42"
    # consistency pillar note must disclose pending backlog
    assert "pending" in report["pillars"]["consistency"][2]


def test_rubric_boundary_min_entries(tmp_path):
    url = _db(tmp_path / "t.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s)
        for day in range(MIN_ENTRIES - 1):  # one short of the minimum
            _tx(s, mid, day * 3)
        s.commit()
    assert generate_report(mid, db_url=url)["readiness"]["band"] == "insufficient_data"


def test_seed_is_deterministic(tmp_path):
    a, b = seed_demo(f"sqlite:///{tmp_path/'a.db'}"), seed_demo(f"sqlite:///{tmp_path/'b.db'}")
    ra, rb = (generate_report(a, db_url=f"sqlite:///{tmp_path/'a.db'}"),
              generate_report(b, db_url=f"sqlite:///{tmp_path/'b.db'}"))
    assert ra["readiness"]["score"] == rb["readiness"]["score"]
    assert ra["metrics"][0]["display"] == rb["metrics"][0]["display"]
    assert ra["readiness"]["band"] in ("ready", "nearly")


def test_seed_contrast_profile_demos_range_not_ready(tmp_path):
    """Bilal Ki Dukan (contrast) must band BELOW the healthy merchant — the
    loan-officer picker demos range, not two 'ready' rows (D4 block task)."""
    def run(tag):
        url = f"sqlite:///{tmp_path/(tag + '.db')}"
        mid = seed_demo(url, merchant_name="Bilal Ki Dukan", days=60, profile="contrast")
        return generate_report(mid, period="last_90_days", db_url=url)
    ra, rb = run("ba"), run("bb")
    assert ra["readiness"]["score"] == rb["readiness"]["score"]  # deterministic
    assert ra["readiness"]["band"] in ("nearly", "not_yet")      # never "ready"
    assert 14 <= int(ra["metrics"][0]["display"]) <= 30          # sparse but scorable
    anomalies = sum(f["count"] for f in ra["red_flags"] if f["flag"] == "price_anomaly")
    assert 2 <= anomalies <= 3
    assert "0 pending" not in ra["pillars"]["consistency"][2]    # pending backlog real
    assert abs(ra["metrics"][2]["value"]) < 5000                 # net cash-flow ~ zero
    healthy = generate_report(
        seed_demo(f"sqlite:///{tmp_path/'h.db'}"), period="last_90_days",
        db_url=f"sqlite:///{tmp_path/'h.db'}")
    assert healthy["readiness"]["score"] > ra["readiness"]["score"]


def test_rendered_html_escapes_hostile_strings(tmp_path):
    url = _db(tmp_path / "t.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _mk_merchant(s, "<script>alert(1)</script>")
        s.commit()
    report = generate_report(mid, db_url=url)
    out = render_report_html(report)
    assert "<script>alert" not in out  # escaped, not executed
    assert "&lt;script&gt;" in out
