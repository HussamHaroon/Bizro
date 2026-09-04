"""Canned realistic Urdu scenarios for MOCK_MODE (SKILL.md: every mock payload is
marked `"mock": true` and must never be presentable as real model output).

Mock output is shaped EXACTLY like the real model's text response (a JSON object), so
the pipeline's extraction → validation → flag → confirmation path runs for real — only
the network call is faked.
"""

from __future__ import annotations

# Each scenario = the JSON the single-prompt asks the model to produce.
# Transcript style: casual spoken Urdu, numbers as words, code-switch included.

SCENARIOS: dict[str, dict] = {
    "clean_udhar": {
        "transcript": "احمد کو پانچ ہزار روپے ادھار دیے ہیں، کل شام کو کا حساب ہے۔",
        "transaction": {
            "kind": "udhar_given",
            "amount_pkr": 5000,
            "counterparty": {"name": "احمد", "phone": None},
            "description": "Udhar given to Ahmad",
            "item_lines": [],
            "unclear": [],
        },
        "confidence": 0.93,
    },
    "sale_with_items": {
        "transcript": (
            "بلال نے آج دو پیکٹ چائے پتی لیے اور ایک ڈبن گھی، کُل پندرہ سو روپے، "
            "نقد دے دیے۔"
        ),
        "transaction": {
            "kind": "sale",
            "amount_pkr": 1500,
            "counterparty": {"name": "بلال", "phone": None},
            "description": "Cash sale to Bilal: 2 packets tea leaves, 1 tin ghee",
            "item_lines": [
                {"item": "چائے پتی", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700},
                {"item": "گھی", "qty": 1, "unit": "tin", "unit_price": 800, "line_total": 800},
            ],
            "unclear": [],
        },
        "confidence": 0.9,
    },
    "ambiguous_amount": {
        "transcript": "احمد کو کچھ روپے ادھار دیے تھے… پانچ ہزار یا چھ ہزار، پکا نہیں پتا۔",
        "transaction": {
            "kind": "udhar_given",
            "amount_pkr": None,  # NEVER guess (schema.md §1)
            "counterparty": {"name": "احمد", "phone": None},
            "description": "Udhar to Ahmad, amount uncertain",
            "item_lines": [],
            "unclear": ["amount"],
        },
        "confidence": 0.31,
    },
    "unclear_kind": {
        "transcript": "پچھلے مہینے کا پورا حساب دکھاؤ، کتنا ادھار باقی ہے؟",
        "transaction": {
            "kind": None,  # not a transaction at all — a query
            "amount_pkr": None,
            "counterparty": {"name": None, "phone": None},
            "description": "Not a transaction: ledger query",
            "item_lines": [],
            "unclear": ["kind", "amount"],
        },
        "confidence": 0.12,
    },
    "mixed_urdu_english": {
        "transcript": "Usman ne panch hazar ka saman liya, cash diye, bill bhi le gaya.",
        "transaction": {
            "kind": "sale",
            "amount_pkr": 5000,
            "counterparty": {"name": "Usman", "phone": None},
            "description": "Cash sale to Usman (mixed Urdu/English note)",
            "item_lines": [],
            "unclear": [],
        },
        "confidence": 0.88,
    },
    "expense_supplier": {
        "transcript": (
            "المدینا ڈسٹریبیوٹرز سے آٹھ بوری چاول آئے ہیں، بیس ہزار روپے، ادھار پر۔"
        ),
        "transaction": {
            "kind": "expense",
            "amount_pkr": 20000,
            "counterparty": {"name": "المدینا ڈسٹریبیوٹرز", "phone": None},
            "description": "Supplier purchase: 8 bags rice on credit",
            "item_lines": [
                {"item": "چاول", "qty": 8, "unit": "بوری", "unit_price": 2500, "line_total": 20000},
            ],
            "unclear": [],
        },
        "confidence": 0.86,
    },
    "garbage_audio": {
        # Model heard nothing usable. Pipeline maps this to the low-confidence fallback.
        "transcript": "",
        "transaction": None,
        "confidence": 0.0,
    },
}

SCENARIO_NAMES = list(SCENARIOS)


def infer_scenario(audio_bytes: bytes) -> str:
    """Heuristic pick when no explicit scenario is requested: tiny/junkish payloads
    that would not survive real decode count as garbage; otherwise clean_udhar."""
    if len(audio_bytes) < 64 or audio_bytes[:4] == b"\x00\x00\x00\x00":
        return "garbage_audio"
    return "clean_udhar"


def mock_response_text(scenario: str) -> str:
    """Render the scenario as the model's textual JSON reply (code-fenced, like the
    real model tends to emit even when told not to — keeps extraction code honest)."""
    import json

    payload = SCENARIOS[scenario]
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
