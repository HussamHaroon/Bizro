"""Live-path walk evidence script — run against the live :8000 server (mock mode).

Creates a disposable QA merchant via the webhook simulator, then exercises every
dashboard data call and records the ACTUAL response shapes vs what
dashboard/src/api/client.ts expects. Cleans up after itself (deletes the QA
merchant rows from bizro.db).

Usage: python live_walk.py   (server must be running on :8000)
"""
from __future__ import annotations

import base64
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://localhost:8000"
QA_WA_ID = "923009000777"
QA_NAME = "QA Sweep Bot (disposable)"
DB = r"D:\02-Study\AlkhidmatHackathon\bizro.db"

sys.path.insert(0, r"D:\02-Study\AlkhidmatHackathon")


def req(url: str, method: str = "GET", payload: dict | None = None, raw_body: bytes | None = None):
    data = raw_body if raw_body is not None else (json.dumps(payload).encode() if payload is not None else None)
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body[:200]
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:200]


def synth_audio(stamp: int) -> bytes:
    header = f"BIZRO-QA-SWEEP ts={stamp}".encode()
    # pad to >64 bytes so voice_agent's infer_scenario picks clean_udhar
    # (sub-64-byte junk maps to garbage_audio — that path is tested separately)
    return header + b"\x00" + uuid.uuid4().bytes + b"\x00" * 48


def build_voice_payload(wamid: str, stamp: int) -> dict:
    data = base64.b64encode(synth_audio(stamp)).decode()
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "SIM_WABA",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001111", "phone_number_id": "SIM"},
                    "contacts": [{"profile": {"name": QA_NAME}, "wa_id": QA_WA_ID}],
                    "messages": [{
                        "from": QA_WA_ID,
                        "id": wamid,
                        "timestamp": str(int(time.time())),
                        "type": "audio",
                        "audio": {"id": f"SIM_MEDIA_{uuid.uuid4().hex[:8]}", "mime_type": "audio/ogg; codecs=opus"},
                    }],
                },
            }],
        }],
        "bizro_sim": {"media_b64": data, "mime_type": "audio/ogg; codecs=opus"},
    }


