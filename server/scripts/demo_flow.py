"""One-command demo driver — the rehearsal + recording assistant (Day 4).

Drives the whole Bizro story end-to-end through real HTTP calls and prints a
judge-facing timeline: what happens on the phone and on the dashboard at each
moment, with wall-clock ms per step.

    python server/scripts/demo_flow.py                     # :8000 if up, else in-process
    python server/scripts/demo_flow.py --local             # force in-process (TestClient)
    python server/scripts/demo_flow.py --url http://localhost:8000
    python server/scripts/demo_flow.py --merchant <uuid>   # target a specific merchant

Mock-safe with zero keys: if the merchants table is empty, demo data is seeded
first (credit_agent.seed.seed_demo via the same lazy-import dispatch uses).
Exits non-zero the moment any step fails, so a broken demo dies in rehearsal
instead of on stage. Timings are labeled MOCK MODE unless DASHSCOPE_API_KEY is
live on the target server.
"""

from __future__ import annotations

import argparse
import base64
import importlib
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

MOCK_TIMING_LABEL = "MOCK MODE timings; live timings need DASHSCOPE_API_KEY"
LIVE_TIMING_LABEL = "LIVE MODE timings"

DEFAULT_URL = "http://localhost:8000"


class StepFailure(Exception):
    """A demo step broke — fail the rehearsal loudly."""


# --------------------------------------------------------------------------
# HTTP layer: same two-method contract over a running server or TestClient.
# --------------------------------------------------------------------------


def _maybe_json(resp: Any) -> Any:
    try:
        return resp.json()
    except Exception:
        return getattr(resp, "text", str(resp))


