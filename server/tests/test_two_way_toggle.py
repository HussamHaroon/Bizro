"""Two-way toggle (owner ruling 2026-09-07) — server truth for the officer flag.

`two_way_confirmation_required` is a per-merchant setting DEFAULT OFF; only
the officer flips it. OFF = today's rubric byte-identical (the scoring side
lives in credit-agent/tests/test_two_way_toggle.py). Contract under test:

- GET implies False (missing row AND stored row without the flag set).
- PUT true → GET true; PUT false alone is a valid save (False survives the
  explicit-null filter — it must never read as "nothing provided").
- Partial PUTs preserve the flag; the flag PUT preserves other settings.
- Unknown keys / non-bool values are 422; nothing persists from a rejected PUT.
- The additive migration backfills existing rows to False (SQLite ALTER path).

Runs offline against the throwaway SQLite DB pinned in conftest.py.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, db_session
from server.app.main import app


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


def _new_merchant(prefix: str, name: str = "Two Way Ctx") -> uuid.UUID:
    with db_session() as s:
        m = Merchant(wa_id=f"{prefix}{uuid.uuid4().hex[:8]}", display_name=name)
        s.add(m)
        s.commit()
        return m.id


# ===================== defaults: OFF everywhere until the officer speaks =====


def test_get_missing_row_implies_two_way_off(client):
    """No settings row → the implied defaults carry the flag OFF (a merchant
    who never touched settings can never be scored under two-way)."""
    mid = _new_merchant("92560")
    r = client.get(f"/api/merchants/{mid}/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["two_way_confirmation_required"] is False


def test_default_false_for_existing_rows(client):
    """A row saved before the flag existed (or without it) reads OFF — the
    NOT NULL DEFAULT FALSE backfill, observed through the API."""
    mid = _new_merchant("92561")
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur"})
    assert r.status_code == 200, r.text
    assert r.json()["two_way_confirmation_required"] is False, (
        "saving unrelated settings must not turn the flag on"
    )
    assert client.get(f"/api/merchants/{mid}/settings").json()[
        "two_way_confirmation_required"
    ] is False


# ===================== officer flip: PUT → GET roundtrip =====================


def test_put_true_then_get_true_roundtrip(client):
    """The officer flips the flag: PUT true persists, GET returns true, and
    the roundtrip through a fresh request carries it."""
    mid = _new_merchant("92562")
    r = client.put(f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["two_way_confirmation_required"] is True
    assert body["updated_at"] is not None and "T" in body["updated_at"]

    got = client.get(f"/api/merchants/{mid}/settings").json()
    assert got["two_way_confirmation_required"] is True


def test_put_false_alone_is_a_valid_save(client):
    """False is a real value (flag flipped back off), not 'not provided': the
    explicit-null filter drops None, never False — a False-only PUT must save
    and must not 422 as an empty body."""
    mid = _new_merchant("92563")
    assert client.put(
        f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": True}
    ).json()["two_way_confirmation_required"] is True

    r = client.put(f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": False})
    assert r.status_code == 200, r.text
    assert r.json()["two_way_confirmation_required"] is False
    assert client.get(f"/api/merchants/{mid}/settings").json()[
        "two_way_confirmation_required"
    ] is False


def test_first_save_can_carry_the_flag_with_other_defaults(client):
    """First-ever PUT of only the flag: unset columns take the implied
    defaults (language 'mixed', numeral_style env-mirrored = western)."""
    mid = _new_merchant("92564")
    r = client.put(f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["two_way_confirmation_required"] is True
    assert body["language"] == "mixed"
    assert body["numeral_style"] == "western"


def test_partial_puts_merge_across_fields_both_ways(client):
    """The flag merges like any other setting — and never resets the others."""
    mid = _new_merchant("92565")
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur"})
    assert r.status_code == 200, r.text

    r = client.put(f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["language"] == "ur", "flag PUT must preserve language"
    assert body["two_way_confirmation_required"] is True

    r = client.put(f"/api/merchants/{mid}/settings", json={"numeral_style": "urdu"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["numeral_style"] == "urdu"
    assert body["two_way_confirmation_required"] is True, "unrelated PUT must preserve the flag"


def test_merchants_are_independent(client):
    """One merchant's toggle never leaks into another's row."""
    a, b = _new_merchant("92566", "Shop A"), _new_merchant("92567", "Shop B")
    assert client.put(
        f"/api/merchants/{a}/settings", json={"two_way_confirmation_required": True}
    ).status_code == 200
    assert client.get(f"/api/merchants/{b}/settings").json()[
        "two_way_confirmation_required"
    ] is False
    assert client.get(f"/api/merchants/{a}/settings").json()[
        "two_way_confirmation_required"
    ] is True


# ===================== rejection cases (422, nothing persisted) ==============


def test_put_unknown_key_still_422_with_flag_present(client):
    """extra="forbid" holds after the new field: a typo'd neighbour still
    fails the whole body atomically."""
    mid = _new_merchant("92568")
    r = client.put(
        f"/api/merchants/{mid}/settings",
        json={"two_way_confirmation_required": True, "two_way_confirmation_requied": True},
    )
    assert r.status_code == 422, r.text
    assert client.get(f"/api/merchants/{mid}/settings").json()[
        "two_way_confirmation_required"
    ] is False


def test_put_non_bool_flag_422(client):
    mid = _new_merchant("92569")
    # "yes"/"on"/1 are legitimate pydantic-bool coercions; these are not.
    for bad in ("maybe", "2", 1.5, 2, ["true"]):
        r = client.put(f"/api/merchants/{mid}/settings", json={"two_way_confirmation_required": bad})
        assert r.status_code == 422, r.text
    assert client.get(f"/api/merchants/{mid}/settings").json()["updated_at"] is None


# ===================== additive migration backfill ===========================


def test_additive_alter_backfills_existing_rows_false(monkeypatch, tmp_path):
    """The _ensure_additive_columns path for a PRE-toggle database: a legacy
    merchant_settings without the column gains it via ALTER, and existing rows
    backfill to False (SQLite dialect; same DDL runs on Postgres)."""
    from sqlalchemy import create_engine, text

    from server.app import db as dbmod

    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE outbound_messages (id TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE merchants (id TEXT PRIMARY KEY)"))
        # the ALTER loop inspects transactions unconditionally — a legacy DB
        # has it (with the §11 columns already present, so no ALTERs fire)
        conn.execute(
            text(
                "CREATE TABLE transactions (id TEXT PRIMARY KEY, entry_hash TEXT, "
                "prev_entry_hash TEXT, trust_tier TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE merchant_settings ("
                "merchant_id TEXT PRIMARY KEY, language TEXT, "
                "numeral_style TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO merchant_settings VALUES "
                "('m1', 'ur', 'western', '2026-09-07T00:00:00+00:00')"
            )
        )

    monkeypatch.setattr(dbmod, "engine", eng)
    dbmod._ensure_additive_columns()  # idempotent re-run is the contract

    with eng.begin() as conn:
        rows = conn.execute(
            text("SELECT two_way_confirmation_required FROM merchant_settings")
        ).scalars().all()
    assert [bool(v) for v in rows] == [False], "existing rows must backfill OFF"

    dbmod._ensure_additive_columns()  # second run: no-op, no error
