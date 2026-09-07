"""Honest labeling + seed enrichment tests (schema.md §12).

The readiness score renders with its honest label everywhere it appears; the
four standing limitations ride the payload and render as a footer card; the
seeded demo history shows the real officer-pack states: one concentrated top
debtor, aged udhar, a deliberate latest-week activity dip — all deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.committee_summary import render_committee_summary_html
from credit_agent.render import render_report_html
from credit_agent.report import generate_report
from credit_agent.rubric import INDICATOR_NOTE, LIMITATIONS
from credit_agent.seed import TOP_DEBTOR, seed_demo


@pytest.fixture(scope="module")
def enriched(tmp_path_factory):
    d = tmp_path_factory.mktemp("enriched")
    url = f"sqlite:///{d / 'e.db'}"
    mid = seed_demo(url)
    report = generate_report(mid, period="last_90_days", db_url=url)
    return report, url, mid


# --- honest labeling ------------------------------------------------------------


def test_report_json_carries_indicator_note_and_limitations(enriched):
    report, _, _ = enriched
    assert report["readiness"]["note"] == INDICATOR_NOTE
    assert report["limitations"] == LIMITATIONS
    for phrase in ("self-reported", "No outcome validation", "Urdu",
                   "heuristics"):
        joined = " ".join(report["limitations"])
        assert phrase in joined, f"limitation missing: {phrase}"


def test_full_report_html_labels_the_score_and_lists_limitations(enriched):
    report, _, _ = enriched
    html = render_report_html(report)
    assert INDICATOR_NOTE in html           # under the band, where the score is
    assert "Limitations — read before deciding" in html
    assert "not a validated repayment predictor" in html
    assert html.count("<li>") >= len(LIMITATIONS)


def test_committee_page_labels_the_score_too(enriched):
    report, url, _ = enriched
    html = render_committee_summary_html(report, db_url=url)
    assert INDICATOR_NOTE in html
    assert "merchant-self-reported" in html or "merchant-self-reported" in " ".join(
        report["limitations"]
    )


def test_legacy_payload_without_note_renders_without_label():
    report = {
        "merchant": {"name": "Old"}, "period": {"label": "p"},
        "readiness": {"band": "nearly", "score": 60},
        "red_flags": [], "line_items": [], "metrics": [],
        "model": "m", "model_provider": "OpenRouter",
        "generated_at_display": "Sep 3, 2026, 7:51 pm",
    }
    html = render_report_html(report)
    assert "nearly" in html           # still renders
    assert INDICATOR_NOTE not in html  # no invented label on legacy payloads


# --- seed enrichment --------------------------------------------------------------


def test_seed_concentrates_one_top_debtor(enriched):
    report, _, _ = enriched
    conc = report["officer"]["concentration"]
    assert conc["top_debtor"] == TOP_DEBTOR
    assert conc["warn"] is True
    assert conc["top_share"] > 40.0


def test_seed_aged_udhar_fills_aging_buckets(enriched):
    report, _, _ = enriched
    buckets = {b["bucket"]: b["total"] for b in report["officer"]["aging"]["buckets"]}
    assert buckets["61-90"] > 0


def test_seed_90plus_bucket_when_history_runs_long_enough(tmp_path):
    """With a 100-day seed and period=all, the 95-day-old credit lands in 90+."""
    url = f"sqlite:///{tmp_path / 'long.db'}"
    mid = seed_demo(url, days=100)
    report = generate_report(mid, period="all", db_url=url)
    buckets = {b["bucket"]: b["total"] for b in report["officer"]["aging"]["buckets"]}
    assert buckets["90+"] > 0


def test_seed_activity_dip_in_latest_week(enriched):
    report, _, _ = enriched
    act = report["officer"]["activity"]
    assert act["activity_drop_pct"] is not None
    assert act["latest_full_week_count"] < 0.5 * act["eight_week_median"]
    # the shop is slowed, not abandoned: the latest week is not empty
    assert act["latest_full_week_count"] > 0


def test_seed_enrichment_is_deterministic(tmp_path):
    urls = [f"sqlite:///{tmp_path / f'{n}.db'}" for n in ("a", "b")]
    reports = [
        generate_report(seed_demo(u), period="last_90_days", db_url=u)
        for u in urls
    ]
    ra, rb = reports
    assert ra["readiness"]["score"] == rb["readiness"]["score"]
    assert ra["trust"]["corroboration_pct"] == rb["trust"]["corroboration_pct"]
    assert (ra["officer"]["concentration"]["top_share"]
            == rb["officer"]["concentration"]["top_share"])
    assert (ra["officer"]["activity"]["activity_drop_pct"]
            == rb["officer"]["activity"]["activity_drop_pct"])
