"""Day-2 fix block — one TestClient test per QA finding (2026-08-22 sweep).

Covers: C-1/C-2 (§6.7 wire-row mutations), H-1 (/health), F-5 (webhook
idempotency, §6.8), F-7 (PATCH counterparty), F-1/F-6 (§6.9 clarification +
rejection — reply sent, nothing persisted), F-4 (price history threading),
E-1 (amount bound, §6.10), R-1 (single credit_reports row + mock key kept),
W-1 (confirmation_ur on the wire), SEC P2s (constant-time verify token,
media magic/size caps).

Everything runs offline (MOCK_MODE=always) against a throwaway SQLite DB
pinned in conftest.py — never main's bizro.db.
"""

from __future__ import annotations

import base64
import uuid

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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


# ----------------------------------------------------------------- helpers


def _audio_payload(wa_id: str, audio: bytes | None = None, wamid: str | None = None,
                   timestamp: str = "1755798180"):
    audio = audio if audio is not None else b"\x01" + b"v " * 40
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Fix Blk"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": wamid or f"wamid.{uuid.uuid4().hex}",
                        "timestamp": timestamp,
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


def _image_payload(wa_id: str, image: bytes | None = None, wamid: str | None = None):
    image = image if image is not None else b"\x89PNG\r\n\x1a\nmock"
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": wa_id,
                        "id": wamid or f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180",
                        "type": "image",
                        "image": {"id": "m2", "mime_type": "image/jpeg"},
                    }],
                },
                "field": "messages",
            }],
        }],
        "bizro_sim": {
            "media_b64": base64.b64encode(image).decode(),
            "mime_type": "image/jpeg",
        },
    }


def _seed_pending_tx(client: TestClient, wa: str) -> str:
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    return out["transaction_id"]


def _txs_for_wa(wa: str) -> list:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one_or_none()
        if m is None:
            return []
        return s.query(Transaction).filter_by(merchant_id=m.id).all()


def _outbound_for_wa(wa: str) -> list[str]:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one_or_none()
        if m is None:
            return []
        return [r.body or "" for r in
                s.query(OutboundMessage).filter_by(merchant_id=m.id).all()]


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


# ------------------------------------------------- C-1: confirm wire row


def test_c1_confirm_returns_full_wire_transaction(client):
    tx_id = _seed_pending_tx(client, _wa("92370"))
    r = client.post(f"/api/transactions/{tx_id}/confirm")
    assert r.status_code == 200, r.text
    body = r.json()
    for field in ("id", "kind", "amount_pkd", "status", "source", "occurred_at"):
        assert field in body, f"confirm response missing Transaction.{field}"
    assert body["id"] == tx_id  # the row itself, not an {ok,...} wrapper
    assert body["status"] == "confirmed"


def test_c1_confirm_double_still_409(client):
    tx_id = _seed_pending_tx(client, _wa("92371"))
    assert client.post(f"/api/transactions/{tx_id}/confirm").status_code == 200
    assert client.post(f"/api/transactions/{tx_id}/confirm").status_code == 409


# ------------------------------------------------- C-2: PATCH wire row


def test_c2_patch_returns_wire_row_top_level_with_original_values(client):
    tx_id = _seed_pending_tx(client, _wa("92372"))
    r = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkd": 4242})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "transaction" not in body, "§6.7: no {ok, transaction:{...}} wrapper"
    assert body["id"] == tx_id
    assert body["amount_pkd"] == 4242
    assert body["status"] == "edited"
    # §6.7: PATCH additionally carries the pre-edit snapshot alongside.
    assert body["original_values"]["amount_pkd"] != 4242


# ------------------------------------------------- H-1: /health JSON


