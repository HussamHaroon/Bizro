"""Clearly-labeled synthetic OCR outputs (MOCK_MODE, Orchestrator decision D0-3).

Mock results can never masquerade as real model output (notes.md D-V7):
- the pipeline records source.model = "mock:<model-id>"
- source.raw_output carries {"mock": true, ...}

Scenarios are keyed by filename stem so tests drive behavior with plain image
files; an explicit scenario override is also supported (adapters.MockOcrAdapter).
Raw texts deliberately include ```json fences to exercise the real parser.
"""

from __future__ import annotations

# Scenario keys
CLEAN = "clean"
BLURRY = "blurry"
WRONG_PRICE = "wrong_price"
NOT_RECEIPT = "not_receipt"

_SCENARIO_BY_FILENAME_TOKEN = {
    "blurry": BLURRY,
    "blur": BLURRY,
    "wrong_price": WRONG_PRICE,
    "wrongprice": WRONG_PRICE,
    "anomaly": WRONG_PRICE,
    "not_receipt": NOT_RECEIPT,
    "notreceipt": NOT_RECEIPT,
    "photo": NOT_RECEIPT,
    "selfie": NOT_RECEIPT,
}


def scenario_for_path(path) -> str:
    """Map an image filename to a mock scenario (default: clean receipt)."""
    stem = getattr(path, "stem", str(path)).lower()
    for token, scenario in _SCENARIO_BY_FILENAME_TOKEN.items():
        if token in stem:
            return scenario
    return CLEAN


# Raw "model responses" — JSON wrapped in a fence, like real model behavior.
_RAW: dict[str, str] = {
    CLEAN: """\
Here is the extracted receipt:
```json
{
  "is_receipt": true,
  "supplier_name": "Al-Madina Kiryana Store",
  "items": [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350},
    {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180},
    {"item": "dal masoor", "qty": 3, "unit": "kg", "unit_price": 320}
  ],
  "stated_total": 2560,
  "unclear_parts": [],
  "self_confidence": 0.95
}
```""",
    BLURRY: """\
```json
{
  "is_receipt": true,
  "supplier_name": null,
  "items": [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350},
    {"item": "??", "qty": 0, "unit": null, "unit_price": 0}
  ],
  "stated_total": null,
  "unclear_parts": ["shop name unreadable", "second line item and price unreadable", "grand total not readable"],
  "self_confidence": 0.4
}
```""",
    WRONG_PRICE: """\
```json
{
  "is_receipt": true,
  "supplier_name": "Al-Madina Kiryana Store",
  "items": [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 3500},
    {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180},
    {"item": "dal masoor", "qty": 3, "unit": "kg", "unit_price": 320}
  ],
  "stated_total": 8860,
  "unclear_parts": [],
  "self_confidence": 0.93
}
```""",
    NOT_RECEIPT: """\
```json
{
  "is_receipt": false,
  "supplier_name": null,
  "items": [],
  "stated_total": null,
  "unclear_parts": ["image shows a street scene, no receipt text detected"],
  "self_confidence": 0.9
}
```""",
}

# Explanations recorded in raw_output for the audit trail.
_NOTES: dict[str, str] = {
    CLEAN: "synthetic clean handwritten receipt (mock)",
    BLURRY: "synthetic motion-blur/low-light photo: partial read (mock)",
    WRONG_PRICE: "synthetic clean receipt whose chai-patti price is 10x history (mock)",
    NOT_RECEIPT: "synthetic non-receipt photo (mock)",
}


def mock_raw_text(scenario: str) -> str:
    try:
        return _RAW[scenario]
    except KeyError as exc:
        raise KeyError(f"unknown mock scenario {scenario!r}; known: {sorted(_RAW)}") from exc


def mock_note(scenario: str) -> str:
    return _NOTES.get(scenario, "synthetic (mock)")


def all_scenarios() -> list[str]:
    return [CLEAN, BLURRY, WRONG_PRICE, NOT_RECEIPT]
