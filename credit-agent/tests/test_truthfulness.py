"""Truthfulness regression tests — red-team audit of the LIVE /credit screen
(2026-09-04). Each of the four defects is pinned by a test (bizro-testability:
offline, deterministic, no keys, frozen timestamps):

1. Month count, header range and the month list that drives the bars must all
   derive from ONE computation over the actual transaction occurred_at months
   (live: headline said "three months" next to "Months of records 4").
2. Every flag must carry refs (transaction ids) to the entries it flags — or a
   short honest reason; never an untraceable "0 refs".
3. No user-visible surface prints raw ISO timestamps: "Sep 3, 2026, 7:51 pm"
   for datetimes, "Jun 6, 2026 - Sep 1, 2026" for ranges.
4. Footer attribution names the model id ACTUALLY used (env MODEL_REASONING)
   and the provider derived at runtime from the DASHSCOPE_BASE_URL host —
   "Alibaba Cloud Model Studio" is claimed only when the host actually is one.
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.db_view import Base, Merchant, Transaction, get_sessionmaker
from credit_agent.formatting import (
    PKT,
    format_date_label,
    format_datetime_label,
    format_range_label,
    provider_from_base_url,
)
from credit_agent.render import render_report_html
from credit_agent.report import generate_report

# Fixed, frozen timestamps spanning exactly four PKT months — the audit's
# live shape (Jun 6 -> Sep 1 header over four bars).
MOMENTS_4_MONTHS = [
    datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
    datetime(2026, 6, 20, 14, 30, tzinfo=timezone.utc),
    datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    datetime(2026, 8, 20, 8, 45, tzinfo=timezone.utc),
    datetime(2026, 9, 1, 5, 10, tzinfo=timezone.utc),
]

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATETIME_LABEL = re.compile(r"[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [ap]m")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """No key anywhere: the narrative stays the deterministic template and the
    report is mock-marked (D0-3) — tests never touch the network."""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)


def _db(tmp_path, name="t.db"):
    url = f"sqlite:///{tmp_path / name}"
    from sqlalchemy import create_engine
    Base.metadata.create_all(create_engine(url))
    return url


def _merchant(session, name="Truth Store"):
    m = Merchant(id=uuid.uuid4(), wa_id="wa", display_name=name)
    session.add(m)
    session.commit()
    return m.id


def _tx(session, mid, when, kind="sale", amount=1000.0, flag="none",
        status="confirmed", source="voice", conf=0.9):
    tx = Transaction(
        id=uuid.uuid4(), merchant_id=mid, customer_id=None, kind=kind,
        amount_pkr=amount, description=f"{kind} entry", occurred_at=when,
        source_type=source,
        source_media_id=uuid.uuid4() if source != "manual" else None,
        source_model="mock-model" if source != "manual" else None,
        confidence=conf if source != "manual" else None,
        flag=flag, status=status,
    )
    session.add(tx)
    return tx.id


def _seed(tmp_path, moments=MOMENTS_4_MONTHS, flag_every=None, name="t.db"):
    """Returns (db_url, merchant_id, flagged_ids). flag_every: set of indexes
    into moments that get a price_anomaly flag."""
    url = _db(tmp_path, name)
    Session = get_sessionmaker(url)
    flagged: list[str] = []
    with Session() as s:
        mid = _merchant(s)
        for i, when in enumerate(moments):
            is_flagged = flag_every is not None and i in flag_every
            tid = _tx(
                s, mid, when,
                kind="expense" if is_flagged else "sale",
                flag="price_anomaly" if is_flagged else "none",
                conf=0.6 if is_flagged else 0.9,
            )
            if is_flagged:
                flagged.append(str(tid))
        s.commit()
    return url, mid, flagged


# --- defect 1: ONE month computation feeds count, range and month list --------


def test_month_count_header_range_and_month_list_are_one_computation(tmp_path):
    url, mid, _ = _seed(tmp_path)
    report = generate_report(mid, period="all", db_url=url)
    period = report["period"]

    # The single source: distinct PKT months of the ACTUAL occurred_at values
    # (computed independently here with stdlib only).
    expected_months = sorted({w.astimezone(PKT).strftime("%Y-%m") for w in MOMENTS_4_MONTHS})
    assert period["months"] == expected_months
    assert period["months_count"] == len(period["months"]) == 4

    # The months metric (the consistency card's number) is the SAME computation.
    months_metric = next(m for m in report["metrics"] if m["key"] == "months")
    assert months_metric["value"] == period["months_count"]
    assert months_metric["display"] == str(period["months_count"])

    # The header range labels are the formatted min/max of the SAME rows, so
    # they always start inside months[0] and end inside months[-1].
    assert period["label"] == f"{period['start_display']} - {period['end_display']}"
    assert period["start_display"] == format_date_label(min(MOMENTS_4_MONTHS))
    assert period["end_display"] == format_date_label(max(MOMENTS_4_MONTHS))
    assert period["label"] == "Jun 6, 2026 - Sep 1, 2026"

    # The (mock) narrative states the SAME month count — no "three months"
    # prose next to a four-month record.
    assert "cover 4 months" in report["narrative_ur"]

    # And the printable HTML shows the formatted range, never raw ISO.
    html = render_report_html(report)
    assert period["label"] in html
    assert not ISO_DATE.search(html)


def test_empty_history_months_are_zero_and_say_so(tmp_path):
    url = _db(tmp_path, "empty.db")
    Session = get_sessionmaker(url)
    with Session() as s:
        mid = _merchant(s)
    report = generate_report(mid, period="all", db_url=url)
    assert report["period"]["months"] == []
    assert report["period"]["months_count"] == 0
    months_metric = next(m for m in report["metrics"] if m["key"] == "months")
    assert months_metric["display"] == "0"
    assert "cover 0 months" in report["narrative_ur"]  # honest, never invented


# --- defect 2: every flag is traceable to the entries it flags ----------------


def test_every_flag_carries_refs_to_flagged_entries(tmp_path):
    url, mid, flagged_ids = _seed(tmp_path, flag_every={1, 3}, name="f.db")
    report = generate_report(mid, period="all", db_url=url)
    pf = next(f for f in report["red_flags"] if f["flag"] == "price_anomaly")
    assert pf["count"] == len(pf["refs"]) == 2
    assert sorted(pf["refs"]) == sorted(flagged_ids)
    assert "refs_reason" not in pf  # a reason is only for the impossible case

    html = render_report_html(report)
    assert "0 refs" not in html
    for tid in flagged_ids:
        assert tid in html  # the printed artifact links the flag to its entries


def test_render_prints_honest_reason_when_refs_cannot_exist():
    report = {
        "merchant": {"name": "X"},
        "period": {"start": "2026-06-06", "end": "2026-09-01",
                   "label": "Jun 6, 2026 - Sep 1, 2026"},
        "readiness": {"band": "nearly", "score": 60},
        "red_flags": [{
            "flag": "price_anomaly", "count": 2, "refs": [],
            "refs_reason": "the flagged entry ids were not stored with this report",
            "note_en": "2 entries flagged price_anomaly", "note_ur": "2 اندراجات",
        }],
        "model": "m", "model_provider": "OpenRouter",
        "generated_at_display": "Sep 3, 2026, 7:51 pm",
    }
    html = render_report_html(report)
    assert "0 refs" not in html
    assert "not stored with this report" in html


# --- defect 3: human-formatted dates everywhere, raw ISO nowhere --------------


def test_format_labels_match_the_required_human_formats():
    assert format_date_label("2026-06-06") == "Jun 6, 2026"
    assert format_range_label("2026-06-06", "2026-09-01") == "Jun 6, 2026 - Sep 1, 2026"
    # 14:51 UTC == 7:51 pm PKT — the audit's example format, to the minute.
    dt = datetime(2026, 9, 3, 14, 51, 24, tzinfo=timezone.utc)
    assert format_datetime_label(dt) == "Sep 3, 2026, 7:51 pm"
    # Naive datetimes (SQLite round-trip) are read as UTC — same label.
    assert format_datetime_label(datetime(2026, 9, 3, 14, 51)) == "Sep 3, 2026, 7:51 pm"


def test_payload_and_html_carry_formatted_labels_not_raw_iso(tmp_path):
    url, mid, _ = _seed(tmp_path, name="d.db")
    report = generate_report(mid, period="all", db_url=url)
    assert DATETIME_LABEL.fullmatch(report["generated_at_display"])
    assert DATETIME_LABEL.fullmatch(
        format_datetime_label(report["generated_at"])  # ISO stays machine-facing
    )
    html = render_report_html(report)
    assert report["generated_at_display"] in html
    assert report["period"]["label"] in html
    assert not ISO_DATE.search(html)  # no 2026-06-06-style dates anywhere
    assert report["generated_at"] not in html  # no raw ISO datetime either


# --- defect 4: real model id + runtime-derived provider -----------------------


def test_footer_payload_carries_real_model_id_and_openrouter_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_REASONING", "minimax/minimax-m3:free")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://openrouter.ai/api/v1")
    url, mid, _ = _seed(tmp_path, name="p.db")
    report = generate_report(mid, period="all", db_url=url)

    assert report["model"] == "minimax/minimax-m3:free"      # env, not hardcoded
    assert report["model_provider"] == "OpenRouter"          # host-derived

    # Mock report (no key here): no model ran — the artifact says so honestly
    # and never claims Alibaba Cloud Model Studio for an openrouter.ai host.
    html = render_report_html(report)
    assert "Alibaba" not in html
    assert "Model: none" in html

    # A live (non-mock) report names the model AND the derived provider.
    live = dict(report)
    live.pop("mock", None)
    html_live = render_report_html(live)
    assert "minimax/minimax-m3:free" in html_live
    assert "via OpenRouter" in html_live
    assert "Alibaba" not in html_live


def test_alibaba_claimed_only_when_host_actually_is_alibaba(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_REASONING", "qwen3.7-plus")
    monkeypatch.setenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    url, mid, _ = _seed(tmp_path, name="a.db")
    report = generate_report(mid, period="all", db_url=url)
    assert report["model_provider"] == "Alibaba Cloud Model Studio"
    live = dict(report)
    live.pop("mock", None)
    assert "via Alibaba Cloud Model Studio" in render_report_html(live)


def test_provider_derivation_from_base_url_host():
    assert provider_from_base_url("https://openrouter.ai/api/v1") == "OpenRouter"
    assert provider_from_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1") == (
        "Alibaba Cloud Model Studio"
    )
    # Unknown host -> the honest host label, never a guessed brand.
    unknown = provider_from_base_url("https://api.mystery.dev/v1")
    assert unknown == "api.mystery.dev"
    assert "Alibaba" not in unknown
    assert "OpenRouter" not in unknown
