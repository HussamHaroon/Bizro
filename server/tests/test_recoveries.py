"""Recovery-ladder tests (bizro-testability: offline, deterministic).

Pins the phase-1 ladder design (server/app/recoveries.py docstring):
- tier boundaries at exactly 15 / 30 / 45 days (and the 0-14 "none" band),
- FIFO settlement aging (oldest surviving entry sets the tier),
- no message without an explicit outstanding balance > 0,
- rejected entries never count,
- per-tier message copy,
- escalation notifies the shopkeeper + every customer message CC'd as fine
  print (all mock-safe: deliver() is monkeypatched, nothing hits a network),
- no-phone customers listed, not messaged,
- same-day rerun produces zero new sends; next day it speaks again.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from server.app.db import (
    Customer,
    Merchant,
    OutboundMessage,
    Transaction,
    db_session,
)

# Fixed anchor: every seeded entry's occurred_at is NOW - timedelta(days=n),
# so (NOW - occurred_at).days == n exactly — the tier boundaries are exact.
NOW = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
SHOP_NAME = "Al-Madina Kiryana Store"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """Tables must exist even when tests are picked individually (the client
    fixture's lifespan is what usually runs init_db)."""
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(autouse=True)
def deliver_calls(monkeypatch):
    """Mock-safe by construction: recoveries.deliver is a recorder in EVERY
    test of this module (no network, no real WhatsApp, ever)."""
    calls: list[dict] = []

    def _fake_deliver(wa_id, body, buttons=None):
        calls.append({"to": wa_id, "body": body})
        return {"delivered": True, "mock": True, "to": wa_id, "body": body}

    monkeypatch.setattr("server.app.recoveries.deliver", _fake_deliver)
    return calls


# ----------------------------------------------------------------- helpers


def _mk_merchant(name: str = SHOP_NAME) -> tuple[uuid.UUID, str]:
    with db_session() as s:
        m = Merchant(wa_id=f"92300{uuid.uuid4().hex[:10]}", display_name=name)
        s.add(m)
        s.commit()
        return m.id, m.wa_id


def _mk_customer(mid: uuid.UUID, name: str, phone: str | None = None) -> uuid.UUID:
    with db_session() as s:
        c = Customer(merchant_id=mid, name=name, phone=phone)
        s.add(c)
        s.commit()
        return c.id


def _tx(
    mid: uuid.UUID,
    cust_id: uuid.UUID | None,
    kind: str,
    amount: float,
    days_ago: int,
    status: str = "confirmed",
) -> uuid.UUID:
    with db_session() as s:
        t = Transaction(
            merchant_id=mid,
            customer_id=cust_id,
            kind=kind,
            amount_pkr=float(amount),
            currency="PKR",
            description="recovery test entry",
            occurred_at=NOW - timedelta(days=days_ago),
            source_type="manual",
            flag="none",
            status=status,
            created_at=NOW - timedelta(days=days_ago),
        )
        s.add(t)
        s.commit()
        return t.id


# ============================ ladder boundaries ===========================


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (14, None),  # 0-14: the weekly nudge covers it — no recovery message
        (15, "gentle"),
        (29, "gentle"),
        (30, "firm"),
        (44, "firm"),
        (45, "escalation"),
    ],
)
def test_tier_boundaries_at_exact_days(days, expected):
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    cid = _mk_customer(mid, f"Cust{days}", phone="92300111223")
    _tx(mid, cid, "udhar_given", 3000, days_ago=days)
    with db_session() as s:
        actions = compute_recovery_actions(s, mid, now=NOW)
    if expected is None:
        assert actions == []
        return
    assert len(actions) == 1
    a = actions[0]
    assert a["tier"] == expected
    assert a["oldest_days"] == days
    assert a["amount"] == 3000
    assert a["customer"] == f"Cust{days}"
    assert a["customer_id"] == str(cid)
    assert a["phone"] == "92300111223"
    assert a["message"]


def test_action_shape_matches_the_design_contract():
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    cid = _mk_customer(mid, "Shape", phone="92300444555")
    tx_id = _tx(mid, cid, "udhar_given", 1200, days_ago=20)
    with db_session() as s:
        actions = compute_recovery_actions(s, mid, now=NOW)
    assert set(actions[0]) >= {
        "customer", "customer_id", "phone", "amount", "oldest_days", "tier", "message",
    }
    assert actions[0]["oldest_tx_id"] == str(tx_id)


def test_fifo_settlement_ages_from_oldest_surviving_entry():
    """FIFO: a 5000 settlement pays down the OLDEST entry first — the 40-day
    entry survives with 1000, so the tier keys on 40 days (firm), not the
    10-day top-up."""
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    cid = _mk_customer(mid, "Fifo", phone="92300555666")
    _tx(mid, cid, "udhar_given", 6000, days_ago=40)
    _tx(mid, cid, "udhar_given", 4000, days_ago=10)
    _tx(mid, cid, "udhar_settlement", 5000, days_ago=3)
    with db_session() as s:
        actions = compute_recovery_actions(s, mid, now=NOW)
    assert len(actions) == 1
    a = actions[0]
    assert a["amount"] == 5000  # 6000 + 4000 - 5000
    assert a["oldest_days"] == 40
    assert a["tier"] == "firm"


