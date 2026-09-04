"""Day-3 feature block (schema.md §7, ruling D3-1) — one suite, three features.

1. WhatsApp one-tap confirm/correct buttons (§7.1): outbound interactive
   buttons on pending confirmations (Graph API wire shape live; labels logged
   in the outbound log in mock mode), inbound button.payload / button.text
   handling, text-reply fallback intact.
2. Readiness history endpoint (§7.2): shape + oldest→newest ordering + 'me'.
3. Savings streak (§7.3): Mon–Sun PKT weeks, net>0, zero-entry breaks,
   best-streak, rejected exclusion, PKT boundary, nudge streak sentence.

Everything runs offline (MOCK_MODE=always) against the throwaway SQLite DB
pinned in conftest.py — never main's bizro.db.
"""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.app.db import (
    CreditReport,
    Merchant,
    OutboundMessage,
    Transaction,
    db_session,
)
from server.app.main import app

# Anchor (verified): 2026-08-17 is a Monday, 2026-08-21 a Friday —
# `now` below sits inside the Mon 17–Sun 23 PKT week.
NOW = datetime.fromisoformat("2026-08-21T12:00:00+05:00")


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """Tables must exist even when tests are picked individually (the client
    fixture's lifespan is what usually runs init_db)."""
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


# ----------------------------------------------------------------- helpers


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _audio_payload(wa_id: str, wamid: str | None = None):
    audio = b"\x01" + b"v " * 40
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Day 3"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": wamid or f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180",
                        "type": "audio",
                        "audio": {"id": "m1", "mime_type": "audio/ogg"},
                    }],
                },
                "field": "messages",
            }],
        }],
        "bizro_sim": {
            "media_b64": base64.b64encode(audio).decode(),
            "mime_type": "audio/ogg",
        },
    }


def _button_payload(wa_id: str, payload: str | None = None, text: str | None = None):
    button: dict = {}
    if payload is not None:
        button["payload"] = payload
    if text is not None:
        button["text"] = text
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Day 3"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180",
                        "type": "button",
                        "button": button,
                    }],
                },
                "field": "messages",
            }],
        }],
    }


def _seed_pending_tx(client: TestClient, wa: str) -> str:
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True and out["status"] == "pending", out
    return out["transaction_id"]


def _new_merchant(wa: str) -> uuid.UUID:
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Day3 Ctx")
        s.add(m)
        s.commit()
        return m.id


def _seed_tx(merchant_id, kind: str, amount: float, occurred_at: str, status: str = "confirmed"):
    from server.app import dispatch as disp

    with db_session() as s:
        disp.persist_transaction(
            s,
            s.get(Merchant, merchant_id),
            {
                "kind": kind,
                "amount_pkr": float(amount),
                "occurred_at": occurred_at,
                "source": {"type": "manual", "media_id": None, "model": None,
                           "confidence": 0.95, "raw_output": {}},
                "status": status,
            },
            None,
        )


# ============================== §7.1 buttons ==============================
# Outbound ---------------------------------------------------------------


def test_pending_confirmation_outbound_row_carries_buttons(client):
    """Mock mode still logs the button labels: the confirmation_text row gets
    the two reply buttons in its payload (§7.1)."""
    from server.app import dispatch as disp

    wa = _wa("92400")
    tx_id = _seed_pending_tx(client, wa)
    with db_session() as s:
        row = (
            s.query(OutboundMessage)
            .filter_by(transaction_id=uuid.UUID(tx_id), kind="confirmation_text")
            .order_by(OutboundMessage.created_at)
            .first()
        )
        assert row is not None and row.payload, "confirmation row must carry a buttons payload"
        buttons = row.payload["buttons"]
        assert [b["reply"]["id"] for b in buttons] == ["confirm", "correct"]
        assert [b["reply"]["title"] for b in buttons] == [
            disp.BUTTON_CONFIRM_TITLE_UR, disp.BUTTON_CORRECT_TITLE_UR,
        ]
        assert all(b["type"] == "reply" for b in buttons)