def test_h1_health_returns_integration_payload_not_spa(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert "integrations" in body and "pipelines" in body


# ------------------------------------------------- F-5: webhook dedupe


def test_f5_duplicate_wamid_dedupes(client):
    wa = _wa("92373")
    wamid = f"wamid.DUP.{uuid.uuid4().hex[:8]}"
    payload = _audio_payload(wa, wamid=wamid)
    r1 = client.post("/webhook/whatsapp", json=payload)
    r2 = client.post("/webhook/whatsapp", json=payload)  # Meta redelivery
    assert r1.status_code == r2.status_code == 200
    assert len(_txs_for_wa(wa)) == 1, "same wamid twice must yield ONE transaction"
    assert r2.json()["results"][0].get("deduped") is True


def test_f5_processed_messages_row_exists(client):
    from server.app.db import ProcessedMessage

    wamid = f"wamid.PM.{uuid.uuid4().hex[:8]}"
    client.post("/webhook/whatsapp", json=_audio_payload(_wa("92374"), wamid=wamid))
    with db_session() as s:
        assert s.get(ProcessedMessage, wamid) is not None


# ------------------------------------------------- F-7: PATCH counterparty


def test_f7_patch_with_counterparty_no_500(client):
    tx_id = _seed_pending_tx(client, _wa("92375"))
    r = client.patch(f"/api/transactions/{tx_id}",
                     json={"counterparty": {"name": "Ahmad Raza"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "edited"
    assert body["counterparty"]["name"] == "Ahmad Raza"


# --------------------------------- F-1 (§6.9): ambiguous amount → clarification


def test_f1_unknown_amount_sends_clarification_persists_nothing(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "ambiguous_amount")
    wa = _wa("92376")
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True, "§6.9: message handled successfully, not internal error"
    assert out.get("rejected") is True and out.get("persisted") is False
    assert len(_txs_for_wa(wa)) == 0
    assert any("رقم" in b for b in _outbound_for_wa(wa)), "clarification must be sent"


def test_f1_pipeline_null_amount_result_is_rejected(client, monkeypatch):
    """Defensive: a pipeline emitting §6.2's canonical null amount (voice-agent
    fix pending) already gets the clarification path today."""
    from server.app import dispatch as disp

    wa = _wa("92377")

    def null_amount_pipeline(path, merchant, occurred_at):
        return {
            "kind": "udhar_given",
            "amount_pkd": None,
            "occurred_at": occurred_at,
            "source": {"type": "voice", "media_id": None, "model": None,
                       "confidence": 0.2, "raw_output": {}},
            "flag": "low_confidence",
            "status": "pending",
            "confirmation_ur": "رقم کتنی تھی؟",
        }

    monkeypatch.setitem(disp._pipeline_cache, "voice_agent.pipeline.process_voice_note",
                        null_amount_pipeline)
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["persisted"] is False
    assert out["reply_ur"] == "رقم کتنی تھی؟"
    assert len(_txs_for_wa(wa)) == 0


def test_f1_rejected_payload_dict_sends_reply_ur(client, monkeypatch):
    from server.app import dispatch as disp

    wa = _wa("92378")

    def rejects(path, merchant, occurred_at):
        return {"rejected": True, "reply_ur": "یہ رسید نہیں لگتی۔"}

    monkeypatch.setitem(disp._pipeline_cache, "vision_agent.pipeline.process_receipt_image",
                        rejects)
    r = client.post("/webhook/whatsapp", json=_image_payload(wa))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["persisted"] is False
    assert out["reply_ur"] == "یہ رسید نہیں لگتی۔"
    assert len(_txs_for_wa(wa)) == 0


# ------------------------------------- F-6 (§6.4): ReceiptRejected → reply


def test_f6_receipt_rejected_exception_gets_polite_reply(client, monkeypatch):
    from vision_agent.adapters import MockOcrAdapter
    import vision_agent.pipeline as vpipe

    monkeypatch.setattr(vpipe, "get_adapter",
                        lambda s: MockOcrAdapter(s, scenario="not_receipt"))
    wa = _wa("92379")
    r = client.post("/webhook/whatsapp", json=_image_payload(wa))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True, "F-6: reply must reach the merchant, not ok:false internal"
    assert out["persisted"] is False
    assert len(_txs_for_wa(wa)) == 0
    assert any(b.strip() for b in _outbound_for_wa(wa))


# ------------------------------------- F-4: price history threading


def test_f4_dispatch_threads_history_into_vision():
    import inspect
    from server.app import dispatch

    src = inspect.getsource(dispatch.process_receipt_image)
    assert "history" in src, "dispatch must thread history to the vision call"


def test_f4_wrong_price_receipt_flagged_through_webhook(client, monkeypatch):
    from vision_agent.adapters import MockOcrAdapter
    import vision_agent.pipeline as vpipe

    monkeypatch.setattr(vpipe, "get_adapter",
                        lambda s: MockOcrAdapter(s, scenario="wrong_price"))
    wa = _wa("92380")
    client.post("/webhook/whatsapp", json=_image_payload(wa))  # seeds history
    r = client.post("/webhook/whatsapp", json=_image_payload(wa))  # same receipt
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    with db_session() as s:
        txs = (
            s.query(Transaction)
            .join(Merchant, Transaction.merchant_id == Merchant.id)
            .filter(Merchant.wa_id == wa)
            .order_by(Transaction.created_at.desc())
            .all()
        )
        assert len(txs) == 2
        assert txs[0].flag in ("price_anomaly", "duplicate_suspect"), txs[0].flag


def test_f4_price_history_shape_is_wire_dicts():
    from datetime import datetime, timezone

    from server.app import dispatch as disp

    wa = _wa("92381")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Hist")
        s.add(m)
        s.flush()
        tx = disp.persist_transaction(
            s, m,
            {
                "kind": "expense",
                "amount_pkd": 2560.0,
                "counterparty": {"name": "Al-Madina Kiryana Store", "phone": None},
                "item_lines": [{"item": "chai patti", "qty": 2, "unit": "packet",
                                "unit_price": 350, "line_total": 700}],
                "occurred_at": "2025-08-21T17:43:00+00:00",
                "source": {"type": "photo", "confidence": 0.9},
                "status": "confirmed",
            },
            None,
        )
        history = disp.price_history(s, m.id)
    assert len(history) == 1
    row = history[0]
    # vision_agent.sanity keys on these fields (schema.md §1 wire form)
    assert row["kind"] == "expense"
    assert row["item_lines"][0]["item"] == "chai patti"
    assert row["item_lines"][0]["unit_price"] == 350
    assert row["counterparty"]["name"] == "Al-Madina Kiryana Store"
    assert row["amount_pkd"] == 2560.0


# ------------------------------------- E-1 (§6.10): amount upper bound


def test_e1_patch_rejects_over_crore(client):
    tx_id = _seed_pending_tx(client, _wa("92382"))
    r = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkd": 10_000_001})
    assert r.status_code == 422
    r = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkd": 1e9})
    assert r.status_code == 422


def test_e1_patch_accepts_boundaries(client):
    tx_id = _seed_pending_tx(client, _wa("92383"))
    r = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkd": 10_000_000})
    assert r.status_code == 200
    assert r.json()["amount_pkd"] == 10_000_000


def test_e1_transaction_in_rejects_absurd_pipeline_output():
    from pydantic import ValidationError

    from server.app.schemas import TransactionIn

    with pytest.raises(ValidationError):
        TransactionIn.model_validate({
            "kind": "sale", "amount_pkd": 100_000_000,
            "occurred_at": "2026-08-21T10:00:00+00:00",
            "source": {"type": "manual", "confidence": 0.9},
        })


# ------------------------------------- R-1: report refresh single row


def test_r1_refresh_writes_exactly_one_row(client):
    wa = _wa("92384")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Report Ctx")
        s.add(m)
        s.commit()
        mid = m.id
    try:
        r = client.get(f"/api/merchants/{mid}/report/preview?refresh=true")
        assert r.status_code == 200, r.text
        with db_session() as s:
            rows = s.query(CreditReport).filter_by(merchant_id=mid).all()
            assert len(rows) == 1, f"one refresh must write ONE row, wrote {len(rows)}"
    finally:
        with db_session() as s:
            for row in s.query(CreditReport).filter_by(merchant_id=mid).all():
                s.delete(row)
            for mm in s.query(Merchant).filter_by(wa_id=wa).all():
                s.delete(mm)
            s.commit()


def test_r1_repeated_preview_without_refresh_writes_no_new_rows(client):
    wa = _wa("92385")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Report Ctx 2")
        s.add(m)
        s.commit()
        mid = m.id
    try:
        assert client.get(f"/api/merchants/{mid}/report/preview?refresh=true").status_code == 200
        for _ in range(3):
            r = client.get(f"/api/merchants/{mid}/report/preview")
            assert r.status_code == 200
            assert r.json()["cached"] is True
        with db_session() as s:
            rows = s.query(CreditReport).filter_by(merchant_id=mid).all()
            assert len(rows) == 1, "cached reads must not write rows"
    finally:
        with db_session() as s:
            for row in s.query(CreditReport).filter_by(merchant_id=mid).all():
                s.delete(row)
            for mm in s.query(Merchant).filter_by(wa_id=wa).all():
                s.delete(mm)
            s.commit()


def test_r1_fallback_report_keeps_mock_key_and_model(client, monkeypatch):
    """Server-fallback path: persisted report_json keeps `mock` (§6.3) and the
    model column reflects the generator, not None."""
    from server.app import dispatch as disp

    monkeypatch.setitem(disp._pipeline_cache, "credit_agent.report.generate_report", None)
    wa = _wa("92386")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Report Ctx 3")
        s.add(m)
        s.commit()
        mid = m.id
    try:
        r = client.get(f"/api/merchants/{mid}/report/preview?refresh=true")
        assert r.status_code == 200
        report = r.json()["report"]
        assert report.get("mock") is True
        with db_session() as s:
            rows = s.query(CreditReport).filter_by(merchant_id=mid).all()
            assert len(rows) == 1
            assert rows[0].report_json.get("mock") is True
            assert rows[0].model == "server_fallback"
    finally:
        with db_session() as s:
            for row in s.query(CreditReport).filter_by(merchant_id=mid).all():
                s.delete(row)
            for mm in s.query(Merchant).filter_by(wa_id=wa).all():
                s.delete(mm)
            s.commit()


# ------------------------------------- W-1: confirmation_ur on the wire


def test_w1_wire_transaction_carries_confirmation_ur(client):
    wa = _wa("92387")
    tx_id = _seed_pending_tx(client, wa)
    mid = str(_txs_for_wa(wa)[0].merchant_id)
    r = client.get(f"/api/merchants/{mid}/transactions")
    assert r.status_code == 200
    row = next(t for t in r.json()["transactions"] if t["id"] == tx_id)
    assert "confirmation_ur" in row
    assert row["confirmation_ur"], "the seeded confirmation text must be there"


def test_w1_confirm_and_patch_responses_carry_confirmation_ur(client):
    tx_id = _seed_pending_tx(client, _wa("92388"))
    body = client.post(f"/api/transactions/{tx_id}/confirm").json()
    assert body["confirmation_ur"]
    body = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkd": 1234}).json()
    assert body["confirmation_ur"]


# ------------------------------------- SEC: verify token constant-time


def test_sec_webhook_verify_handshake(client):
    r = client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "bizro-verify",
        "hub.challenge": "challenge-123",
    })
    assert r.status_code == 200
    assert r.text == "challenge-123"
    r = client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge-123",
    })
    assert r.status_code == 403


