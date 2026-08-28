"""Seed a demo merchant with ~90 days of realistic history, then generate + render
its Credit Readiness Report — the one-command dashboard/report demo data setup.

Usage: python scripts/seed_demo.py [db_url]   (default sqlite:///./bizro.db)
Prints: merchant_id (paste into dashboard/API), report HTML path.
"""

from __future__ import annotations

import json
import os
import sys
import pathlib
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
# repo root (for nothing else — credit_agent is self-contained)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from credit_agent.seed import seed_demo  # noqa: E402
from credit_agent.report import generate_report  # noqa: E402
from credit_agent.render import save_report_html  # noqa: E402


def main() -> None:
    db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "DATABASE_URL", "sqlite:///./bizro.db"
    )
    # The server owns the shared schema (schema.md) — create tables with ITS
    # models so a fresh DB gets the full schema, not the report mirror's subset.
    from sqlalchemy import create_engine

    from server.app.db import Base as ServerBase

    ServerBase.metadata.create_all(create_engine(db))
    mid = seed_demo(db, create_tables=False)
    report = generate_report(mid, period="last_90_days")

    # DA-UI fix: demo trend tells the PRODUCT story — readiness rising as history
    # accumulates (58 → 77 → <latest>), all rows the SAME 90-day window so the
    # sparkline never mixes periods. Mock-marked demo data (schema.md §6.3).
    import copy as _copy
    from datetime import datetime, timedelta, timezone as _tz

    from credit_agent.db_view import CreditReport, get_sessionmaker

    def _hist_row(base: dict, score: int, days_ago: int) -> CreditReport:
        rj = _copy.deepcopy(base)
        rj["readiness"]["score"] = score
        rj["readiness"]["band"] = "ready" if score >= 75 else "nearly"
        rj["readiness"]["label_ur"] = "قرض کے لیے تیار" if score >= 75 else "تقریباً تیار"
        rj.setdefault("mock", True)
        end = datetime.now(_tz.utc) - timedelta(days=days_ago)
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

    Session = get_sessionmaker(db)
    with Session() as s:
        base_json = {k: v for k, v in report.items() if k not in ("mock",)}
        s.add(_hist_row(base_json, 77, 30))
        s.add(_hist_row(base_json, 58, 60))
        s.commit()
    out = pathlib.Path("credit_report_demo.html").resolve()
    save_report_html(report, str(out))
    compact = {k: report[k] for k in ("readiness", "criteria_basis", "mock")
               if k in report}
    print(json.dumps({"merchant_id": mid, "report": compact, "html": str(out)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