def test_mock_send_result_logs_button_labels(client):
    """Mock delivery is observable: the webhook outcome's `sent` payload
    includes the button labels it would have attached live."""
    wa = _wa("92401")
    out = client.post("/webhook/whatsapp", json=_audio_payload(wa)).json()["results"][0]
    assert out["sent"]["mock"] is True
    assert [b["reply"]["id"] for b in out["sent"]["buttons"]] == ["confirm", "correct"]
    assert "Edit" in str(out["sent"]["buttons"])


def test_non_pending_confirmation_has_no_buttons(client, monkeypatch):
    """Buttons attach ONLY to pending confirmations (§7.1) — a high-confidence
    pipeline result persisted as confirmed goes out as plain text."""
    from server.app import dispatch as disp

    def confident_pipeline(path, merchant, occurred_at):
        return {
            "kind": "sale",
            "amount_pkr": 1200.0,
            "counterparty": {"name": "Walk-in", "phone": None},
            "occurred_at": occurred_at,
            "source": {"type": "voice", "media_id": None, "model": None,
                       "confidence": 0.96, "raw_output": {"mock": True}},
            "flag": "none",
            "status": "confirmed",
            "confirmation_ur": "Cash sale: 1200 rupees recorded.",
        }

    monkeypatch.setitem(disp._pipeline_cache, "voice_agent.pipeline.process_voice_note",
                        confident_pipeline)
    wa = _wa("92402")
    out = client.post("/webhook/whatsapp", json=_audio_payload(wa)).json()["results"][0]
    assert out["status"] == "confirmed"
    assert "buttons" not in out["sent"], "confirmed confirmations carry no buttons"
    with db_session() as s:
        rows = (s.query(OutboundMessage)
                .filter_by(transaction_id=uuid.UUID(out["transaction_id"]))
                .all())
        assert rows and all(r.payload is None for r in rows)


def test_live_send_with_buttons_posts_interactive_payload(monkeypatch):
    """Live mode (WHATSAPP_TOKEN set): the confirmation goes out as a Graph API
    interactive.type=button message with the two reply buttons."""
    from server.app.config import Settings
    from server.app import dispatch as disp
    from server.app import whatsapp_client as wc

    live = Settings(whatsapp_token="test-token", whatsapp_phone_number_id="PNID1",
                    mock_mode="auto")
    monkeypatch.setattr(wc, "get_settings", lambda: live)

    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"messages": [{"id": "wamid.OUT"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"], captured["json"] = url, json
        return FakeResp()

    monkeypatch.setattr(wc.httpx, "post", fake_post)

    wc.send_text("923001112233", "Got it. 5000 rupees credit to Ahmad. Is this correct?",
                 buttons=disp.CONFIRM_BUTTONS)
    body = captured["json"]
    assert "PNID1" in captured["url"]
    assert body["type"] == "interactive"
    assert body["interactive"]["type"] == "button"
    assert body["interactive"]["body"]["text"] == (
        "Got it. 5000 rupees credit to Ahmad. Is this correct?"
    )
    sent_buttons = body["interactive"]["action"]["buttons"]
    assert [b["reply"]["id"] for b in sent_buttons] == ["confirm", "correct"]
    assert sent_buttons[0]["type"] == "reply"

    # and without buttons: still the plain text message
    wc.send_text("923001112233", "plain message")
    assert captured["json"]["type"] == "text"


# Inbound ----------------------------------------------------------------


def test_button_confirm_payload_confirms_most_recent_pending(client):
    wa = _wa("92403")
    tx_id = _seed_pending_tx(client, wa)

    r = client.post("/webhook/whatsapp", json=_button_payload(wa, payload="confirm"))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True and out["type"] == "button"
    assert out["action"] == "confirm"
    # wire-row response logging, same row shape as POST /confirm
    assert out["transaction"]["id"] == tx_id
    assert out["transaction"]["status"] == "confirmed"
    assert out["transaction"]["confirmation_ur"]  # W-1 consistency

    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(tx_id))
        assert tx.status == "confirmed"
        ack = (s.query(OutboundMessage)
               .filter_by(transaction_id=tx.id, kind="confirmation_text")
               .order_by(OutboundMessage.created_at.desc()).first())
        assert ack.body == out["reply"]


def test_button_correct_keeps_pending_and_asks_for_voice_note(client):
    wa = _wa("92404")
    tx_id = _seed_pending_tx(client, wa)

    r = client.post("/webhook/whatsapp", json=_button_payload(wa, payload="correct"))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["action"] == "correct"
    assert out["transaction"]["id"] == tx_id
    assert out["transaction"]["status"] == "pending", "correct → stays pending (§7.1)"

    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(tx_id))
        assert tx.status == "pending"
    # English reply requests the corrected voice note (owner ruling: EN output)
    assert "voice note" in out["reply"]


