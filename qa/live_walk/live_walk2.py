"""Part 2 of the live walk — reuses the QA merchant left by live_walk.py,
finishes the remaining endpoint checks, then cleans up the DB."""
from __future__ import annotations

import json
import sqlite3
import urllib.request
import urllib.error
import uuid

BASE = "http://localhost:8000"
QA_WA_ID = "923009000777"
DB = r"D:\02-Study\AlkhidmatHackathon\bizro.db"


def req(url: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body[:300]
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:300]


conn = sqlite3.connect(DB)
mid = conn.execute("SELECT id FROM merchants WHERE wa_id=?", (QA_WA_ID,)).fetchone()[0]
print("QA merchant:", mid)
conn.close()

st, txs = req(f"{BASE}/api/merchants/{mid}/transactions")
tx = txs["transactions"][0]
tx_id, media_id = tx["id"], tx["source"]["media_id"]
print("using tx:", tx_id, tx["status"], "media:", media_id)

st, cp = req(f"{BASE}/api/transactions/{tx_id}", "PATCH",
             {"counterparty": {"name": "Zubair", "phone": None}})
print(f"[patch-counterparty] HTTP {st} -> {cp if isinstance(cp, (dict, list)) else cp!r}")

st, g = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {"amount_pkd": -5})
print(f"[patch-garbage amount=-5] HTTP {st} -> {str(g)[:120]}")

st, g2 = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {"kind": "nonsense"})
print(f"[patch-garbage kind=nonsense] HTTP {st} -> {str(g2)[:120]}")

st, g3 = req(f"{BASE}/api/transactions/{tx_id}", "PATCH", {})
print(f"[patch-empty] HTTP {st} -> {str(g3)[:120]}")

st, _ = req(f"{BASE}/api/media/{media_id}")
print(f"[media-ok] HTTP {st}")
st, _ = req(f"{BASE}/api/media/{uuid.uuid4()}")
print(f"[media-404] HTTP {st}")
st, b = req(f"{BASE}/api/media/not-a-uuid")
print(f"[media-badid] HTTP {st} -> {str(b)[:80]}")
# path traversal shape: FastAPI path param won't include slashes; encoded traversal
st, b = req(f"{BASE}/api/media/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
print(f"[media-traversal-encoded] HTTP {st} -> {str(b)[:80]}")

st, rep = req(f"{BASE}/api/merchants/{mid}/report/preview?refresh=true")
if isinstance(rep, dict):
    r = rep.get("report", rep)
    print(f"[report-empty-history] HTTP {st} readiness={json.dumps(r.get('readiness'), ensure_ascii=False)[:200]} "
          f"line_items={len(r.get('line_items') or [])} criteria_basis={r.get('criteria_basis')!r}")
else:
    print(f"[report-empty-history] HTTP {st} -> {rep!r}")

# filter checks used by the dashboard month/query params
st, f1 = req(f"{BASE}/api/merchants/{mid}/transactions?kind=udhar_given")
print(f"[filter kind=udhar_given] HTTP {st} count={f1.get('count') if isinstance(f1, dict) else f1}")
st, f2 = req(f"{BASE}/api/merchants/{mid}/transactions?from=2026-01-01&to=2026-12-31")
print(f"[filter from/to] HTTP {st} count={f2.get('count') if isinstance(f2, dict) else f2}")

# 404 transaction / bad uuid
st, b = req(f"{BASE}/api/transactions/{uuid.uuid4()}/confirm", "POST")
print(f"[confirm-unknown] HTTP {st} -> {str(b)[:100]}")

# cleanup
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT id FROM merchants WHERE wa_id=?", (QA_WA_ID,))
rows = cur.fetchall()
for (m,) in rows:
    cur.execute("DELETE FROM transactions WHERE merchant_id=?", (m,))
    cur.execute("DELETE FROM outbound_messages WHERE merchant_id=?", (m,))
    cur.execute("DELETE FROM customers WHERE merchant_id=?", (m,))
    cur.execute("DELETE FROM media_blobs WHERE merchant_id=?", (m,))
    cur.execute("DELETE FROM credit_reports WHERE merchant_id=?", (m,))
    cur.execute("DELETE FROM merchants WHERE id=?", (m,))
conn.commit()
print(f"cleanup: removed {len(rows)} QA merchant(s)")
conn.close()
