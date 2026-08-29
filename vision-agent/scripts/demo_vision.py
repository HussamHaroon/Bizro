"""Demo beat 2 rehearsal: samples/demo receipt photos -> pipeline -> verdict.

Runs each clearly-synthetic DEMO receipt image through the REAL production
entry point (``vision_agent.pipeline.process_receipt_image``) and prints what
the judge would see, per image: kind, amount, flag, confidence, and the Urdu
confirmation. Adapter resolution is production behavior too (MOCK_MODE):

- no ``DASHSCOPE_API_KEY``  -> mock adapter (clearly labeled, filename-routed
  scenarios that mirror what the images depict)
- ``DASHSCOPE_API_KEY`` set -> the real OCR adapter fires automatically

The script says which one ran and exits non-zero on any unexpected outcome,
so it is safe to wire into a pre-demo checklist.

Usage (root venv, any cwd):
  .venv/Scripts/python vision-agent/scripts/demo_vision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: make vision_agent importable (script lives in vision-agent/scripts).
VISION_AGENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VISION_AGENT_DIR))

from vision_agent.adapters import MockOcrAdapter, get_adapter  # noqa: E402
from vision_agent.config import default_settings  # noqa: E402
from vision_agent.pipeline import ReceiptRejected, process_receipt_image  # noqa: E402

WORKTREE_ROOT = VISION_AGENT_DIR.parent
DEMO_DIR = WORKTREE_ROOT / "samples" / "demo"

MERCHANT = "wa:923001234567"  # demo merchant (audit context only)

# Price-history fixture (schema.md §1 transaction dicts, like the server would
# pass): chai patti 350 / cheeni 180 / dal masoor 320 — the medians that make
# the 3,500 PKR chai patti line on receipt_wrong_price.png a price_anomaly.
HISTORY = [
    {
        "kind": "expense",
        "amount_pkd": 2560,
        "counterparty": {"name": "Al-Madina Kiryana Store", "phone": None},
        "item_lines": [
            {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700},
            {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180, "line_total": 900},
            {"item": "dal masoor", "qty": 3, "unit": "kg", "unit_price": 320, "line_total": 960},
        ],
        "occurred_at": "2026-08-18T10:00:00+05:00",  # days before OCCURRED: no duplicate
        "status": "confirmed",
    }
]
OCCURRED = "2026-08-29T19:03:00+05:00"

# filename -> (expected flag, English narration line for the demo script)
EXPECTATIONS = {
    "receipt_clean.png": (
        "none",
        "judge sees: expense recorded in Urdu, awaiting one-tap confirm",
    ),
    "receipt_wrong_price.png": (
        "price_anomaly",
        "judge sees: price error flagged in Urdu",
    ),
    "receipt_blurry.png": (
        "low_confidence",
        "judge sees: blurry photo politely refused in Urdu — asked for a clearer shot",
    ),
}


def banner(text: str) -> None:
    print("\n" + "=" * 74 + f"\n{text}\n" + "=" * 74)


def main() -> int:
    # Windows consoles (cp1252) would otherwise crash on the Urdu strings.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    settings = default_settings()
    banner("Bizro demo beat 2: photo in -> price-error flag out (rehearsal)")

    try:
        adapter = get_adapter(settings)
    except Exception as exc:  # OcrConfigError: MOCK_MODE=never without a key
        print(f"ADAPTER ERROR: {exc}")
        return 2

    if isinstance(adapter, MockOcrAdapter):
        print(f"adapter : MOCK ({adapter.model}) — no DASHSCOPE_API_KEY set;")
        print("          synthetic OCR output, clearly labeled in the audit trail")
    else:
        print(f"adapter : REAL ({adapter.name} -> {adapter.model}) — DASHSCOPE_API_KEY set")
    print(f"merchant: {MERCHANT}, history fixture: {len(HISTORY[0]['item_lines'])} price points")

    failures: list[str] = []
    for filename, (expected_flag, narration) in EXPECTATIONS.items():
        path = DEMO_DIR / filename
        print(f"\n--- {path.relative_to(WORKTREE_ROOT)}")
        if not path.exists():
            failures.append(f"{filename}: missing (run scripts/make_demo_receipts.py)")
            print("  MISSING — regenerate with scripts/make_demo_receipts.py")
            continue
        try:
            tx = process_receipt_image(
                path,
                merchant=MERCHANT,
                occurred_at=OCCURRED,
                history=HISTORY,
                media_id=f"demo-{path.stem}",
            )
        except ReceiptRejected as exc:
            failures.append(f"{filename}: rejected ({exc.reason}) — expected {expected_flag}")
            print(f"  REJECTED ({exc.reason}): {exc.reply_ur}")
            continue

        flag = tx["flag"]
        ok = flag == expected_flag and tx["kind"] == "expense" and tx["status"] == "pending"
        if isinstance(adapter, MockOcrAdapter) and ok:
            # Offline amounts are deterministic (mock_data scenarios) — check them.
            expected_amount = {"receipt_clean.png": 2560, "receipt_wrong_price.png": 8860,
                               "receipt_blurry.png": 700}[filename]
            ok = tx["amount_pkd"] == expected_amount
        if not ok:
            failures.append(
                f"{filename}: flag={flag} kind={tx['kind']} status={tx['status']} "
                f"amount={tx['amount_pkd']} — expected flag={expected_flag}"
            )

        print(f"  kind        : {tx['kind']}")
        print(f"  amount      : {tx['amount_pkd']} PKR")
        print(f"  flag        : {flag} (expected {expected_flag})")
        print(f"  confidence  : {tx['source']['confidence']}  model: {tx['source']['model']}")
        print(f"  status      : {tx['status']}")
        print(f"  confirmation_ur:")
        for line in tx["confirmation_ur"].splitlines():
            print(f"    {line}")
        print(f"  >> {narration}" + ("" if flag == expected_flag else "   [MISSED]"))

    banner("DEMO VERDICT")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"\n{len(failures)} unexpected outcome(s) — demo is NOT ready.")
        return 1
    print("all 3 receipts behaved as scripted — demo beat 2 is green.")
    print("(offline mock run: rehearsed, not proven — bake-off still needs real photos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