def test_button_text_fallback_confirm(client):
    """Older Graph API versions carry only button.text — no payload."""
    wa = _wa("92405")
    tx_id = _seed_pending_tx(client, wa)
    r = client.post("/webhook/whatsapp",
                    json=_button_payload(wa, text="Correct"))
    out = r.json()["results"][0]
    assert out["action"] == "confirm"
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "confirmed"


def test_button_text_fallback_correct(client):
    wa = _wa("92406")
    tx_id = _seed_pending_tx(client, wa)
    r = client.post("/webhook/whatsapp", json=_button_payload(wa, text="Edit"))
    out = r.json()["results"][0]
    assert out["action"] == "correct"
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "pending"


def test_button_acts_on_most_recent_pending_only(client):
    wa = _wa("92407")
    older = _seed_pending_tx(client, wa)
    newer = _seed_pending_tx(client, wa)
    r = client.post("/webhook/whatsapp", json=_button_payload(wa, payload="confirm"))
    out = r.json()["results"][0]
    assert out["transaction"]["id"] == newer
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(newer)).status == "confirmed"
        assert s.get(Transaction, uuid.UUID(older)).status == "pending"


def test_button_with_no_pending_tx_gets_polite_reply(client):
    wa = _wa("92408")  # no transaction ever seeded
    r = client.post("/webhook/whatsapp", json=_button_payload(wa, payload="confirm"))
    out = r.json()["results"][0]
    assert out["ok"] is True
    assert out["transaction"] is None
    assert "pending" in out["reply"]


def test_button_unknown_payload_gets_help_reply(client):
    wa = _wa("92409")
    tx_id = _seed_pending_tx(client, wa)
    r = client.post("/webhook/whatsapp", json=_button_payload(wa, payload="???"))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["action"] == "unknown"
    assert out["transaction"] is None
    assert out["reply"]  # help text — never silence (§6.9 spirit)
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "pending"


def test_text_reply_confirm_path_still_works(client):
    """Buttons are an upgrade, not a replacement — '1' still confirms."""
    wa = _wa("92410")
    tx_id = _seed_pending_tx(client, wa)
    r = client.post("/webhook/whatsapp", json={
        "entry": [{"changes": [{"value": {"messages": [{
            "from": wa, "id": f"wamid.{uuid.uuid4().hex}", "timestamp": "1755798180",
            "type": "text", "text": {"body": "1"},
        }]}, "field": "messages"}]}],
    })
    out = r.json()["results"][0]
    assert out["ok"] is True and out["type"] == "text"
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "confirmed"


# ============================ §7.2 report history ============================


def _seed_report(merchant_id, created_at: datetime, score: int, band: str):
    with db_session() as s:
        s.add(CreditReport(
            merchant_id=merchant_id,
            period_start=created_at.date() - timedelta(days=30),
            period_end=created_at.date(),
            model="qwen3.7-plus",
            report_json={"readiness": {"score": score, "band": band, "label_ur": "…"},
                         "generated_at": created_at.isoformat()},
            created_at=created_at,
        ))
        s.commit()


def test_report_history_shape_and_ordering(client):
    mid = _new_merchant(_wa("92411"))
    t1 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    _seed_report(mid, t1, 40, "not_yet")
    _seed_report(mid, t1 + timedelta(days=7), 62, "nearly")
    _seed_report(mid, t1 + timedelta(days=14), 78, "ready")

    r = client.get(f"/api/merchants/{mid}/report/history")
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body) == ["history"]
    hist = body["history"]
    assert len(hist) == 3
    for item in hist:
        assert set(item) == {"generated_at", "score", "band"}
        assert isinstance(item["score"], int) and isinstance(item["band"], str)
        datetime.fromisoformat(item["generated_at"])  # ISO-8601
    # oldest → newest
    assert [h["score"] for h in hist] == [40, 62, 78]
    assert [h["band"] for h in hist] == ["not_yet", "nearly", "ready"]
    assert hist[0]["generated_at"] <= hist[1]["generated_at"] <= hist[2]["generated_at"]