# ============================== skip rules ===============================


def test_no_message_without_explicit_outstanding_balance():
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    full = _mk_customer(mid, "SettledFull", phone="92300666777")
    _tx(mid, full, "udhar_given", 5000, days_ago=50)
    _tx(mid, full, "udhar_settlement", 5000, days_ago=2)
    over = _mk_customer(mid, "Overpaid", phone="92300777889")
    _tx(mid, over, "udhar_given", 2000, days_ago=50)
    _tx(mid, over, "udhar_settlement", 2500, days_ago=2)
    with db_session() as s:
        assert compute_recovery_actions(s, mid, now=NOW) == []


def test_rejected_entries_never_count():
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    cid = _mk_customer(mid, "RejectedOnly", phone="92300888990")
    _tx(mid, cid, "udhar_given", 8000, days_ago=60, status="rejected")
    with db_session() as s:
        assert compute_recovery_actions(s, mid, now=NOW) == []


def test_unlinked_udhaar_is_never_messaged():
    """customer_id NULL — there is nobody to address, so no action."""
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    _tx(mid, None, "udhar_given", 9000, days_ago=60)
    with db_session() as s:
        assert compute_recovery_actions(s, mid, now=NOW) == []


# ============================== message copy =============================


def test_message_wording_per_tier():
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    gentle = _mk_customer(mid, "Gentle", phone="92300101001")
    _tx(mid, gentle, "udhar_given", 1500, days_ago=20)
    firm = _mk_customer(mid, "Firm", phone="92300101002")
    _tx(mid, firm, "udhar_given", 2500, days_ago=35)
    esc = _mk_customer(mid, "Escalate", phone="92300101003")
    _tx(mid, esc, "udhar_given", 3500, days_ago=50)
    with db_session() as s:
        actions = {a["customer"]: a for a in compute_recovery_actions(s, mid, now=NOW)}

    g = actions["Gentle"]["message"]
    assert g.startswith("Assalam-o-alaikum! A gentle reminder:")
    assert "PKR 1,500" in g and SHOP_NAME in g
    assert "since 18 Aug 2026" in g  # oldest entry's PKT date
    assert g.endswith("reply here if you need a day.")

    f = actions["Firm"]["message"]
    assert f == (
        f"Your balance of PKR 2,500 at {SHOP_NAME} is now 30+ days old. "
        "Please arrange payment this week."
    )

    e = actions["Escalate"]["message"]
    assert e == (
        "Your PKR 3,500 balance is 45+ days overdue. "
        "Our team may visit to settle the account in person."
    )


def test_actions_sorted_worst_debtor_first():
    from server.app.recoveries import compute_recovery_actions

    mid, _ = _mk_merchant()
    a = _mk_customer(mid, "Young", phone="92300101011")
    _tx(mid, a, "udhar_given", 1000, days_ago=16)
    b = _mk_customer(mid, "Old", phone="92300101012")
    _tx(mid, b, "udhar_given", 2000, days_ago=50)
    with db_session() as s:
        actions = compute_recovery_actions(s, mid, now=NOW)
    assert [x["customer"] for x in actions] == ["Old", "Young"]


# ============================ send behaviour =============================