def main() -> None:
    findings: list[str] = []

    # ---- 0) health (expectation: JSON integrations/pipelines; schema.md §4) ----
    st, health = req(f"{BASE}/health")
    print(f"[health] HTTP {st} -> {str(health)[:120]}")
    if not (isinstance(health, dict) and "integrations" in health):
        findings.append("[P1] GET /health does NOT return the health JSON (SPA catch-all "
                        "main.py:64 registered before /health main.py:79 shadows it) — got HTML instead")

    # ---- 1) idempotency: same wamid POSTed twice -> one transaction expected ----
    wamid = f"wamid.QASWEEP{uuid.uuid4().hex[:10]}"
    payload = build_voice_payload(wamid, time.time_ns())
    st1, r1 = req(f"{BASE}/webhook/whatsapp", "POST", payload)
    st2, r2 = req(f"{BASE}/webhook/whatsapp", "POST", payload)  # identical bytes, identical wamid
    merchant_id = r1["results"][0]["merchant_id"]
    st3, txs = req(f"{BASE}/api/merchants/{merchant_id}/transactions")
    n = txs["count"]
    print(f"[dedupe] POST same wamid twice -> HTTP {st1}/{st2}; transactions now: {n}")
    if n != 1:
        findings.append(f"[P1] Webhook is NOT idempotent: identical payload (same message id) POSTed "
                        f"twice created {n} transactions (Meta redelivers webhooks — bizro-security hard rule)")

    tx = txs["transactions"][0]
    tx_id = tx["id"]
    media_id = tx["source"]["media_id"]

    # ---- 2) wire Transaction shape vs dashboard/src/types/schema.ts ----
    expected_ts = {"id", "kind", "amount_pkr", "currency", "counterparty", "description",
                   "item_lines", "occurred_at", "source", "flag", "status"}
    missing = expected_ts - set(tx.keys())
    print(f"[wire-tx] keys: {sorted(tx.keys())}")
    print(f"[wire-tx] missing vs Transaction type: {sorted(missing) or 'none'}; "
          f"confirmation_ur present: {'confirmation_ur' in tx}")
    if missing:
        findings.append(f"[P1] wire transaction missing fields the Transaction type declares: {sorted(missing)}")

    # ---- 3) POST /confirm response shape (client expects full Transaction) ----
    st, conf = req(f"{BASE}/api/transactions/{tx_id}/confirm", "POST")
    print(f"[confirm] HTTP {st} -> {json.dumps(conf)[:200]}")
    if isinstance(conf, dict) and "kind" not in conf:
        findings.append("[P0] confirm response is {ok, transaction_id, status} — client.ts:105 "
                        "types it as a full Transaction; MonthlyLedgerScreen.tsx:93 reads data.id "
                        f"(undefined here) so the confirmed row never updates. Got keys: {sorted(conf.keys())}")
    st, conf2 = req(f"{BASE}/api/transactions/{tx_id}/confirm", "POST")
    print(f"[confirm-again] HTTP {st} -> {json.dumps(conf2)[:140]}")

    # ---- 4) PATCH response shape (client expects full Transaction) ----
    st, patch = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {"amount_pkr": 4242, "status": "edited"})
    print(f"[patch] HTTP {st} -> top-level keys {sorted(patch.keys()) if isinstance(patch, dict) else patch}")
    if isinstance(patch, dict) and "transaction" in patch and "kind" not in patch:
        findings.append("[P0] PATCH response nests the row as {ok, transaction} — client.ts:110-113 "
                        "types the whole body as Transaction; EditTransactionForm.tsx:40 onSaved(data) "
                        "gets an object with no id/kind — the edited row never updates in the ledger")

    # ---- 5) PATCH counterparty (dashboard correction path for wrong name) ----
    st, cp = req(f"{BASE}/api/transactions/{tx_id}", "PATCH",
                 {"counterparty": {"name": "Zubair", "phone": None}})
    print(f"[patch-counterparty] HTTP {st} -> {json.dumps(cp)[:200]}")
    if st == 500:
        findings.append("[P1] PATCH with counterparty -> HTTP 500 NameError: api.py:219 uses "
                        "sqlalchemy.func but only `select` is imported (api.py:25)")

    # ---- 6) PATCH garbage (pydantic boundary) ----
    st, g = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {"amount_pkr": -5})
    print(f"[patch-garbage] amount_pkr=-5 -> HTTP {st}")
    if st != 422:
        findings.append(f"[P1] PATCH with invalid amount accepted: HTTP {st}")
    st, g2 = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {})
    print(f"[patch-empty] {{}} -> HTTP {st}")

    # ---- 7) media endpoint ----
    st, _ = req(f"{BASE}/api/media/{media_id}")
    print(f"[media-ok] GET /api/media/{media_id} -> HTTP {st}")
    st, _ = req(f"{BASE}/api/media/{uuid.uuid4()}")
    print(f"[media-404] random uuid -> HTTP {st}")
    st, body = req(f"{BASE}/api/media/../../etc/passwd")
    print(f"[media-traversal] '../..' path -> HTTP {st} ({str(body)[:80]})")
    st, body = req(f"{BASE}/api/media/not-a-uuid")
    print(f"[media-badid] not-a-uuid -> HTTP {st}")

    # ---- 8) webhook signature path (disabled state — no app secret configured) ----
    st, body = req(f"{BASE}/webhook/whatsapp", "POST", raw_body=b"not json at all")
    print(f"[webhook-nonjson] -> HTTP {st} {str(body)[:80]}")

    # ---- 9) report preview for QA merchant (empty history edge) ----
    st, rep = req(f"{BASE}/api/merchants/{merchant_id}/report/preview?refresh=true")
    if isinstance(rep, dict):
        r = rep.get("report", rep)
        print(f"[report-empty] HTTP {st} readiness={json.dumps(r.get('readiness'))[:160]}")
    else:
        print(f"[report-empty] HTTP {st} {str(rep)[:160]}")

    print("\n=== FINDINGS FROM LIVE WALK ===")
    for f in findings:
        print(f)
    print(f"\nmerchant_id={merchant_id} tx={tx_id}")

    # ---- 10) cleanup: remove the disposable QA merchant + rows (data only) ----
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM merchants WHERE wa_id=?", (QA_WA_ID,))
    rows = cur.fetchall()
    for (mid,) in rows:
        cur.execute("DELETE FROM transactions WHERE merchant_id=?", (mid,))
        cur.execute("DELETE FROM outbound_messages WHERE merchant_id=?", (mid,))
        cur.execute("DELETE FROM customers WHERE merchant_id=?", (mid,))
        cur.execute("DELETE FROM media_blobs WHERE merchant_id=?", (mid,))
        cur.execute("DELETE FROM credit_reports WHERE merchant_id=?", (mid,))
        cur.execute("DELETE FROM merchants WHERE id=?", (mid,))
    conn.commit()
    print(f"cleanup: removed {len(rows)} QA merchant(s) and their rows")
    conn.close()


if __name__ == "__main__":
    main()
