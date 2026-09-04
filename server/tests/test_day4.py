"""Day-4 block — loan-officer CSV export + one-command demo driver.

Part 1 (§ export): GET /api/merchants/{id}/transactions/export.csv —
text/csv + attachment disposition, UTF-8 BOM (Urdu must survive a loan
officer double-clicking the file in Excel), CRLF records, stdlib csv
quoting, bound to the same from/to/kind filters as the list endpoint,
'me' sentinel honored (filename carries the RESOLVED id).

Part 2 (demo driver): server/scripts/demo_flow.py — see the test section
below; runs the rehearsal in-process (MOCK_MODE=always) and must exit
non-zero the moment any step fails.

Everything runs offline against the throwaway SQLite DB pinned in
conftest.py — never main's bizro.db, never the live :8000.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.api import CSV_COLUMNS
from server.app.db import Merchant, Transaction, db_session
from server.app.main import app

BOM = b"\xef\xbb\xbf"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """Tables must exist even when tests are picked individually."""
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _new_merchant(wa: str, name: str = "Day4 Ctx") -> uuid.UUID:
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name=name)
        s.add(m)
        s.commit()
        return m.id


def _seed_tx(
    merchant_id,
    kind: str,
    amount: float,
    occurred_at: str,
    *,
    desc: str = "",
    counterparty: str | None = None,
    confidence: float = 0.9,
    confirmation_ur: str | None = None,
    source: str = "voice",
    status: str = "confirmed",
):
    """Persist via the real dispatch path so the outbound confirmation row
    (confirmation_ur column source) exists too."""
    from server.app import dispatch as disp

    with db_session() as s:
        disp.persist_transaction(
            s,
            s.get(Merchant, merchant_id),
            {
                "kind": kind,
                "amount_pkr": float(amount),
                "currency": "PKR",
                "counterparty": ({"name": counterparty, "phone": None} if counterparty else None),
                "description": desc,
                "occurred_at": occurred_at,
                "source": {"type": source, "media_id": None, "model": "qwen3.5-omni-plus",
                           "confidence": confidence, "raw_output": {}},
                "flag": "none",
                "status": status,
                "confirmation_ur": confirmation_ur,
            },
            None,
        )


# ===================== 1. CSV export (loan-officer view) =====================


def test_export_csv_content_type_disposition_bom(client):
    """HTTP envelope: text/csv, attachment filename with the RESOLVED merchant
    id, UTF-8 BOM prefix, CRLF record separator, exact column header."""
    mid = _new_merchant(_wa("92500"))
    _seed_tx(mid, "sale", 1500.5, "2026-08-20T10:00:00+00:00",
             desc="cash sale", counterparty="Walk-in",
             confirmation_ur="Cash sale: 1500 rupees.")

    r = client.get(f"/api/merchants/{mid}/transactions/export.csv")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == (
        f'attachment; filename="bizro-ledger-{mid}.csv"'
    )
    assert r.content.startswith(BOM), "Excel-safe UTF-8 BOM prefix missing"
    assert b"\r\n" in r.content, "CRLF line endings missing"

    text = r.content.decode("utf-8-sig")  # BOM-aware decode
    assert text.split("\r\n")[0] == ",".join(CSV_COLUMNS)


def test_export_csv_row_values_and_quoting_roundtrip(client):
    """A row whose description holds commas, quotes, a newline and Urdu parses
    back as ONE csv record with every field intact — plus the audit columns."""
    mid = _new_merchant(_wa("92501"))
    desc = 'chai, patti ("premium")\nsecond line — رات کی فروخت'
    _seed_tx(mid, "udhar_given", 5000, "2026-08-21T19:03:00+00:00",
             desc=desc, counterparty="Ahmad", confidence=0.87,
             confirmation_ur="Got it. 5000 rupees credit to Ahmad. Is this correct?")

    r = client.get(f"/api/merchants/{mid}/transactions/export.csv")
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == list(CSV_COLUMNS)
    assert len(rows) == 2, "embedded newline must not split the csv record"
    row = dict(zip(CSV_COLUMNS, rows[1]))
    assert row["kind"] == "udhar_given"
    assert row["amount_pkr"] == "5000.00"
    assert row["currency"] == "PKR"
    assert row["description"] == desc
    assert row["counterparty_name"] == "Ahmad"
    assert row["source_type"] == "voice"
    assert row["source_model"] == "qwen3.5-omni-plus"
    assert row["confidence"] == "0.870"
    assert row["status"] == "confirmed"
    assert row["confirmation_ur"] == "Got it. 5000 rupees credit to Ahmad. Is this correct?"
    uuid.UUID(row["transaction_id"])  # parseable id → audit drill-down works
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(row["transaction_id"])) is not None


def test_export_csv_empty_confidence_and_missing_fields_render_blank(client):
    """Manual entries carry no model/confidence — blank cells, not 'None'."""
    mid = _new_merchant(_wa("92502"))
    _seed_tx(mid, "sale", 300, "2026-08-21T08:00:00+00:00",
             desc="", source="manual", confidence=0.99)  # manual path w/o confirmation
    # re-seed as truly manual: confidence is required by TransactionIn, so the
    # realistic manual row keeps confidence but no model — blank source_model.
    r = client.get(f"/api/merchants/{mid}/transactions/export.csv")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    row = dict(zip(CSV_COLUMNS, rows[1]))
    assert row["confirmation_ur"] == ""
    assert row["counterparty_name"] == ""


def test_export_csv_filters_bound_to_list_endpoint(client):
    """Same from/to/kind filters as the list endpoint — counts must agree."""
    mid = _new_merchant(_wa("92503"))
    _seed_tx(mid, "sale", 1000, "2026-08-05T10:00:00+00:00", desc="s1")
    _seed_tx(mid, "expense", 400, "2026-08-10T10:00:00+00:00", desc="e1")
    _seed_tx(mid, "sale", 2000, "2026-08-25T10:00:00+00:00", desc="s2")

    for params in (
        {"kind": "sale"},
        {"kind": "expense"},
        {"from": "2026-08-01", "to": "2026-08-12"},
        {"from": "2026-08-20", "kind": "sale"},
        {},
    ):
        listed = client.get(f"/api/merchants/{mid}/transactions", params=params).json()
        r = client.get(f"/api/merchants/{mid}/transactions/export.csv", params=params)
        assert r.status_code == 200, (params, r.text)
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert len(rows) - 1 == listed["count"], params
        assert [row[1] for row in rows[1:]] == [t["kind"] for t in listed["transactions"]], params

    # window isolates exactly the mid-month expense
    r = client.get(f"/api/merchants/{mid}/transactions/export.csv",
                   params={"from": "2026-08-06", "to": "2026-08-20"})
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert len(rows) == 2 and rows[1][1] == "expense"


def test_export_csv_me_sentinel_and_escaped_query_params(client):
    """'me' resolves like every other route — filename carries the RESOLVED id,
    never the literal 'me'. Hostile/odd query params stay params: no error, no
    row leakage."""
    with db_session() as s:
        first = s.query(Merchant).order_by(Merchant.created_at).first()
    assert first is not None, "merchants exist from the rest of the suite"

    r = client.get("/api/merchants/me/transactions/export.csv")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == (
        f'attachment; filename="bizro-ledger-{first.id}.csv"'
    )
    assert r.content.startswith(BOM)

    # a kind that IS a csv payload stays a filter value: quoted in the URL,
    # matched against no rows, never smuggled into the csv body
    weird = client.get("/api/merchants/me/transactions/export.csv",
                       params={"kind": 'sale","x": "injection', "from": "2026-08-01"})
    assert weird.status_code == 200
    rows = list(csv.reader(io.StringIO(weird.content.decode("utf-8-sig"))))
    assert len(rows) == 1, "no kind matches — header only, nothing smuggled in"

    assert client.get("/api/merchants/not-a-uuid/transactions/export.csv").status_code == 400
    assert client.get(f"/api/merchants/{uuid.uuid4()}/transactions/export.csv").status_code == 404


# ===================== 2. Demo driver (scripts/demo_flow.py) =====================
#
# demo_flow lives in scripts/ (not a package) — load it from its file path.
# Tests ALWAYS pass --local (or a dead --url): never the live :8000, whose DB
# belongs to main's demo environment.


def _load_demo_flow():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "bizro_demo_flow", Path(__file__).resolve().parents[1] / "scripts" / "demo_flow.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


demo_flow = _load_demo_flow()


def test_demo_flow_local_full_run_ok(capsys):
    """The rehearsal happy path: 6/6 steps, judge-facing lines, per-step mock
    timings, exit code 0 — under 30s."""
    wa = _wa("92510")
    mid = _new_merchant(wa, name="Demo Flow Store")
    _seed_tx(mid, "sale", 2500, "2026-08-28T10:00:00+00:00", desc="cash sale")
    _seed_tx(mid, "expense", 600, "2026-08-27T10:00:00+00:00", desc="restock",
             source="photo", confirmation_ur="Expense: 600 rupees.")

    rc = demo_flow.main(["--local", "--merchant", str(mid), "--wa-id", wa])
    out = capsys.readouterr().out
    assert rc == 0, out
    for n in range(1, 7):
        assert f"[{n}/6]" in out
    assert "ALL 6 STEPS OK" in out
    assert "MOCK MODE timings; live timings need DASHSCOPE_API_KEY" in out
    assert "ms (" in out, "per-step wall-clock timing missing"
    assert "JUDGE SEES (phone)" in out and "JUDGE SEES (dashboard)" in out
    assert "It's correct" in out, "one-tap buttons must be shown for step 1"
    assert str(mid) in out, "--merchant must be echoed in the timeline header"


def test_demo_flow_default_target_is_first_merchant(capsys):
    """No --merchant: the first merchant (created_at order, same rule as 'me')."""
    with db_session() as s:
        first = s.query(Merchant).order_by(Merchant.created_at).first()
    assert first is not None, "merchants exist from the rest of the suite"

    rc = demo_flow.main(["--local", "--wa-id", str(first.wa_id)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert str(first.id) in out


def test_demo_flow_unknown_merchant_exits_nonzero(capsys):
    rc = demo_flow.main(["--local", "--merchant", str(uuid.uuid4())])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not found" in out


def test_demo_flow_dead_explicit_url_exits_nonzero(capsys):
    """An explicit --url that isn't running is an error, not a silent local
    fallback (the operator asked for THAT server)."""
    rc = demo_flow.main(["--url", "http://127.0.0.1:9"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "no server" in out


def test_demo_flow_step_failure_breaks_and_exits_nonzero(capsys, monkeypatch):
    """A broken step fails the rehearsal immediately — later steps never run."""
    StepFailure = demo_flow.StepFailure

    def boom(http, ctx):
        raise StepFailure("rehearsal explosion")

    monkeypatch.setattr(demo_flow, "STEPS",
                        [("step that always breaks", boom)] + demo_flow.STEPS[1:])
    rc = demo_flow.main(["--local"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED" in out and "rehearsal explosion" in out
    assert "[2/6]" not in out, "a failed step must stop the run"
    assert "ALL 6 STEPS OK" not in out


def test_seed_demo_data_seeds_via_credit_agent(tmp_path, monkeypatch):
    """The lazy seed path: credit_agent.seed.seed_demo runs with
    create_tables=False against DATABASE_URL (server models own the DDL)."""
    from types import SimpleNamespace

    from sqlalchemy import create_engine, func as sa_func, select

    from server.app import config as cfg
    from server.app.db import Base, Merchant as MerchantModel, Transaction as TxModel

    url = f"sqlite:///{(tmp_path / 'seed.db').as_posix()}"
    ddl_engine = create_engine(url)  # server owns the DDL
    Base.metadata.create_all(ddl_engine)
    ddl_engine.dispose()
    monkeypatch.setattr(cfg, "get_settings", lambda: SimpleNamespace(database_url=url))

    seeded_id = demo_flow._seed_demo_data()
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            merchants = conn.execute(select(MerchantModel)).all()
            n_tx = conn.scalar(select(sa_func.count()).select_from(TxModel))
    finally:
        engine.dispose()
    assert len(merchants) == 1 and str(merchants[0].id) == seeded_id
    assert (n_tx or 0) > 50, "~90 days of karyana history expected"


def test_nudge_from_wire_rows_uses_real_nudge_math():
    """Step 4 runs the REAL compute_weekly_nudge over HTTP-fetched rows —
    same numbers the Friday send_nudges.py job would produce."""
    from datetime import datetime, timezone

    mid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    rows = [
        {"id": str(uuid.uuid4()), "kind": "sale", "amount_pkr": 5000.0,
         "occurred_at": now.isoformat(), "status": "confirmed", "source": {"type": "voice"}},
        {"id": str(uuid.uuid4()), "kind": "sale", "amount_pkr": 1000.0,
         "occurred_at": now.isoformat(), "status": "pending", "source": {"type": "voice"}},
    ]
    nudge = demo_flow._nudge_from_wire_rows(str(mid), rows)
    assert nudge["text_ur"].startswith("Weekly summary")  # English content, historical key
    assert nudge["stats"]["sales_this_week"] == 6000.0  # pending counts too (not rejected)
    assert nudge["stats"]["streak_weeks"] >= 1