def test_report_history_empty_for_new_merchant(client):
    mid = _new_merchant(_wa("92412"))
    r = client.get(f"/api/merchants/{mid}/report/history")
    assert r.status_code == 200
    assert r.json() == {"history": []}


def test_report_history_me_sentinel_matches_first_merchant(client):
    """'me' resolves exactly like the other merchant routes (ruling D1-2)."""
    with db_session() as s:
        first = s.query(Merchant).order_by(Merchant.created_at).first()
    assert first is not None, "merchants exist from the rest of the suite"
    r_me = client.get("/api/merchants/me/report/history")
    r_id = client.get(f"/api/merchants/{first.id}/report/history")
    assert r_me.status_code == 200
    assert r_me.json() == r_id.json()


def test_report_history_tolerates_fallback_band_shape(client):
    """Server-fallback reports store readiness as a bare band string."""
    mid = _new_merchant(_wa("92413"))
    with db_session() as s:
        s.add(CreditReport(
            merchant_id=mid,
            period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
            model="server_fallback",
            report_json={"readiness": "insufficient_data"},
            created_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
        ))
        s.commit()
    hist = client.get(f"/api/merchants/{mid}/report/history").json()["history"]
    assert hist == [{"generated_at": hist[0]["generated_at"], "score": 0,
                     "band": "insufficient_data"}]


# ============================== §7.3 streak ==============================


def _streak(mid, now=NOW):
    from server.app.nudges import compute_streak

    with db_session() as s:
        return compute_streak(s, mid, now=now)


def test_streak_counts_consecutive_positive_weeks_backwards():
    mid = _new_merchant(_wa("92414"))
    _seed_tx(mid, "sale", 5000, "2026-08-19T15:00:00+00:00")          # current week
    _seed_tx(mid, "sale", 3000, "2026-08-11T10:00:00+00:00")          # prev week
    _seed_tx(mid, "expense", 1000, "2026-08-12T10:00:00+00:00")       #   net +2000
    _seed_tx(mid, "udhar_settlement", 800, "2026-08-05T10:00:00+00:00")  # two ago
    # three weeks ago: no entries → breaks the streak
    out = _streak(mid)
    assert out == {"streak_weeks": 3, "best_streak_weeks": 3,
                   "current_week_positive": True}


def test_streak_net_is_cash_in_minus_cash_out():
    """udhar_given is cash OUT; sale + settlement are cash IN (§1 directions)."""
    mid = _new_merchant(_wa("92415"))
    _seed_tx(mid, "sale", 2000, "2026-08-18T10:00:00+00:00")
    _seed_tx(mid, "udhar_given", 2500, "2026-08-18T11:00:00+00:00")  # net -500
    out = _streak(mid)
    assert out["streak_weeks"] == 0 and out["current_week_positive"] is False


def test_streak_breaks_on_net_negative_week():
    mid = _new_merchant(_wa("92416"))
    _seed_tx(mid, "sale", 4000, "2026-08-19T10:00:00+00:00")           # current +
    _seed_tx(mid, "expense", 9000, "2026-08-11T10:00:00+00:00")        # prev net -
    _seed_tx(mid, "sale", 1000, "2026-08-04T10:00:00+00:00")           # two ago +
    out = _streak(mid)
    assert out["streak_weeks"] == 1
    assert out["best_streak_weeks"] == 1  # the gap-free run is the current week only


def test_streak_zero_entry_current_week_breaks_but_best_remembers():
    mid = _new_merchant(_wa("92417"))
    _seed_tx(mid, "sale", 1000, "2026-08-11T10:00:00+00:00")   # prev week +
    _seed_tx(mid, "sale", 1000, "2026-08-04T10:00:00+00:00")   # two ago +
    _seed_tx(mid, "sale", 1000, "2026-07-28T10:00:00+00:00")   # three ago +
    out = _streak(mid)
    assert out["streak_weeks"] == 0, "current week has zero entries → streak broken"
    assert out["current_week_positive"] is False
    assert out["best_streak_weeks"] == 3