class RemoteHttp:
    """Thin urllib client against a RUNNING server (default :8000)."""

    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, method: str, payload: dict | None, params: dict | None):
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                return resp.status, (json.loads(body) if body.startswith(("{", "[")) else body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(body)
            except Exception:
                return exc.code, body

    def get(self, path: str, params: dict | None = None):
        return self._request(path, "GET", None, params)

    def post(self, path: str, payload: dict):
        return self._request(path, "POST", payload, None)

    def close(self) -> None:
        pass


class LocalHttp:
    """In-process TestClient against server.app.main:app (same DB as a local
    `uvicorn server.app.main:app` — the app engine anchors bizro.db to the
    repo root). Lifespan runs, so init_db fires before the first step."""

    def __init__(self):
        from fastapi.testclient import TestClient

        from server.app.main import app

        self._client = TestClient(app)
        self._client.__enter__()  # run lifespan (init_db)

    def get(self, path: str, params: dict | None = None):
        resp = self._client.get(path, params=params)
        return resp.status_code, _maybe_json(resp)

    def post(self, path: str, payload: dict):
        resp = self._client.post(path, json=payload)
        return resp.status_code, _maybe_json(resp)

    def close(self) -> None:
        self._client.__exit__(None, None, None)


# --------------------------------------------------------------------------
# Payload helpers — reuse the simulator's synthetic media (clearly mock-labeled).
# --------------------------------------------------------------------------


def _load_sim():
    try:
        return importlib.import_module("simulate_inbound")
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "bizro_simulate_inbound", Path(__file__).parent / "simulate_inbound.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod


# --------------------------------------------------------------------------
# Demo data seeding — lazy import, same tolerance as dispatch._load_pipeline_fn.
# --------------------------------------------------------------------------


def _seed_demo_data() -> str:
    """Seed ~90 days of karyana history via credit_agent.seed.seed_demo.
    Returns the new merchant id. create_tables=False: the server's models own
    the DDL (seed.py's own docstring rule)."""
    from server.app.config import ensure_repo_root_on_path, get_settings
    from server.app.db import init_db

    ensure_repo_root_on_path()
    init_db()
    try:
        mod = importlib.import_module("credit_agent.seed")
        seed_demo = getattr(mod, "seed_demo", None)
    except ImportError as exc:
        raise StepFailure(
            f"merchants table is empty and credit_agent.seed is not importable ({exc}) — "
            "cannot seed demo data"
        ) from exc
    if seed_demo is None:
        raise StepFailure("credit_agent.seed.seed_demo not found — cannot seed demo data")
    return str(seed_demo(get_settings().database_url, create_tables=False))


def _ensure_demo_data(http, explicit_merchant: str | None) -> dict:
    """Pre-flight: at least one merchant must exist (seed if not), then resolve
    the target merchant (—merchant id, else the first) with its wa_id."""
    status, body = http.get("/api/merchants")
    if status != 200:
        raise StepFailure(f"GET /api/merchants -> HTTP {status}: {body}")
    merchants = body if isinstance(body, list) else []

    if not merchants:
        seeded = _seed_demo_data()
        print(f"     merchants table was empty — seeded demo history (merchant {seeded[:8]}…)")
        status, body = http.get("/api/merchants")
        merchants = body if isinstance(body, list) else []
        if not merchants:
            raise StepFailure(
                "demo seeding did not reach the target server's DB (remote server with its "
                "own DATABASE_URL?). Seed it first or run with --local."
            )

    if explicit_merchant:
        target = next((m for m in merchants if m["id"] == explicit_merchant), None)
        if target is None:
            raise StepFailure(
                f"--merchant {explicit_merchant} not found on the target server "
                f"({len(merchants)} merchant(s) available)"
            )
    else:
        target = merchants[0]
    return target


# --------------------------------------------------------------------------
# Steps — each prints its judge-facing lines, raises StepFailure on breakage.
# --------------------------------------------------------------------------


def _wire_row(http, merchant_id: str, tx_id: str) -> dict:
    """Fetch the §1 wire row for a transaction via the public list endpoint."""
    status, body = http.get(f"/api/merchants/{merchant_id}/transactions")
    if status != 200:
        raise StepFailure(f"GET transactions -> HTTP {status}: {body}")
    for row in body.get("transactions", []):
        if row["id"] == tx_id:
            return row
    raise StepFailure(f"transaction {tx_id} not returned by the list endpoint")


def _webhook(http, sim, wa_id: str, payload: dict) -> dict:
    status, body = http.post("/webhook/whatsapp", payload)
    if status != 200 or not body.get("processed"):
        raise StepFailure(f"POST /webhook/whatsapp -> HTTP {status}: {body}")
    out = body["results"][0]
    if not out.get("ok"):
        raise StepFailure(f"webhook rejected the message: {out}")
    return out


def step_voice_note(http, ctx: dict) -> None:
    """(1) merchant sends an Urdu voice note → pending udhar entry + Urdu
    confirmation with one-tap buttons."""
    sim = ctx["sim"]
    audio = sim.synth_voice_bytes()
    out = _webhook(http, sim, ctx["wa_id"], sim.build_payload(
        ctx["wa_id"], ctx["display_name"],
        base64.b64encode(audio).decode(), "audio/ogg; codecs=opus", None,
    ))
    if not out.get("transaction_id"):
        raise StepFailure(f"voice note produced no transaction: {out}")
    row = _wire_row(http, ctx["merchant_id"], out["transaction_id"])

    print(f"     Merchant sends: 12s Urdu voice note — “Ahmad ko 5 hazar udhar diye”")
    print(f"     Bizro replies (WhatsApp): {out.get('confirmation_ur')}")
    buttons = (out.get("sent") or {}).get("buttons")
    if buttons:
        titles = " ".join(f"[{b['reply']['title']}]" for b in buttons)
        print(f"     One-tap buttons: {titles}  (payloads: confirm / correct)")
    print(f"     Ledger wire row: {row['kind']} PKR {row['amount_pkr']:,.0f} "
          f"status={row['status']} conf={row['source']['confidence']} "
          f"model={row['source']['model']} flag={row['flag']}")
    print("     JUDGE SEES (phone): the Urdu confirmation bubble + درست ہے / بدلیں buttons")
    print("     JUDGE SEES (dashboard): ledger row pending, source=voice, audit drill-down live")
    ctx["voice_tx_id"] = out["transaction_id"]


def step_button_confirm(http, ctx: dict) -> None:
    """(2) merchant taps درست ہے → the pending row flips to confirmed."""
    sim = ctx["sim"]
    out = _webhook(http, sim, ctx["wa_id"], sim.build_payload(
        ctx["wa_id"], ctx["display_name"], None, None, None, button="confirm",
    ))
    tx = out.get("transaction")
    if tx is None:
        raise StepFailure(f"button confirm acted on no transaction: {out}")
    if tx["status"] != "confirmed":
        raise StepFailure(f"button confirm left status={tx['status']}: {out}")
    print(f"     Merchant taps: [درست ہے] → Bizro replies: {out.get('reply')}")
    print(f"     Wire row now: id={tx['id'][:8]}… status={tx['status']} "
          f"confirmation_ur={bool(tx['confirmation_ur'])}")
    print("     JUDGE SEES (phone): “شکریہ! اندراج درست کر دیا گیا۔”")
    print("     JUDGE SEES (dashboard): ledger row pending → confirmed, zero typing")


def step_receipt_photo(http, ctx: dict) -> None:
    """(3) merchant snaps a supplier receipt → OCR expense entry + price flag."""
    sim = ctx["sim"]
    image = sim.synth_receipt_png()
    out = _webhook(http, sim, ctx["wa_id"], sim.build_payload(
        ctx["wa_id"], ctx["display_name"],
        base64.b64encode(image).decode(), "image/png", None,
    ))
    if not out.get("transaction_id"):
        raise StepFailure(f"receipt photo produced no transaction: {out}")
    row = _wire_row(http, ctx["merchant_id"], out["transaction_id"])

    lines = "; ".join(
        f"{l['item']} ×{l['qty']} @ {l['unit_price']}" for l in row["item_lines"]
    ) or "no item lines"
    print(f"     Merchant sends: supplier receipt photo")
    print(f"     Bizro replies (WhatsApp): {out.get('confirmation_ur')}")
    print(f"     OCR expense row: PKR {row['amount_pkr']:,.0f} ({lines})")
    print(f"     FLAG: {row['flag']}  conf={row['source']['confidence']} "
          f"model={row['source']['model']}")
    print("     JUDGE SEES (phone): receipt summary in Urdu, asking for confirmation")
    print("     JUDGE SEES (dashboard): expense entry with flag chip + original photo "
          "(audit trail)")


def _nudge_from_wire_rows(merchant_id: str, rows: list[dict]) -> dict:
    """compute_weekly_nudge over rows fetched via HTTP: rebuild a throwaway
    in-memory transactions table and run the REAL nudge math on it (single
    source of truth — no re-implementation), so the step works identically
    against a remote server."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from server.app.db import Transaction as TxModel
    from server.app.nudges import compute_weekly_nudge

    engine = create_engine("sqlite:///:memory:")
    TxModel.__table__.create(engine)
    make = sessionmaker(bind=engine)
    mid = uuid.UUID(merchant_id)
    with make() as s:
        for r in rows:
            when = datetime.fromisoformat(str(r["occurred_at"]).replace("Z", "+00:00"))
            if when.tzinfo is None:  # SQLite round-trips drop tz; stored times are UTC
                when = when.replace(tzinfo=timezone.utc)
            s.add(TxModel(id=uuid.UUID(r["id"]), merchant_id=mid, kind=r["kind"],
                          amount_pkr=r["amount_pkr"], occurred_at=when,
                          source_type=r["source"]["type"], status=r["status"]))
        s.commit()
        return compute_weekly_nudge(s, mid)


def step_weekly_nudge(http, ctx: dict) -> None:
    """(4) the Friday nudge the merchant receives (send_nudges.py path)."""
    status, body = http.get(f"/api/merchants/{ctx['merchant_id']}/transactions")
    if status != 200:
        raise StepFailure(f"GET transactions -> HTTP {status}: {body}")
    nudge = _nudge_from_wire_rows(ctx["merchant_id"], body.get("transactions", []))
    if not nudge.get("text_ur"):
        raise StepFailure("weekly nudge produced no text")
    print(f"     WhatsApp message (Friday nudge): {nudge['text_ur']}")
    st = nudge["stats"]
    print(f"     Stats: sales_this_week=PKR {st['sales_this_week']:,.0f}, "
          f"expenses=PKR {st['expenses_this_week']:,.0f}, "
          f"udhar_outstanding=PKR {st['udhar_outstanding']:,.0f}, "
          f"streak={st['streak_weeks']}w")
    print("     JUDGE SEES (phone): the weekly Urdu financial summary, no typing anywhere")


def step_report_preview(http, ctx: dict) -> None:
    """(5) credit readiness report → score + band (the loan-officer view)."""
    status, body = http.get(f"/api/merchants/{ctx['merchant_id']}/report/preview")
    if status != 200:
        raise StepFailure(f"GET report/preview -> HTTP {status}: {body}")
    report = body.get("report") or {}
    readiness = report.get("readiness")
    if isinstance(readiness, dict):
        score, band = readiness.get("score"), readiness.get("band")
    else:  # server-fallback reports store a bare band string
        score, band = None, readiness
    if not band:
        raise StepFailure(f"report preview has no readiness band: {report}")
    print(f"     Readiness: score={score} band={band} "
          f"(cached={body.get('cached')}, generated_at={body.get('created_at')})")
    if report.get("mock"):
        print("     ⚠ report carries the mock marker — dashboard shows the MOCK DATA banner")
    print("     JUDGE SEES (dashboard): Credit tab — readiness score, band, trend sparkline, "
          "line items with audit fields")


def step_streak(http, ctx: dict) -> None:
    """(6) savings streak chip."""
    status, body = http.get(f"/api/merchants/{ctx['merchant_id']}/streak")
    if status != 200:
        raise StepFailure(f"GET streak -> HTTP {status}: {body}")
    for key in ("streak_weeks", "best_streak_weeks", "current_week_positive"):
        if key not in body:
            raise StepFailure(f"streak response missing {key}: {body}")
    print(f"     Streak: {body['streak_weeks']} week(s) running "
          f"(best {body['best_streak_weeks']}, current week positive: "
          f"{body['current_week_positive']})")
    print("     JUDGE SEES (dashboard): ledger hero streak chip — “لگاتار N ہفتے”")


STEPS: list[tuple[str, Callable[[Any, dict], None]]] = [
    ("Voice note (udhar) → pending entry + Urdu confirmation", step_voice_note),
    ("One-tap button confirm → wire row flips to confirmed", step_button_confirm),
    ("Receipt photo → OCR expense entry + price flag", step_receipt_photo),
    ("Weekly Urdu nudge", step_weekly_nudge),
    ("Credit report preview → score + band", step_report_preview),
    ("Savings streak", step_streak),
]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def _detect_remote(base_url: str, timeout: float = 2.0) -> tuple[bool, dict | None]:
    """Is a server already running at base_url? Returns (up, health-body)."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
            return resp.status == 200, body
    except Exception:
        return False, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--merchant", default=None, help="target merchant uuid (default: first)")
    parser.add_argument("--wa-id", default=None, help="target merchant wa_id (required for non-demo merchants — the public merchants endpoint hides real numbers)")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"server base URL (default {DEFAULT_URL})")
    parser.add_argument("--local", action="store_true",
                        help="force the in-process TestClient (ignore a running :8000)")
    args = parser.parse_args(argv)

    try:  # Urdu on Windows pipes (cp1252) must not crash a recording session;
          # line buffering keeps prints interleaved with server logs in order
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

    if args.local:
        print(f"Bizro demo flow — IN-PROCESS mode (no server needed, same DB as uvicorn)")
        http, health = LocalHttp(), None
    else:
        up, health = _detect_remote(args.url)
        if up:
            print(f"Bizro demo flow — driving the RUNNING server at {args.url}")
            http = RemoteHttp(args.url)
        else:
            if args.url != DEFAULT_URL:
                print(f"FAILED: no server at {args.url} (pass --local for in-process mode)")
                return 1
            print(f"Bizro demo flow — no server at {args.url}, spinning TestClient in-process")
            http, health = LocalHttp(), None

    dashscope_mode = "mock"
    if health:
        dashscope_mode = (health.get("integrations", {}).get("dashscope", {}).get("mode")
                          or "mock")
    else:
        try:
            from server.app import dashscope_client

            dashscope_mode = "live" if dashscope_client.is_live() else "mock"
        except Exception:
            dashscope_mode = "mock"
    timing_label = LIVE_TIMING_LABEL if dashscope_mode == "live" else MOCK_TIMING_LABEL
    print(f"DashScope: {dashscope_mode} — {timing_label}\n")

    sim = _load_sim()
    failures = 0
    total_ms = 0.0
    started = time.perf_counter()
    try:
        target = _ensure_demo_data(http, args.merchant)
        # The public merchants endpoint no longer exposes wa_id (privacy,
        # D6-6) — the seeded demo stores have fixed known wa_ids; anything
        # else falls back to the store's display name as the sender id.
        KNOWN_WA = {
            "Al-Madina Kiryana Store": "923009999888",
            "Bilal Ki Dukan": "923009111222",
        }
        ctx = {
            "merchant_id": target["id"],
            "wa_id": args.wa_id or target.get("wa_id") or KNOWN_WA.get(target.get("display_name") or "", target["id"]),
            "display_name": target.get("display_name") or target["wa_id"],
            "sim": sim,
        }
        print(f"Merchant: {ctx['display_name']} ({target['id']}) wa_id={ctx['wa_id']}\n")

        for n, (title, fn) in enumerate(STEPS, 1):
            print(f"[{n}/{len(STEPS)}] {title}")
            t0 = time.perf_counter()
            try:
                fn(http, ctx)
            except StepFailure as exc:
                print(f"     FAILED: {exc}")
                failures += 1
                break
            except Exception as exc:  # never let a demo step die silently
                print(f"     FAILED (unexpected {type(exc).__name__}): {exc}")
                failures += 1
                break
            ms = (time.perf_counter() - t0) * 1000
            total_ms += ms
            print(f"     ⏱ {ms:,.0f} ms ({timing_label})\n")
    except Exception as exc:  # setup failures (backend, seeding, merchant resolution)
        print(f"SETUP FAILED ({type(exc).__name__}): {exc}")
        failures += 1
    finally:
        http.close()

    if failures:
        print(f"DEMO FLOW FAILED after {time.perf_counter() - started:,.1f}s — fix the step above")
        return 1
    print(f"ALL {len(STEPS)} STEPS OK — total {time.perf_counter() - started:,.1f}s "
          f"(steps {total_ms:,.0f} ms) ({timing_label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
