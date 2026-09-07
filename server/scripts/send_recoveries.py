"""Send the udhaar recovery ladder to merchants (run nightly; mock-safe).

Polite escalating reminders to customers with aging udhaar (gentle 15-29d,
firm 30-44d, escalation 45d+), every customer message CC'd to the shopkeeper
thread as fine print, and a separate shopkeeper escalation notice at 45d+.
One message per customer per day (idempotent via outbound_messages).

Usage:
    python server/scripts/send_recoveries.py [--merchant <uuid>] [--dry-run]

--dry-run computes the ladder and prints the actions without sending
(presenter-safe). Default sends via dispatch.deliver() — mock mode logs,
live mode sends.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import select  # noqa: E402

from server.app.db import Merchant, db_session  # noqa: E402
from server.app.recoveries import compute_recovery_actions, send_recovery_messages  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--merchant", default=None, help="single merchant uuid")
    ap.add_argument(
        "--dry-run", action="store_true",
        help="compute the ladder only — show who would be messaged, send nothing",
    )
    args = ap.parse_args()

    with db_session() as session:
        if args.merchant:
            merchant_ids = [uuid.UUID(args.merchant)]
        else:
            merchant_ids = [
                m.id
                for m in session.scalars(
                    select(Merchant).order_by(Merchant.created_at)
                ).all()
            ]

        if args.dry_run:
            for mid in merchant_ids:
                actions = compute_recovery_actions(session, mid)
                print(json.dumps({"merchant_id": str(mid), "actions": actions},
                                 ensure_ascii=False, indent=2))
        else:
            for mid in merchant_ids:
                for row in send_recovery_messages(session, merchant_id=mid):
                    print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