def test_streak_best_skips_zero_entry_gap():
    mid = _new_merchant(_wa("92418"))
    _seed_tx(mid, "sale", 1000, "2026-08-19T10:00:00+00:00")   # current +
    _seed_tx(mid, "sale", 1000, "2026-08-12T10:00:00+00:00")   # prev +
    # two weeks ago: nothing → breaks any run crossing it
    _seed_tx(mid, "sale", 1000, "2026-07-29T10:00:00+00:00")   # three ago +
    out = _streak(mid)
    assert out["streak_weeks"] == 2
    assert out["best_streak_weeks"] == 2


def test_streak_pkt_week_boundary():
    """Weeks are Mon–Sun in PKT: 19:30 UTC Sunday is already Monday in PKT."""
    mid = _new_merchant(_wa("92419"))
    # 2026-08-16T19:30Z == 2026-08-17T00:30 PKT (Monday) → CURRENT week
    _seed_tx(mid, "sale", 700, "2026-08-16T19:30:00+00:00")
    out = _streak(mid)
    assert out == {"streak_weeks": 1, "best_streak_weeks": 1,
                   "current_week_positive": True}

    mid2 = _new_merchant(_wa("92420"))
    # 18:59Z is still Sunday 23:59 PKT → PREVIOUS week; current week stays empty
    _seed_tx(mid2, "sale", 700, "2026-08-16T18:59:00+00:00")
    out2 = _streak(mid2)
    assert out2["streak_weeks"] == 0 and out2["current_week_positive"] is False
    assert out2["best_streak_weeks"] == 1


def test_streak_ignores_rejected_entries():
    mid = _new_merchant(_wa("92421"))
    _seed_tx(mid, "sale", 1000, "2026-08-19T10:00:00+00:00")
    _seed_tx(mid, "expense", 5000, "2026-08-19T11:00:00+00:00", status="rejected")
    out = _streak(mid)
    assert out["streak_weeks"] == 1 and out["current_week_positive"] is True


def test_streak_endpoint_shape_and_wiring(client):
    mid = _new_merchant(_wa("92423"))
    _seed_tx(mid, "sale", 900,
             datetime.now(timezone.utc).isoformat())  # lands in the current week
    r = client.get(f"/api/merchants/{mid}/streak")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"streak_weeks", "best_streak_weeks", "current_week_positive"}
    assert isinstance(body["streak_weeks"], int)
    assert body["streak_weeks"] >= 1 and body["current_week_positive"] is True


def test_streak_endpoint_me_sentinel_and_unknown_ids(client):
    r = client.get("/api/merchants/me/streak")
    assert r.status_code == 200
    assert client.get("/api/merchants/not-a-uuid/streak").status_code == 400
    assert client.get(f"/api/merchants/{uuid.uuid4()}/streak").status_code == 404


# ------------------------------- nudge wiring ------------------------------


def test_nudge_includes_streak_sentence_when_positive():
    from server.app.nudges import compute_weekly_nudge

    mid = _new_merchant(_wa("92424"))
    _seed_tx(mid, "sale", 5000, "2026-08-19T15:00:00+00:00")   # current week +
    _seed_tx(mid, "sale", 3000, "2026-08-11T10:00:00+00:00")   # prev week +
    with db_session() as s:
        nudge = compute_weekly_nudge(s, mid, now=NOW)
    assert nudge["stats"]["streak_weeks"] == 2
    assert "in a row" in nudge["text_ur"]
    assert "2" in nudge["text_ur"]


def test_nudge_omits_streak_sentence_when_zero():
    from server.app.nudges import compute_weekly_nudge

    mid = _new_merchant(_wa("92425"))
    with db_session() as s:
        nudge = compute_weekly_nudge(s, mid, now=NOW)
    assert nudge["stats"]["streak_weeks"] == 0
    assert "in a row" not in nudge["text_ur"]
