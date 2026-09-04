"""Day-1 full-sweep additions: the LIVE-path contract between the dashboard's
typed API client (dashboard/src/api/client.ts) and the real server responses,
plus /health, media 410, and the §6.3 mock-marker persistence on credit reports.

Every xfail below was first proven LIVE against the running :8000 server
(evidence in qa/reviews/2026-08-22-full-sweep.md §1); these offline tests pin
the same findings deterministically.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import MediaBlob, db_session
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _audio_payload(wa_id: str, audio: bytes | None = None):
    audio = audio if audio is not None else b"\x01" + b"v " * 40
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Dash Ctx"}, "wa_id": wa_id}],
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


def _seed_pending_tx(client: TestClient, wa: str) -> str:
    r = client.post("/webhook/whatsapp", json=_audio_payload(wa))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    return out["transaction_id"]


# --- C-1 [P0]: POST /confirm response shape -------------------------------------


@pytest.mark.xfail(
    reason="C-1 [P0]: client.ts confirmTransaction (dashboard/src/api/client.ts:105) "
    "types the 200 response as a full Transaction and MonthlyLedgerScreen.tsx:93 "
    "reads data.id from it; the server returns {ok, transaction_id, status} — "
    "data.id is undefined, so the confirmed row NEVER updates and the seal "
    "animation never fires on live data (works only against mocks).",
    strict=False,
)
def test_confirm_response_is_full_wire_transaction(client):
    tx_id = _seed_pending_tx(client, "923601111111")
    r = client.post(f"/api/transactions/{tx_id}/confirm")
    assert r.status_code == 200
    body = r.json()
    # The client-side contract (types/schema.ts Transaction): these fields must
    # be on the response body itself for setTxs(map x.id===data.id -> data) to work.
    for field in ("id", "kind", "amount_pkr", "status", "source", "occurred_at"):
        assert field in body, f"confirm response missing Transaction.{field}"


# --- C-2 [P0]: PATCH response shape ----------------------------------------------


@pytest.mark.xfail(
    reason="C-2 [P0]: client.ts patchTransaction (dashboard/src/api/client.ts:110-113) "
    "types the 200 response body as the Transaction itself; the server returns "
    "{ok, transaction: {...}} — EditTransactionForm.tsx:40 onSaved(data) hands the "
    "screen an object with no id/kind, so the edited row NEVER updates in the "
    "live ledger (mock client returns the bare row, hiding the mismatch).",
    strict=False,
)
def test_patch_response_is_full_wire_transaction(client):
    tx_id = _seed_pending_tx(client, "923602222222")
    r = client.patch(f"/api/transactions/{tx_id}", json={"amount_pkr": 4242})
    assert r.status_code == 200
    body = r.json()
    assert "transaction" not in body or body.get("id"), (
        "PATCH must return the wire Transaction at the TOP level (client.ts contract)"
    )
    for field in ("id", "kind", "amount_pkr", "status"):
        assert field in body, f"patch response missing Transaction.{field}"


# --- H-1 [P1]: /health shadowed by the SPA catch-all -----------------------------


@pytest.mark.xfail(
    reason="H-1 [P1]: main.py registers the SPA fallback GET /{full_path:path} "
    "(server/app/main.py:64) BEFORE GET /health (main.py:79) — Starlette matches "
    "the catch-all first, so /health serves index.html (or the 'not built' JSON) "
    "instead of the integrations/pipelines payload documented in schema.md §4. "
    "Live evidence: curl :8000/health -> 200 text/html doctype.",
    strict=False,
)
def test_health_returns_integration_payload(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert "integrations" in body and "pipelines" in body


# --- M-1: media 410 when the blob row exists but the file is gone ----------------


def test_media_410_when_file_missing_on_disk(client):
    """The audit trail keeps blob rows forever; a missing file must 410 (Gone),
    not 500 or a blank 200 — SourceMedia treats any !ok as 'unavailable'."""
    with db_session() as s:
        m = s.query(MediaBlob).first()
        if m is None:  # no blobs in this test DB yet — seed one via webhook
            client.post("/webhook/whatsapp", json=_audio_payload("923603333333"))
            m = s.query(MediaBlob).first()
    real_path = m.storage_path
    m.storage_path = str(uuid.uuid4()) + "-definitely-missing.ogg"
    s.add(m)
    s.commit()
    missing_id = str(m.id)
    try:
        r = client.get(f"/api/media/{missing_id}")
        assert r.status_code == 410, f"expected 410 Gone, got {r.status_code}: {r.text[:120]}"
    finally:
        with db_session() as s2:
            row = s2.get(MediaBlob, uuid.UUID(missing_id))
            if row is not None:
                row.storage_path = real_path
                s2.add(row)
                s2.commit()


# --- W-1 [P2]: wire transaction omits confirmation_ur declared by the client type


@pytest.mark.xfail(
    reason="W-1 [P2]: transaction_to_wire (server/app/schemas.py:90-125) never emits "
    "confirmation_ur, but dashboard types/schema.ts:60 declares it non-optional and "
    "AuditTrail.tsx:150 renders it — on live data the Urdu confirmation line "
    "silently disappears (mock fixtures always include it, hiding the gap).",
    strict=False,
)
def test_wire_transaction_carries_confirmation_ur(client):
    tx_id = _seed_pending_tx(client, "923604444444")
    r = client.get("/api/merchants/me/transactions")
    assert r.status_code == 200
    row = next(t for t in r.json()["transactions"] if t["id"] == tx_id)
    assert "confirmation_ur" in row


# --- R-1 [P2]: refresh double-writes credit_reports ------------------------------


@pytest.mark.xfail(
    reason="R-1 [P2]: GET /report/preview?refresh=true writes TWO credit_reports "
    "rows — credit_agent.generate_report commits its own row (with the §6.3 mock "
    "key STRIPPED, credit-agent/credit_agent/report.py:134) and then api.py:264-275 "
    "commits a second one (mock kept, but model=None because it reads the absent "
    "'generator' key). The dead marker-less row is a §6.3 landmine for any future "
    "consumer of credit_reports; the model=None column mislabels provenance.",
    strict=False,
)
def test_report_refresh_writes_single_row(client):
    from server.app.db import CreditReport, Merchant

    wa = f"92360{uuid.uuid4().hex[:8]}"
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Report Ctx")
        s.add(m)
        s.commit()
        mid = str(m.id)
    try:
        r = client.get(f"/api/merchants/{mid}/report/preview?refresh=true")
        assert r.status_code == 200
        with db_session() as s:
            rows = (
                s.query(CreditReport).filter_by(merchant_id=uuid.UUID(mid)).all()
            )
            assert len(rows) == 1, f"one refresh must write ONE row, wrote {len(rows)}"
    finally:
        with db_session() as s:
            for row in (
                s.query(CreditReport).filter_by(merchant_id=uuid.UUID(mid)).all()
            ):
                s.delete(row)
            for mm in s.query(Merchant).filter_by(wa_id=wa).all():
                s.delete(mm)
            s.commit()
