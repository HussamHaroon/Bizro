"""Ledger integrity chain (schema.md §11) — tamper-EVIDENT, not tamper-PROOF.

Every transaction row is sealed with:

    entry_hash      = sha256(prev_entry_hash | merchant_id | kind | amount |
                            occurred_at | description | item_lines canonical |
                            source_media_id | created_at)
    prev_entry_hash = the previous row's entry_hash for the SAME merchant

The chain appends at insert time. Edits and deletes NEVER rewrite hashes —
instead, `verify_chain` recomputes each row's hash from its CURRENT fields and
reports:
  - mismatch    → "amended after sealing" (the edit is visible, expected,
                  still auditable via original_values)
  - broken link → a row vanished or was inserted out of band (the gap IS the
                  detection)
This is honest: a hash chain over mutable storage proves what was sealed and
makes every later change detectable — it cannot stop the operator with DB
write access. The loan officer sees the verdict, the officer decides.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timezone as _UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Transaction


def _canonical_item_lines(item_lines: Any) -> str:
    """Sorted-keys, no-whitespace JSON; None/[] normalize to '[]'."""
    if not item_lines:
        return "[]"
    if isinstance(item_lines, str):
        try:
            item_lines = json.loads(item_lines)
        except (TypeError, ValueError):
            return "[]"
    return json.dumps(item_lines, sort_keys=True, separators=(",", ":"), default=str)


def _iso(value: Any) -> str:
    """Timestamps must hash IDENTICALLY at seal time and at verify time.
    SQLite reads back naive datetimes while inserts were tz-aware, so every
    datetime is normalized to UTC before hashing — naive values are treated
    as UTC (the server-wide storage convention)."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        dt = value if not hasattr(value, "tzinfo") else value
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=_UTC.utc)
        return dt.astimezone(_UTC.utc).isoformat()
    return str(value)


def compute_entry_hash(
    *,
    prev_hash: str | None,
    merchant_id: Any,
    kind: str,
    amount_pkr: Any,
    occurred_at: Any,
    description: Any,
    item_lines: Any,
    source_media_id: Any,
    created_at: Any,
) -> str:
    """The single canonical hash definition. changing ANY input byte changes
    the hash — that property is the whole feature."""
    payload = "|".join(
        [
            prev_hash or "",
            str(merchant_id),
            kind or "",
            f"{float(amount_pkr):.2f}",
            _iso(occurred_at),
            description or "",
            _canonical_item_lines(item_lines),
            str(source_media_id) if source_media_id else "",
            _iso(created_at),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seal_transaction(tx: Transaction, prev_hash: str | None) -> None:
    """Seal a NEW row onto the merchant's chain (insert path only)."""
    tx.prev_entry_hash = prev_hash
    tx.entry_hash = compute_entry_hash(
        prev_hash=prev_hash,
        merchant_id=tx.merchant_id,
        kind=tx.kind,
        amount_pkr=tx.amount_pkr,
        occurred_at=tx.occurred_at,
        description=tx.description,
        item_lines=tx.item_lines,
        source_media_id=tx.source_media_id,
        created_at=tx.created_at,
    )


def chain_tail(session: Session, merchant_id: uuid.UUID) -> str | None:
    """The latest sealed entry_hash for a merchant, or None when the merchant
    has no sealed rows yet."""
    row = session.execute(
        select(Transaction.entry_hash)
        .where(
            Transaction.merchant_id == merchant_id,
            Transaction.entry_hash.is_not(None),
        )
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def verify_chain(session: Session, merchant_id: uuid.UUID) -> dict[str, Any]:
    """Recompute every sealed row and walk the links.

    Returns:
      {"valid": bool, "checked": int,
       "amended_after_sealing": [tx ids], "unsealed": int,
       "broken_at": tx id | null, "details": [...]}
    """
    rows = (
        session.scalars(
            select(Transaction)
            .where(Transaction.merchant_id == merchant_id)
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        )
        .all()
    )
    sealed = [t for t in rows if t.entry_hash]
    amended: list[str] = []
    broken_at: str | None = None
    details: list[dict[str, Any]] = []
    expected_prev: str | None = None

    for tx in sealed:
        if expected_prev is not None and (tx.prev_entry_hash or "") != expected_prev:
            broken_at = str(tx.id)
            details.append(
                {
                    "tx_id": str(tx.id),
                    "problem": "broken_link",
                    "expected_prev": expected_prev,
                    "found_prev": tx.prev_entry_hash,
                }
            )
            expected_prev = tx.entry_hash  # resync so one gap doesn't cascade
            continue

        recomputed = compute_entry_hash(
            prev_hash=tx.prev_entry_hash,
            merchant_id=tx.merchant_id,
            kind=tx.kind,
            amount_pkr=tx.amount_pkr,
            occurred_at=tx.occurred_at,
            description=tx.description,
            item_lines=tx.item_lines,
            source_media_id=tx.source_media_id,
            created_at=tx.created_at,
        )
        if recomputed != tx.entry_hash:
            amended.append(str(tx.id))
            details.append(
                {
                    "tx_id": str(tx.id),
                    "problem": "amended_after_sealing",
                    "note": "current fields differ from the sealed hash; "
                    "see original_values for the pre-edit snapshot",
                }
            )
        expected_prev = tx.entry_hash

    return {
        "valid": not amended and broken_at is None,
        "checked": len(sealed),
        "amended_after_sealing": amended,
        "unsealed": len(rows) - len(sealed),
        "broken_at": broken_at,
        "details": details,
    }