# ------------------------------------- SEC: media magic + size caps


def test_sec_media_validation_rules():
    from server.app.media import MediaValidationError, validate_media

    # allowed: png on an image message (even mislabeled jpeg), ogg on voice
    validate_media(b"\x89PNG\r\n\x1a\n" + b"x" * 10, "image")
    validate_media(b"\xff\xd8\xff" + b"x" * 10, "image")
    validate_media(b"OggS" + b"x" * 10, "voice")
    # unrecognized magic (simulator fixtures) passes
    validate_media(b"\x01" + b"v " * 40, "voice")

    with pytest.raises(MediaValidationError):
        validate_media(b"OggS" + b"x" * 10, "image")  # audio on an image message
    with pytest.raises(MediaValidationError):
        validate_media(b"MZ" + b"x" * 64, "image")  # PE executable
    with pytest.raises(MediaValidationError):
        validate_media(b"\x7fELF" + b"x" * 64, "voice")  # ELF executable
    with pytest.raises(MediaValidationError):
        validate_media(b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024), "image")  # >5MB
    with pytest.raises(MediaValidationError):
        validate_media(b"OggS" + b"x" * (16 * 1024 * 1024), "voice")  # >16MB


def test_sec_oversized_media_gets_reply_not_persisted(client):
    wa = _wa("92389")
    big = b"OggS" + b"\x00" * (16 * 1024 * 1024 + 1)
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa, audio=big))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True and out["persisted"] is False
    assert out["rejected"] is True
    assert len(_txs_for_wa(wa)) == 0
    assert any(b.strip() for b in _outbound_for_wa(wa))


def test_sec_executable_uploads_rejected(client):
    wa = _wa("92390")
    exe = b"MZ" + b"\x00" * 64
    r = client.post("/webhook/whatsapp", json=_image_payload(wa, image=exe))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["persisted"] is False
    assert len(_txs_for_wa(wa)) == 0


# ------------------------------------- regressions (must not break)


def test_regression_voice_happy_path_still_persists(client):
    wa = _wa("92391")
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    out = r.json()["results"][0]
    assert out["ok"] is True and out["transaction_id"] and out["status"] == "pending"
    assert len(_txs_for_wa(wa)) == 1


def test_regression_udhar_and_media_endpoints_alive(client):
    wa = _wa("92392")
    tx_id = _seed_pending_tx(client, wa)
    mid = str(_txs_for_wa(wa)[0].merchant_id)
    assert client.get(f"/api/merchants/{mid}/udhar").status_code == 200
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(tx_id))
        r = client.get(f"/api/media/{tx.source_media_id}")
    assert r.status_code == 200