def test_escalation_notifies_shopkeeper_and_ccs_the_message(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    mid, wa = _mk_merchant()
    cid = _mk_customer(mid, "Rahmat", phone="92300445566")
    _tx(mid, cid, "udhar_given", 7000, days_ago=50)
    with db_session() as s:
        results = send_recovery_messages(s, merchant_id=mid, now=NOW)

    assert len(results) == 1
    r = results[0]
    assert r["no_phone"] == [] and r["skipped_today"] == []
    kinds = [m["kind"] for m in r["sent"]]
    assert kinds == [
        "recovery_escalation",
        "recovery_escalation_cc",
        "recovery_escalation_shopkeeper",
    ]

    cust_msg, cc, notice = r["sent"]
    assert cust_msg["to"] == "92300445566"
    assert "45+ days overdue" in cust_msg["body"]
    assert cc["to"] == wa  # fine print lands in the shopkeeper's thread
    assert "[Copy sent to Rahmat]:" in cc["body"]
    assert "45+ days overdue" in cc["body"]
    assert notice["to"] == wa
    assert notice["body"] == (
        "Rahmat's balance is 45+ days overdue — we suggest a personal visit."
    )
    assert [c["to"] for c in deliver_calls] == ["92300445566", wa, wa]

    # audit rows: kind="recovery_<tier>" + payload carries the customer_id
    with db_session() as s:
        rows = s.query(OutboundMessage).filter(OutboundMessage.merchant_id == mid).all()
        by_kind = {row.kind: row for row in rows}
        assert set(by_kind) == {
            "recovery_escalation",
            "recovery_escalation_cc",
            "recovery_escalation_shopkeeper",
        }
        assert by_kind["recovery_escalation"].payload["customer_id"] == str(cid)
        assert by_kind["recovery_escalation"].body == cust_msg["body"]


def test_gentle_and_firm_send_customer_message_plus_cc_only(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    mid, wa = _mk_merchant()
    g = _mk_customer(mid, "Gentle", phone="92300101021")
    _tx(mid, g, "udhar_given", 1500, days_ago=20)
    f = _mk_customer(mid, "Firm", phone="92300101022")
    _tx(mid, f, "udhar_given", 2500, days_ago=35)
    with db_session() as s:
        results = send_recovery_messages(s, merchant_id=mid, now=NOW)

    kinds = sorted(m["kind"] for m in results[0]["sent"])
    assert kinds == [
        "recovery_firm",
        "recovery_firm_cc",
        "recovery_gentle",
        "recovery_gentle_cc",
    ]
    # no shopkeeper escalation notice below 45 days
    assert all("shopkeeper" not in k for k in kinds)
    assert {c["to"] for c in deliver_calls} == {wa, "92300101021", "92300101022"}


def test_no_phone_customer_listed_not_messaged(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    mid, wa = _mk_merchant()
    cid = _mk_customer(mid, "NoPhone")  # phone=None
    _tx(mid, cid, "udhar_given", 6000, days_ago=60)
    with db_session() as s:
        results = send_recovery_messages(s, merchant_id=mid, now=NOW)

    r = results[0]
    assert r["no_phone"] == [
        {"customer": "NoPhone", "tier": "escalation", "amount": 6000, "oldest_days": 60}
    ]
    # no customer message, no CC — but the shopkeeper STILL gets the notice
    kinds = [m["kind"] for m in r["sent"]]
    assert kinds == ["recovery_escalation_shopkeeper"]
    assert all(c["to"] == wa for c in deliver_calls)
    assert r["sent"][0]["body"] == (
        "NoPhone's balance is 45+ days overdue — we suggest a personal visit. "
        "(no phone on file)"
    )


def test_no_balance_customer_produces_no_send_at_all(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    mid, wa = _mk_merchant()
    cid = _mk_customer(mid, "Settled", phone="92300999001")
    _tx(mid, cid, "udhar_given", 5000, days_ago=50)
    _tx(mid, cid, "udhar_settlement", 5000, days_ago=2)
    with db_session() as s:
        results = send_recovery_messages(s, merchant_id=mid, now=NOW)
    assert results[0]["sent"] == [] and results[0]["no_phone"] == []
    assert deliver_calls == []
    with db_session() as s:
        assert (
            s.query(OutboundMessage).filter(OutboundMessage.merchant_id == mid).count() == 0
        )


def test_same_day_rerun_produces_zero_new_sends(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    mid, _ = _mk_merchant()
    cid = _mk_customer(mid, "Idem", phone="92300777880")
    _tx(mid, cid, "udhar_given", 4000, days_ago=20)
    with db_session() as s:
        first = send_recovery_messages(s, merchant_id=mid, now=NOW)
    assert [m["kind"] for m in first[0]["sent"]] == [
        "recovery_gentle",
        "recovery_gentle_cc",
    ]
    calls_after_first = len(deliver_calls)

    with db_session() as s:
        second = send_recovery_messages(s, merchant_id=mid, now=NOW)
    assert second[0]["sent"] == []
    assert second[0]["skipped_today"] == [{"customer": "Idem", "tier": "gentle"}]
    assert len(deliver_calls) == calls_after_first  # nothing went out again

    # the next PKT day the ladder speaks again (per-DAY idempotency, not once-ever)
    with db_session() as s:
        third = send_recovery_messages(s, merchant_id=mid, now=NOW + timedelta(days=1))
    assert [m["kind"] for m in third[0]["sent"]] == [
        "recovery_gentle",
        "recovery_gentle_cc",
    ]


def test_send_to_all_merchants_when_merchant_id_is_none(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    m1, _ = _mk_merchant("Shop One")
    c1 = _mk_customer(m1, "A-one", phone="92300111111")
    _tx(m1, c1, "udhar_given", 1000, days_ago=20)
    m2, _ = _mk_merchant("Shop Two")
    c2 = _mk_customer(m2, "B-two", phone="92300222222")
    _tx(m2, c2, "udhar_given", 2000, days_ago=40)

    with db_session() as s:
        results = send_recovery_messages(s, merchant_id=None, now=NOW)
    mine = {r["merchant_id"]: r for r in results if r["merchant_id"] in {str(m1), str(m2)}}
    assert set(mine) == {str(m1), str(m2)}
    assert [m["kind"] for m in mine[str(m1)]["sent"]] == [
        "recovery_gentle",
        "recovery_gentle_cc",
    ]
    assert [m["kind"] for m in mine[str(m2)]["sent"]] == [
        "recovery_firm",
        "recovery_firm_cc",
    ]


def test_unknown_merchant_id_is_a_no_op(deliver_calls):
    from server.app.recoveries import send_recovery_messages

    with db_session() as s:
        assert send_recovery_messages(s, merchant_id=uuid.uuid4(), now=NOW) == []
    assert deliver_calls == []
