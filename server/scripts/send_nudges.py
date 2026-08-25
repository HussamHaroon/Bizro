"""Send the weekly Urdu nudge to all merchants (run Fridays; mock-safe).

Usage: python server/scripts/send_nudges.py [--merchant <uuid>]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from server.app.db import db_session  # noqa: E402
from server.app.nudges import compute_weekly_nudge, send_weekly_nudges  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merchant", default=None, help="single merchant uuid")
    args = ap.parse_args()

    with db_session() as session:
        if args.merchant:
            nudge = compute_weekly_nudge(session, uuid.UUID(args.merchant))
            print(json.dumps({"merchant_id": args.merchant, **nudge},
                             ensure_ascii=False, indent=2))
        else:
            for row in send_weekly_nudges(session):
                print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
