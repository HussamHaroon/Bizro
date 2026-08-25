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
    out = pathlib.Path("credit_report_demo.html").resolve()
    save_report_html(report, str(out))
    compact = {k: report[k] for k in ("readiness", "criteria_basis", "mock")
               if k in report}
    print(json.dumps({"merchant_id": mid, "report": compact, "html": str(out)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
