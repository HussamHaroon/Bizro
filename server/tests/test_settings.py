"""Day-4 block — per-merchant settings API (schema.md §8, ruling D4-2).

GET/PUT /api/merchants/{id}/settings: settings persist server-side (each
merchant IS an account) so they follow the user across browsers/devices.
Contract under test:

- GET with no stored row → implied defaults, 200 (never 404), updated_at null;
  the implied numeral_style mirrors the NUMERAL_STYLE env at first read.
- PUT with a partial body upserts and returns the merged row with a fresh
  updated_at; unknown keys / bad enums / empty body are 422.
- 'me' sentinel honored; merchants are independent.

Runs offline against the throwaway SQLite DB pinned in conftest.py.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

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


def _new_merchant(prefix: str, name: str = "Settings Ctx") -> uuid.UUID:
    with db_session() as s:
        m = Merchant(wa_id=f"{prefix}{uuid.uuid4().hex[:8]}", display_name=name)
        s.add(m)
        s.commit()
        return m.id


# ===================== GET: implied defaults =====================


def test_get_missing_row_returns_implied_defaults(client):
    """No settings saved yet → 200 with language 'mixed', numeral_style
    'western' (NUMERAL_STYLE unset in tests), updated_at null — not 404."""
    mid = _new_merchant("92550")
    r = client.get(f"/api/merchants/{mid}/settings")
    assert r.status_code == 200, r.text
    assert r.json() == {"language": "mixed", "numeral_style": "western", "updated_at": None}


def test_get_default_numeral_style_mirrors_env(client, monkeypatch):
    """§8: the implied numeral_style mirrors the NUMERAL_STYLE env — and a
    mis-set env value never leaks past the enum."""
    import server.app.api as api

    mid = _new_merchant("92551")
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(numeral_style="urdu"))
    r = client.get(f"/api/merchants/{mid}/settings")
    assert r.status_code == 200
    assert r.json()["numeral_style"] == "urdu"
    assert r.json()["updated_at"] is None

    # first PUT of only language persists the env-derived numeral_style
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur"})
    assert r.status_code == 200, r.text
    assert r.json()["language"] == "ur"
    assert r.json()["numeral_style"] == "urdu", "env default must materialize on first save"
    assert r.json()["updated_at"] is not None

    # env drift after a row exists must NOT rewrite the saved value
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(numeral_style="western"))
    r = client.get(f"/api/merchants/{mid}/settings")
    assert r.json()["numeral_style"] == "urdu", "per-merchant value wins after first save"


# ===================== PUT: upsert + merge =====================


def test_put_then_get_roundtrip(client):
    """Full-body PUT stores both settings; GET returns them with the stored
    updated_at (non-null, ISO-8601)."""
    mid = _new_merchant("92552")
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "en", "numeral_style": "urdu"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["language"] == "en" and body["numeral_style"] == "urdu"
    assert body["updated_at"] is not None and "T" in body["updated_at"]

    got = client.get(f"/api/merchants/{mid}/settings").json()
    assert got == body


def test_partial_put_preserves_the_other_setting(client):
    """Partial body ({"language": "ur"} is valid per §8): a later PUT of
    numeral_style must not reset language."""
    mid = _new_merchant("92553")
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["language"] == "ur"
    assert body["numeral_style"] == "western", "unset column takes the implied default"

    r = client.put(f"/api/merchants/{mid}/settings", json={"numeral_style": "urdu"})
    assert r.status_code == 200, r.text
    assert r.json()["language"] == "ur", "partial PUT must preserve unset keys"
    assert r.json()["numeral_style"] == "urdu"


def test_put_refreshes_updated_at(client):
    """Every save stamps a fresh updated_at (write-through clock)."""
    mid = _new_merchant("92554")
    first = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur"}).json()
    second = client.put(f"/api/merchants/{mid}/settings", json={"language": "en"}).json()
    assert second["updated_at"] >= first["updated_at"]


# ===================== PUT: rejection cases (all 422) =====================


def test_put_invalid_enum_422(client):
    mid = _new_merchant("92555")
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "french"})
    assert r.status_code == 422, r.text
    r = client.put(f"/api/merchants/{mid}/settings", json={"numeral_style": "roman"})
    assert r.status_code == 422, r.text
    # nothing may have been persisted by a rejected PUT
    assert client.get(f"/api/merchants/{mid}/settings").json()["updated_at"] is None


def test_put_unknown_key_422(client):
    """extra="forbid": a typo'd field (dashboard write-through bug) is loud."""
    mid = _new_merchant("92556")
    r = client.put(f"/api/merchants/{mid}/settings", json={"theme": "dark"})
    assert r.status_code == 422, r.text
    # a VALID key riding along with an unknown one still fails atomically
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": "ur", "theme": "dark"})
    assert r.status_code == 422, r.text
    assert client.get(f"/api/merchants/{mid}/settings").json()["language"] == "mixed"


def test_put_empty_body_422(client):
    mid = _new_merchant("92557")
    r = client.put(f"/api/merchants/{mid}/settings", json={})
    assert r.status_code == 422, r.text
    assert "no settings provided" in r.text
    # explicit nulls are "not provided" too — never a 500 on the NOT NULL columns
    r = client.put(f"/api/merchants/{mid}/settings", json={"language": None})
    assert r.status_code == 422, r.text
    assert "no settings provided" in r.text


# ===================== 'me' sentinel + independence =====================


def test_me_sentinel_roundtrip(client):
    """'me' (first merchant, ruling D1-2) reads and writes the same row — a
    PUT via 'me' is visible under the resolved merchant id."""
    with db_session() as s:
        first = s.query(Merchant).order_by(Merchant.created_at).first()
    assert first is not None, "merchants exist from the rest of the suite"

    r = client.get("/api/merchants/me/settings")
    assert r.status_code == 200, r.text
    before = r.json()

    r = client.put("/api/merchants/me/settings", json={"language": "en"})
    assert r.status_code == 200, r.text

    got = client.get(f"/api/merchants/{first.id}/settings").json()
    assert got["language"] == "en", "PUT via 'me' must land on the resolved merchant"

    # restore so 'me'-dependent assertions elsewhere in the suite stay stable
    client.put("/api/merchants/me/settings", json={"language": before["language"]})


def test_second_merchant_settings_independent(client):
    """Each merchant IS an account: one merchant's save never leaks defaults
    or values into another's row."""
    a, b = _new_merchant("92558", "Shop A"), _new_merchant("92559", "Shop B")

    r = client.put(f"/api/merchants/{a}/settings", json={"language": "ur"})
    assert r.status_code == 200, r.text

    # B still reads its own implied defaults (updated_at null)
    got_b = client.get(f"/api/merchants/{b}/settings").json()
    assert got_b == {"language": "mixed", "numeral_style": "western", "updated_at": None}

    r = client.put(f"/api/merchants/{b}/settings", json={"language": "en", "numeral_style": "urdu"})
    assert r.status_code == 200, r.text

    got_a = client.get(f"/api/merchants/{a}/settings").json()
    assert got_a["language"] == "ur" and got_a["numeral_style"] == "western"

    got_b_after = client.get(f"/api/merchants/{b}/settings").json()
    assert got_b_after["language"] == "en" and got_b_after["numeral_style"] == "urdu"


def test_settings_unknown_merchant_404_and_bad_id_400(client):
    assert client.get(f"/api/merchants/{uuid.uuid4()}/settings").status_code == 404
    assert client.get("/api/merchants/not-a-uuid/settings").status_code == 400
    assert client.put(f"/api/merchants/{uuid.uuid4()}/settings", json={"language": "ur"}).status_code == 404
