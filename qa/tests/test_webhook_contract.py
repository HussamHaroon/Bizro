"""Webhook + REST contract checks against the REAL FastAPI endpoints
(in-process TestClient — no server process, no network, MOCK_MODE=always).

Ruling-conformance tests that currently FAIL are marked xfail with the finding
id so the suite stays green while mechanically documenting the gap.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, OutboundMessage, Transaction, db_session
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


def _audio_payload(wa_id="923001234567", wamid=None, audio=b"\x01" + b"v " * 40,
                   timestamp="1755798180"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "EBID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"profile": {"name": "Test Merchant"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": wamid or f"wamid.{uuid.uuid4().hex}",
                        "timestamp": timestamp,
                        "type": "audio",
                        "audio": {"id": "media-1", "mime_type": "audio/ogg", "sha256": "x"},
                    }],
                },
                "field": "messages",
            }],
        }],
        "bizro_sim": {
            "media_b64": base64.b64encode(audio).decode(),
            "mime_type": "audio/ogg",
            "filename": "note.ogg",
        },
    }


def _image_payload(wa_id="923007654321", wamid=None, image=b"\x89PNG\r\n\x1a\nmock"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "EBID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"profile": {"name": "Test Merchant"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": wamid or f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180",
                        "type": "image",
                        "image": {"id": "media-2", "mime_type": "image/jpeg", "sha256": "y"},
                    }],
                },
                "field": "messages",
            }],
        }],
        "bizro_sim": {
            "media_b64": base64.b64encode(image).decode(),
            "mime_type": "image/jpeg",
            "filename": "receipt.jpg",
        },
    }


def _tx_count(merchant_id) -> int:
    with db_session() as s:
        return len(
            s.query(Transaction).filter_by(merchant_id=uuid.UUID(merchant_id)).all()
        )


def _tx_count_for_wa(wa_id: str) -> int:
    """Failure paths roll the whole session back (merchant included), so count
    via wa_id rather than a merchant_id the response never carries."""
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa_id).one_or_none()
        if m is None:
            return 0
        return len(s.query(Transaction).filter_by(merchant_id=m.id).all())


def _outbound_bodies(merchant_id) -> list[str]:
    with db_session() as s:
        rows = (
            s.query(OutboundMessage)
            .filter_by(merchant_id=uuid.UUID(merchant_id))
            .all()
        )
        return [r.body or "" for r in rows]


def _outbound_bodies_for_wa(wa_id: str) -> list[str]:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa_id).one_or_none()
        if m is None:
            return []
        rows = s.query(OutboundMessage).filter_by(merchant_id=m.id).all()
        return [r.body or "" for r in rows]


# ---------------------------------------------------------------- happy paths


def test_voice_ingest_happy_path_persists_and_confirms(client):
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923001111111"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True
    assert out["transaction_id"]
    assert out["status"] == "pending"  # every AI entry awaits confirmation
    assert _tx_count(out["merchant_id"]) == 1
    assert any("Is this correct" in b for b in _outbound_bodies(out["merchant_id"]))


def test_image_ingest_happy_path_d0_12_datetime_occurred_at(client):
    """Server passes a datetime into vision; the D0-12 coercion must land a
    valid ISO string through persist (TransactionIn.occurred_at parses it)."""
    r = client.post("/webhook/whatsapp", json=_image_payload(wa_id="923002222222"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(out["transaction_id"]))
        assert tx.item_lines and len(tx.item_lines) == 3  # clean mock receipt
        assert tx.occurred_at is not None


@pytest.mark.xfail(
    reason="F-8 [P2]: SQLite DateTime round-trip drops tzinfo, so "
    "transaction_to_wire emits naive ISO strings ('2025-08-21T17:43:00' with no "
    "offset) — violating §6.6's tz-aware ISO example on the default dev DB "
    "(Postgres TIMESTAMPTZ round-trips fine).",
    strict=False,
)
def test_wire_occurred_at_is_tz_aware_per_6_6(client):
    from server.app.schemas import transaction_to_wire

    r = client.post("/webhook/whatsapp", json=_image_payload(wa_id="923002222223"))
    out = r.json()["results"][0]
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(out["transaction_id"]))
        when = __import__("datetime").datetime.fromisoformat(
            transaction_to_wire(tx)["occurred_at"]
        )
        assert when.tzinfo is not None


def test_text_reply_confirms_latest_pending(client):
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923003333333"))
    mid = r.json()["results"][0]["merchant_id"]
    r2 = client.post(
        "/webhook/whatsapp",
        json={
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "923003333333",
                            "id": f"wamid.{uuid.uuid4().hex}",
                            "timestamp": "1755798200",
                            "type": "text",
                            "text": {"body": "1"},
                        }],
                    },
                    "field": "messages",
                }],
            }],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["results"][0]["ok"] is True
    with db_session() as s:
        txs = (
            s.query(Transaction)
            .filter_by(merchant_id=uuid.UUID(mid))
            .order_by(Transaction.created_at.desc())
            .all()
        )
        assert txs[0].status == "confirmed"


# ------------------------------------------------------------- ruling failures


@pytest.mark.xfail(
    reason="F-5 [P1]: no message-id dedupe — Meta redelivery double-posts the "
    "same voice note into two transactions + two media blobs (bizro-security "
    "'Idempotency' rule; schema.md §2 audit integrity).",
    strict=False,
)
def test_duplicate_webhook_delivery_is_idempotent(client):
    payload = _audio_payload(wa_id="923004444444", wamid="wamid.DUPPLICATE.1")
    r1 = client.post("/webhook/whatsapp", json=payload)
    r2 = client.post("/webhook/whatsapp", json=payload)  # Meta redelivery
    assert r1.status_code == r2.status_code == 200
    mid = r1.json()["results"][0]["merchant_id"]
    assert _tx_count(mid) == 1, "same wamid POSTed twice must yield ONE transaction"


def test_unknown_amount_persists_nothing(client, monkeypatch):
    """§6.9 (D2-1 ruling): ambiguous amount → clarification sent, nothing persisted,
    message handled OK. The old ok:false/internal silence is abolished."""
    monkeypatch.setenv("MOCK_SCENARIO", "ambiguous_amount")
    wa = "923005555555"
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id=wa))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert _tx_count_for_wa(wa) == 0, "no guessed amount may be persisted"
    assert out["ok"] is True and out.get("persisted") is False
    assert any("How much" in b for b in _outbound_bodies_for_wa(wa))


def test_non_receipt_image_persists_nothing(client, monkeypatch):
    """§6.4+§6.9: non-receipt photo → polite Urdu reply, nothing persisted, OK."""
    from vision_agent.adapters import MockOcrAdapter
    import vision_agent.pipeline as vpipe

    monkeypatch.setattr(
        vpipe, "get_adapter", lambda s: MockOcrAdapter(s, scenario="not_receipt")
    )
    wa = "923006666666"
    r = client.post("/webhook/whatsapp", json=_image_payload(wa_id=wa))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert _tx_count_for_wa(wa) == 0
    assert out["ok"] is True and out.get("persisted") is False
    assert any(b.strip() for b in _outbound_bodies_for_wa(wa))


@pytest.mark.xfail(
    reason="F-4 [P1]: dispatch never threads history into the vision pipeline, "
    "so a receipt with a 10x wrong price ingests flag=none via the webhook.",
    strict=False,
)
def test_wrong_price_receipt_flagged_through_webhook(client, monkeypatch):
    from vision_agent.adapters import MockOcrAdapter
    import vision_agent.pipeline as vpipe

    monkeypatch.setattr(
        vpipe, "get_adapter", lambda s: MockOcrAdapter(s, scenario="wrong_price")
    )
    # First ingest seeds history; second identical receipt should flag.
    wa = "923007777777"
    client.post("/webhook/whatsapp", json=_image_payload(wa_id=wa))
    r = client.post("/webhook/whatsapp", json=_image_payload(wa_id=wa))
    out = r.json()["results"][0]
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(out["transaction_id"]))
        assert tx.flag in ("price_anomaly", "duplicate_suspect")


@pytest.mark.xfail(
    reason="F-2 [P1]: persisted voice mock rows carry raw_output.mock_scenario, "
    "not the §6.3 canonical raw_output.mock=true that dashboard/report layers "
    "are told to key on.",
    strict=False,
)
def test_voice_mock_row_carries_canonical_mock_marker(client):
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923008888888"))
    out = r.json()["results"][0]
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(out["transaction_id"]))
        assert (tx.raw_model_output or {}).get("mock") is True


# ------------------------------------------------------- threshold + REST API


def _persist_with_confidence(conf: float, status: str = "confirmed") -> tuple[str, str, str]:
    from server.app import dispatch as disp
    from server.app.db import Merchant

    wa_id = f"92345{uuid.uuid4().hex[:10]}"  # collision-proof
    with db_session() as s:
        m = Merchant(wa_id=wa_id, display_name="T")
        s.add(m)
        s.flush()
        tx = disp.persist_transaction(
            s,
            m,
            {
                "kind": "sale",
                "amount_pkr": 100.0,
                "occurred_at": "2026-08-21T10:00:00+00:00",
                "source": {"type": "manual", "confidence": conf},
                "status": status,
                "confirmation_ur": None,
            },
            None,
        )
        return str(tx.id), str(m.id), tx.status


def test_threshold_boundary_at_persist_level():
    """schema.md §1: confidence < 0.75 forces pending. Exactly 0.75 must NOT
    (strict <). No float-epsilon surprise may decide confirmation."""
    for conf, expected in ((0.75, "confirmed"), (0.75 + 1e-9, "confirmed"),
                           (0.75 - 1e-9, "pending"), (0.749999, "pending")):
        _, _, status = _persist_with_confidence(conf)
        assert status == expected, f"confidence={conf!r} -> status={status}"


@pytest.mark.xfail(
    reason="F-7 [P1]: api.py:179 references sqlalchemy `func` which is never "
    "imported — any PATCH carrying counterparty (the merchant-correction flow) "
    "crashes with NameError/500.",
    strict=False,
)
def test_patch_with_counterparty_correction(client):
    # seed one transaction
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923301111111"))
    tx_id = r.json()["results"][0]["transaction_id"]
    resp = client.patch(
        f"/api/transactions/{tx_id}", json={"counterparty": {"name": "Ahmad Raza"}}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "edited"  # §6.7: wire row top-level


def test_patch_keeps_original_values_audit_snapshot(client):
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923302222222"))
    tx_id = r.json()["results"][0]["transaction_id"]
    resp = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkr": 6000})
    assert resp.status_code == 200
    body = resp.json()  # §6.7: wire row top-level, original_values inside
    assert body["original_values"]["amount_pkr"] == 5000  # first-edit snapshot
    assert body["amount_pkr"] == 6000
    assert body["status"] == "edited"


def test_rejected_transaction_not_editable(client):
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa_id="923303333333"))
    tx_id = r.json()["results"][0]["transaction_id"]
    client.patch(f"/api/transactions/{tx_id}", json={"status": "rejected"})
    resp = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkr": 10})
    assert resp.status_code == 409


def test_confirm_endpoint_rejects_garbage_id(client):
    resp = client.post("/api/transactions/not-a-uuid/confirm")
    assert resp.status_code == 400
