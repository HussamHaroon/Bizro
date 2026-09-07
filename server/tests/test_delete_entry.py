"""Delete-entry block (owner request 2026-10-02): DELETE /api/transactions/{id}
is a TRUE erase — the transaction row, its media_blobs rows (the source voice
note / receipt photo, plus any lazily-rendered invoice image pinned into an
outbound row's payload), the disk fast-path files, and the outbound audit rows
all go together. A half-delete (row gone, voice note bytes still stored) would
silently break the "wherever they live" promise.

Everything runs offline (MOCK_MODE=always, pinned in conftest.py) against the
throwaway SQLite DB — never main's bizro.db. Media bytes land in the repo's
gitignored media/ tree through the REAL webhook ingest path (same as the other
suites); DELETE then proves they are removed.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app.db import MediaBlob, Merchant, OutboundMessage, Transaction, db_session
from server.app.main import app


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """Tables must exist even when tests are picked individually (the client
    fixture's lifespan is what usually runs init_db)."""
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db + fresh rate limits
        yield c


# ----------------------------------------------------------------- helpers


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _audio_payload(wa_id: str):
    """Simulator envelope carrying synthetic voice bytes — the REAL ingest path:
    size/magic validation, disk write, media_blobs row (with durable bytes),
    mock pipeline parse, pending transaction + confirmation outbound row."""
    audio = b"\x01" + b"v " * 40  # no known magic — accepted with a warning
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Del Ctx"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": f"wamid.{uuid.uuid4().hex}",
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


def _seed_voice_tx(client: TestClient, wa: str) -> dict:
    """One webhook voice note → {transaction_id, media_id, storage_path,...}."""
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    assert out["media"]["id"], out
    return out


def _seed_manual_tx(merchant_id, *, confirmation_ur: str = "") -> str:
    """Manual entry via the real persist path (no media row can exist)."""
    from server.app import dispatch as disp

    with db_session() as s:
        tx = disp.persist_transaction(
            s,
            s.get(Merchant, merchant_id),
            {
                "kind": "sale",
                "amount_pkr": 800.0,
                "occurred_at": "2026-09-20T10:00:00+00:00",
                "source": {"type": "manual", "media_id": None, "model": None,
                           "confidence": 0.99, "raw_output": {}},
                "status": "confirmed",
                "confirmation_ur": confirmation_ur or None,
            },
            None,
        )
        return str(tx.id)


# =============================== the erase ==================================


def test_delete_erases_transaction_media_and_audit_rows(client):
    """The full promise in one: row, media_blobs row, disk file, audit rows —
    and the media route 404s afterwards because nothing backs it anymore."""
    wa = _wa("92700")
    out = _seed_voice_tx(client, wa)
    tx_id, media_id = out["transaction_id"], out["media"]["id"]
    disk = Path(out["media"]["storage_path"])

    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(tx_id))
        assert tx is not None and str(tx.source_media_id) == media_id
        blob = s.get(MediaBlob, uuid.UUID(media_id))
        assert blob is not None and blob.data, "durable bytea copy must exist pre-delete"
        assert disk.is_file(), "disk fast-path file must exist pre-delete"
        assert (
            s.query(OutboundMessage).filter_by(transaction_id=uuid.UUID(tx_id)).count() >= 1
        ), "pending voice entries carry a confirmation audit row"

    r = client.delete(f"/api/transactions/{tx_id}")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": True, "transaction_id": tx_id, "media_removed": 1}

    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)) is None
        assert s.get(MediaBlob, uuid.UUID(media_id)) is None
        assert s.query(OutboundMessage).filter_by(transaction_id=uuid.UUID(tx_id)).count() == 0
    assert not disk.exists(), "disk fast-path file must be removed too"
    assert client.get(f"/api/media/{media_id}").status_code == 404

    # Erase is final: a second DELETE has nothing left to delete.
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 404


