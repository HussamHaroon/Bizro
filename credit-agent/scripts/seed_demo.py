"""Seed BOTH demo merchants, then generate + render their Credit Readiness
Reports — the one-command dashboard/report demo data setup. The pair demos
RANGE in the loan-officer picker: Al-Madina Kiryana Store (healthy, scores
"ready") vs Bilal Ki Dukan (contrast profile, scores "nearly"/"not_yet").

Usage: python scripts/seed_demo.py [db_url]   (default sqlite:///./bizro.db)
Prints: JSON — both merchant_ids + readiness (paste into dashboard/API) and
the rendered Al-Madina report HTML path.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import pathlib
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
# repo root (for nothing else — credit_agent is self-contained)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from credit_agent.seed import seed_demo  # noqa: E402
from credit_agent.report import generate_report  # noqa: E402
from credit_agent.render import save_report_html  # noqa: E402
from credit_agent.rubric import BAND_LABELS_UR, BAND_NEARLY, BAND_READY  # noqa: E402
from credit_agent.db_view import CreditReport, get_sessionmaker  # noqa: E402

MERCHANTS = [
    # (name, seed kwargs, mock trend history ascending: oldest → newer → latest)
    ("Al-Madina Kiryana Store", {}, [(60, 58), (30, 77)]),
    ("Bilal Ki Dukan", {"profile": "contrast", "days": 60}, [(60, 41), (30, 55)]),
]


def _band_for(score: int) -> str:
    return ("ready" if score >= BAND_READY
            else "nearly" if score >= BAND_NEARLY else "not_yet")


def _hist_row(base: dict, mid: str, score: int, days_ago: int) -> CreditReport:
    rj = copy.deepcopy(base)
    rj["readiness"]["score"] = score
    rj["readiness"]["band"] = band = _band_for(score)
    rj["readiness"]["label_ur"] = BAND_LABELS_UR[band]
    rj.setdefault("mock", True)
    end = datetime.now(timezone.utc) - timedelta(days=days_ago)
    rj["period"] = {
        "start": (end - timedelta(days=90)).date().isoformat(),
        "end": end.date().isoformat(),
    }
    return CreditReport(
        id=uuid.uuid4(), merchant_id=uuid.UUID(mid),
        period_start=end.date() - timedelta(days=90), period_end=end.date(),
        model=rj.get("model"), report_json=rj,
        narrative_ur=rj.get("narrative_ur"),
        created_at=end,
    )


def main() -> None:
    db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "DATABASE_URL", "sqlite:///./bizro.db"
    )
    # The server owns the shared schema (schema.md) — create tables with ITS
    # models so a fresh DB gets the full schema, not the report mirror's subset.
    from sqlalchemy import create_engine

    from server.app.db import Base as ServerBase

    ServerBase.metadata.create_all(create_engine(db))

    ids, reports = [], {}
    for name, kwargs, _hist in MERCHANTS:
        mid = seed_demo(db, merchant_name=name, create_tables=False, **kwargs)
        ids.append((name, mid, _hist))
        reports[name] = generate_report(mid, period="last_90_days")

    # DA-UI fix: demo trend tells the PRODUCT story — readiness rising as history
    # accumulates (Al-Madina 58 → 77 → latest; Bilal 41 → 55 → latest), all rows
    # the SAME 90-day window so the sparkline never mixes periods. Mock-marked
    # demo data (schema.md §6.3).
    Session = get_sessionmaker(db)
    with Session() as s:
        for name, mid, hist in ids:
            base_json = {k: v for k, v in reports[name].items() if k != "mock"}
            for days_ago, score in hist:
                s.add(_hist_row(base_json, mid, score, days_ago))
        s.commit()

    out = pathlib.Path("credit_report_demo.html").resolve()
    save_report_html(reports[MERCHANTS[0][0]], str(out))
    print(json.dumps({
        "merchants": [
            {
                "name": name,
                "merchant_id": mid,
                "readiness": reports[name]["readiness"],
                "mock": reports[name].get("mock", False),
            }
            for name, mid, _hist in ids
        ],
        "html": str(out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
