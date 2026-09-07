"""generate_report — the server's fixed entrypoint (server/app/dispatch.py).

generate_report(merchant_id, period="last_30_days") -> report dict (schema.md §6.5
skeleton + additive narrative_ur/mock keys), persisted to credit_reports.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .aggregates import Aggregates, compute_aggregates
from .data_quality import compute_data_quality
from .db_view import CreditReport, Customer, Merchant, Transaction, get_sessionmaker
from .forensics import compute_forensics
from .formatting import (
    DEFAULT_BASE_URL,
    format_date_label,
    format_datetime_label,
    format_range_label,
    provider_from_base_url,
)
from .narrative import build_narrative
from .officer import compute_officer_metrics
from .rubric import (
    INDICATOR_NOTE,
    INDICATOR_NOTE_UR,
    LIMITATIONS,
    TWO_WAY_NOTE_CLAUSE,
    TWO_WAY_NOTE_CLAUSE_UR,
    score,
)
from .trust import compute_trust

PERIODS = {
    "last_30_days": 30,
    "last_90_days": 90,
    "all": 3650,
}

MAX_LINE_ITEMS = 12


def _resolve_period(period: str | None) -> tuple[datetime, datetime]:
    days = PERIODS.get(period or "last_30_days", 30)
    end = datetime.now(timezone.utc)
    return end - timedelta(days=days), end


def _metric(key, label_en, label_ur, value, display, provenance) -> dict:
    return {
        "key": key,
        "label_en": label_en,
        "label_ur": label_ur,
        "value": value,
        "display": display,
        "provenance": provenance,
    }


def _prov(agg: Aggregates) -> dict:
    return {
        "voice_pct": agg.provenance.get("voice", 0.0),
        "photo_pct": agg.provenance.get("photo", 0.0),
        "manual_pct": agg.provenance.get("manual", 0.0),
        "median_confidence": agg.median_confidence,
    }


def _two_way_required(session, mid) -> bool:
    """The officer's two-way toggle (server §8 merchant_settings, owner ruling
    2026-09-07). Raw SELECT on the report session — db_view.py mirrors no
    settings table by design. Defensive read: ANY failure (table missing in
    standalone mirror DBs, column missing pre-migration) means OFF, i.e.
    exactly the pre-toggle rubric. Binding is dialect-aware: SQLAlchemy Uuid
    stores CHAR(32) dash-less hex on SQLite, native UUID on Postgres."""
    from sqlalchemy import text as sa_text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
        param = mid if dialect == "postgresql" else mid.hex
        val = session.execute(
            sa_text(
                "SELECT two_way_confirmation_required FROM merchant_settings "
                "WHERE merchant_id = :mid"
            ),
            {"mid": param},
        ).scalar()
    except SQLAlchemyError:
        return False
    return bool(val)


def generate_report(merchant_id, period: str = "last_30_days", db_url: str | None = None) -> dict:
    mid = merchant_id if isinstance(merchant_id, uuid.UUID) else uuid.UUID(str(merchant_id))
    start, end = _resolve_period(period)
    Session = get_sessionmaker(db_url)
    with Session() as session:
        merchant = session.get(Merchant, mid)
        mname = (merchant.display_name if merchant else None) or "Bizro Merchant"

        txs = session.scalars(
            select(Transaction)
            .where(Transaction.merchant_id == mid)
            .where(Transaction.occurred_at >= start)
            .order_by(Transaction.occurred_at.desc())
        ).all()
        cust_ids = {t.customer_id for t in txs if t.customer_id}
        customers = {
            c.id: c
            for c in session.scalars(select(Customer).where(Customer.id.in_(cust_ids)))
        }

        agg = compute_aggregates(list(txs), customers, now=end)
        # §12: corroboration share — how much of the stated revenue (sale +
        # udhar_settlement) carries a tier vouched by someone other than the
        # merchant. Disclosure for the officer, never a trust score — and,
        # when the officer's two-way toggle is ON, the raw value of the
        # CORROBORATION rubric pillar (rubric.py).
        trust = compute_trust(list(txs))
        two_way = _two_way_required(session, mid)
        scored = score(
            agg,
            corroboration_pct=trust["corroboration_pct"],
            two_way_required=two_way,
        )
        narrative_ur, is_mock = build_narrative(agg, scored, mname)
        data_quality = compute_data_quality(list(txs), now=end)
        forensics = compute_forensics(list(txs), customers, now=end)
        # §12: officer completeness metrics — aging, collection rate,
        # concentration, weekly-entries activity. The desk-check numbers a
        # manual credit officer would compile, computed from the ledger.
        officer = compute_officer_metrics(list(txs), customers, now=end)
        # §10: forensics ride the same disclosure card — patterns from ledger
        # internals + receipt provenance, never assertions of intent.
        data_quality["forensics"] = forensics
        data_quality["indicators"] = list(data_quality.get("indicators", [])) + list(
            forensics.get("indicators", [])
        )

        # Attribution (defect 4): the model id ACTUALLY configured, and the
        # provider derived AT RUNTIME from the host the model calls really go
        # to — never a hardcoded brand claim.
        model = os.environ.get("MODEL_REASONING", "qwen-flash")
        provider = provider_from_base_url(
            os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL)
        )
        generated_at = datetime.now(timezone.utc)

        # Period (defects 1 + 3): month count, header-range labels and every
        # downstream bar/month list read from the SAME computation over the
        # actual occurred_at values (agg.months / agg.period_*), and formatted
        # human labels ride along so no surface prints raw ISO strings.
        period_start = agg.period_start or start
        period_end = agg.period_end or end

        red_flags = []
        for f, n in sorted(agg.flag_counts.items()):
            # Defect 2: every flag carries refs to the entries it flags —
            # never an untraceable "0 refs".
            refs = list(agg.flag_refs.get(f, []))
            entry = {
                "flag": f,
                "count": n,
                "refs": refs,
                "note_en": f"{n} entries flagged {f}",
                "note_ur": f"{n} اندراجات میں {f} کا اشارہ",
            }
            if not refs:
                entry["refs_reason"] = (
                    "the flagged entry ids were not stored with this report"
                )
            red_flags.append(entry)

        report: dict = {
            "period": {
                "start": period_start.date().isoformat(),
                "end": period_end.date().isoformat(),
                "start_display": format_date_label(period_start),
                "end_display": format_date_label(period_end),
                "label": format_range_label(period_start, period_end),
                "months": agg.months,
                "months_count": len(agg.months),
            },
            "readiness": {
                "score": scored.score,
                "band": scored.band,
                "label_ur": scored.label_ur,
                # §12 honest labeling: travels with the score into every
                # consumer of the payload, not just the renderers. OFF reports
                # are byte-identical to the pre-toggle payload except the one
                # additive boolean below; ON appends ONE short clause.
                "note": INDICATOR_NOTE
                + (TWO_WAY_NOTE_CLAUSE if two_way else ""),
                **(
                    {"note_ur": INDICATOR_NOTE_UR + TWO_WAY_NOTE_CLAUSE_UR}
                    if two_way
                    else {}
                ),
                # Two-way toggle (owner ruling 2026-09-07): the ONLY flag
                # exposure anywhere in the payload — no banners, no badges.
                "two_way_required": two_way,
            },
            "metrics": [
                _metric("entries", "Total entries", "کل اندراجات",
                        agg.total_entries, str(agg.total_entries), _prov(agg)),
                _metric("consistency", "Weekly consistency", "ہفتہ وار تسلسل",
                        agg.weeks_active / agg.weeks_in_span if agg.weeks_in_span else 0,
                        f"{agg.weeks_active}/{agg.weeks_in_span} weeks", _prov(agg)),
                _metric("cashflow", "Net cash-flow (PKR)", "خالص مالی رفتار",
                        agg.net_cashflow, f"PKR {agg.net_cashflow:,.0f}", _prov(agg)),
                _metric("udhar", "Udhar outstanding (PKR)", "بقایا اُدھار",
                        agg.udhar_outstanding, f"PKR {agg.udhar_outstanding:,.0f}",
                        _prov(agg)),
                # Appended last so existing metrics[i] consumers keep their
                # indexes; same single computation as period.months_count.
                _metric("months", "Months of records", "ریکارڈ کے مہینے",
                        len(agg.months), str(len(agg.months)), _prov(agg)),
            ],
            "line_items": [
                {
                    "ref": str(t.id),
                    "label": (t.description or t.kind),
                    "amount_pkr": float(t.amount_pkr),
                    "source_type": t.source_type,
                    "source_media_id": str(t.source_media_id) if t.source_media_id else None,
                    "source_model": t.source_model,
                    "confidence": float(t.confidence) if t.confidence is not None else None,
                }
                for t in list(txs)[:MAX_LINE_ITEMS]
            ],
            "red_flags": red_flags,
            "criteria_basis": "general-microfinance-pending-mawakhat",
            "model": model,
            "model_provider": provider,
            "generated_at": generated_at.isoformat(),
            "generated_at_display": format_datetime_label(generated_at),
            "merchant": {"id": str(mid), "name": mname},
            "narrative_ur": narrative_ur,
            "pillars": scored.pillars,
            # Data-quality & consistency disclosures (schema.md §9 local ruling):
            # ledger-internals evidence for the loan officer — never a trust score.
            "data_quality": data_quality,
            # §12: trust tiers — corroboration share of stated revenue.
            "trust": trust,
            # §12: officer completeness metrics for the review pack.
            "officer": officer,
            # §12: the four standing limitations, rendered as a footer card on
            # every surface — self-reported inputs, no outcome validation,
            # Urdu-centric parsing, heuristics not forensics.
            "limitations": list(LIMITATIONS),
        }
        if is_mock:
            report["mock"] = True

        # §6.3/§6.11: the mock marker MUST survive persistence — any consumer
        # loading this row (dashboard cached preview, committee tools) must be
        # able to see the report ran without a live model. (The strip here used
        # to hide mock runs stored outside the API's adopt-and-rewrite path.)
        row = CreditReport(
            id=uuid.uuid4(),
            merchant_id=mid,
            period_start=agg.period_start.date() if agg.period_start else start.date(),
            period_end=agg.period_end.date() if agg.period_end else end.date(),
            model=report["model"],
            report_json=report,
            narrative_ur=narrative_ur,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        return report
