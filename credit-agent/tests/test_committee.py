"""Committee one-pager tests (schema.md §12).

The artifact a lending committee reads: identity block with visit-capture
placeholders, band + score with the honest indicator label, corroboration
headline, top metrics, aging summary, top-5 flags/notices, ledger-chain
statement + QR, limitations footer. Offline, deterministic.
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.committee_summary import (
    CHAIN_UNSEALED,
    INDICATOR_NOTE,
    render_committee_summary_html,
)
from credit_agent.db_view import Base, Transaction, get_sessionmaker
from credit_agent.render import render_report_html  # noqa: F401 (parity check)
from credit_agent.report import generate_report
from credit_agent.seed import seed_demo

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.fixture()
def seeded_report(tmp_path):
    url = f"sqlite:///{tmp_path / 'c.db'}"
    mid = seed_demo(url)
    return generate_report(mid, period="last_90_days", db_url=url), url, mid


def test_identity_block_carries_visit_placeholders(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    assert report["merchant"]["name"] in html
    assert html.count("capture on visit") == 3  # city, CNIC, years trading
    assert "Committee Summary" in html
    assert report["period"]["label"] in html


def test_band_score_and_honest_indicator_label(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    assert INDICATOR_NOTE in html
    assert str(report["readiness"]["score"]) in html
    assert report["readiness"]["band"].replace("_", " ") in html


def test_corroboration_headline_and_officer_numbers_on_page(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    assert "corroborated revenue" in html
    assert f"{report['trust']['corroboration_pct']}%" in html
    off = report["officer"]
    # aging buckets and collection rate appear as displayed text
    for b in off["aging"]["buckets"]:
        if b["total"] > 0:
            assert f"{b['bucket']}d PKR" in html
    assert f"{off['collection']['rate'] * 100:.0f}%" in html


def test_flags_and_notices_capped_at_five(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    flags_card = html.split("Flags &amp; notices")[-1].split("</div>")[0]
    assert flags_card.count("<li>") <= 5


def test_chain_statement_unsealed_when_hash_absent(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    assert CHAIN_UNSEALED in html
    assert "Ledger chain: not yet sealed" in html
    assert "Ledger chain sealed" not in html  # never claims integrity it can't see


def test_chain_statement_sealed_shows_hash_and_qr(tmp_path):
    url = f"sqlite:///{tmp_path / 's.db'}"
    mid = seed_demo(url)
    Session = get_sessionmaker(url)
    fake_hash = "ab" * 32
    with Session() as s:
        tx = s.query(Transaction).filter(
            Transaction.merchant_id == uuid.UUID(mid)
        ).order_by(Transaction.occurred_at.desc()).first()
        tx.entry_hash = fake_hash
        s.commit()
    report = generate_report(mid, period="last_90_days", db_url=url)
    html = render_committee_summary_html(report, db_url=url)
    assert "Ledger chain sealed" in html
    assert fake_hash[:16] in html
    assert "data:image/png;base64," in html  # real QR rendered


def test_qr_fallback_marks_pending_when_package_missing(seeded_report, monkeypatch):
    report, url, _ = seeded_report
    monkeypatch.setitem(sys.modules, "qrcode", None)  # import raises ImportError
    html = render_committee_summary_html(report, db_url=url)
    assert "QR pending" in html
    assert "qrcode package unavailable" in html
    assert "data:image/png" not in html


def test_limitations_footer_present_even_on_legacy_payload(tmp_path):
    url = f"sqlite:///{tmp_path / 'l.db'}"
    mid = seed_demo(url)
    report = generate_report(mid, period="last_90_days", db_url=url)
    legacy = {k: v for k, v in report.items() if k != "limitations"}
    html = render_committee_summary_html(legacy, db_url=url)
    assert "Limitations" in html
    assert "not a validated repayment predictor" in html
    assert "merchant-self-reported" in html  # the default footer carried it


def test_no_raw_iso_dates_on_the_one_pager(seeded_report):
    report, url, _ = seeded_report
    html = render_committee_summary_html(report, db_url=url)
    assert not ISO_DATE.search(html), "raw ISO date leaked onto the page"


def test_sealed_chain_on_plain_full_report_payload(seeded_report):
    """Render directly from a fresh generate_report dict with no officer/trust
    blocks stripped — committee page degrades gracefully section by section."""
    report, url, _ = seeded_report
    for key in ("officer", "trust", "red_flags"):
        report.pop(key, None)
    html = render_committee_summary_html(report, db_url=url)
    assert "no flags or notices recorded" in html
    assert "corroboration not yet measured" in html
    assert "no outstanding udhar" in html
    assert "—" in html  # missing metrics shown as dashes, never invented


def test_mock_report_carries_banner_real_report_does_not(seeded_report):
    """F2 (§6.3): the committee one-pager is a report layer — it must surface
    the mock marker wherever the payload carries it (the full report already
    does; this surface used to render a mock report with no disclosure)."""
    report, url, _ = seeded_report
    assert report.get("mock") is True  # offline fixture: templated narrative
    html = render_committee_summary_html(report, db_url=url)
    assert "MOCK DATA" in html

    real = {k: v for k, v in report.items() if k != "mock"}
    assert "MOCK DATA" not in render_committee_summary_html(real, db_url=url)