def test_delete_manual_entry_reports_zero_media_and_drops_audit_rows(client):
    """Manual entries have no media anywhere — media_removed is an honest 0,
    and the confirmation audit row still goes with the entry."""
    with db_session() as s:
        m = Merchant(wa_id=_wa("92701"), display_name="Del Manual Ctx")
        s.add(m)
        s.commit()
        mid = m.id
    tx_id = _seed_manual_tx(mid, confirmation_ur="Cash sale: 800 rupees recorded.")
    with db_session() as s:
        assert s.query(OutboundMessage).filter_by(transaction_id=uuid.UUID(tx_id)).count() == 1

    r = client.delete(f"/api/transactions/{tx_id}")
    assert r.status_code == 200, r.text
    assert r.json()["media_removed"] == 0
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)) is None
        assert s.query(OutboundMessage).filter_by(transaction_id=uuid.UUID(tx_id)).count() == 0


def test_delete_also_erases_invoice_media_pinned_in_outbound_payload(client):
    """The lazily-rendered invoice image (a MediaBlob pinned into the outbound
    row's payload.media_id) belongs to the transaction too: it is counted,
    unlinked from disk, and the renderer's per-tx cache file goes as well."""
    wa = _wa("92702")
    out = _seed_voice_tx(client, wa)
    tx_id, source_media = out["transaction_id"], out["media"]["id"]
    tid = uuid.UUID(tx_id)

    from server.app.config import get_settings
    from server.app.media import store_blob

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16  # valid magic for kind="image"
    storage, digest = store_blob(png, "image/png", "image")
    with db_session() as s:
        # Mimic _ensure_invoice_media's pin: new blob + payload.media_id.
        blob = MediaBlob(
            merchant_id=s.get(Transaction, tid).merchant_id,
            kind="image",
            mime_type="image/png",
            storage_path=str(storage),
            sha256=digest,
            data=png,
        )
        s.add(blob)
        s.flush()
        row = (
            s.query(OutboundMessage)
            .filter_by(transaction_id=tid, kind="confirmation_text")
            .order_by(OutboundMessage.created_at)
            .first()
        )
        payload = dict(row.payload or {})
        payload["media_id"] = str(blob.id)
        row.payload = payload
        s.commit()
        invoice_media = str(blob.id)
    invoice_cache = get_settings().media_dir / "invoices" / f"invoice_{tid}.png"
    invoice_cache.parent.mkdir(parents=True, exist_ok=True)
    invoice_cache.write_bytes(png)

    r = client.delete(f"/api/transactions/{tx_id}")
    assert r.status_code == 200, r.text
    assert r.json()["media_removed"] == 2, "source voice note + invoice image"

    with db_session() as s:
        assert s.get(MediaBlob, uuid.UUID(source_media)) is None
        assert s.get(MediaBlob, uuid.UUID(invoice_media)) is None
    assert not Path(storage).exists(), "invoice blob's media-tree copy must go"
    assert not invoice_cache.exists(), "renderer's per-tx cache file must go"
    assert client.get(f"/api/media/{invoice_media}").status_code == 404


def test_delete_unknown_or_malformed_id_is_clean_404_400(client):
    """Same error idioms as every other /transactions/{id} route."""
    r = client.delete(f"/api/transactions/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["detail"] == "transaction not found"
    r = client.delete("/api/transactions/not-a-uuid")
    assert r.status_code == 400
    assert "invalid transaction id" in r.json()["detail"]


def test_delete_leaves_sibling_transactions_alone(client):
    """Scoping: erasing one entry must not touch a sibling from the same
    merchant — its row, media, and audit rows survive, and the list endpoint
    still shows it."""
    wa = _wa("92703")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Del Sibling Ctx")
        s.add(m)
        s.commit()
        mid = m.id
    kept = _seed_voice_tx(client, wa)  # same wa → same webhook merchant
    gone = _seed_voice_tx(client, wa)

    r = client.delete(f"/api/transactions/{gone['transaction_id']}")
    assert r.status_code == 200, r.text

    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(kept["transaction_id"])) is not None
        assert s.get(MediaBlob, uuid.UUID(kept["media"]["id"])) is not None
        assert Path(kept["media"]["storage_path"]).is_file()
    listed = client.get(f"/api/merchants/{mid}/transactions").json()
    ids = [t["id"] for t in listed["transactions"]]
    assert kept["transaction_id"] in ids
    assert gone["transaction_id"] not in ids

    # cleanup the kept sibling's row so later modules stay hermetic
    client.delete(f"/api/transactions/{kept['transaction_id']}")
