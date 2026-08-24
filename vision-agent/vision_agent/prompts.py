"""Structured-extraction prompt shared by BOTH OCR adapters.

Why a plain custom prompt and not ocr_options/key_information_extraction:
see vision-agent/notes.md §2 — the compatible-mode interface we use takes
custom prompts on both models, ocr_options built-in tasks are a DashScope-native
parameter, and pre-3.5 models override custom prompts when a task is set. The
docs' own ticket-extraction example is exactly this pattern (custom prompt ->
JSON-only output -> fence-strip + json.loads).

qwen3.5-ocr lists "structured output" (response_format) as unsupported, so
JSON-in-text with a robust parser + pydantic repair-retry is the correct shape.
"""

from __future__ import annotations

RECEIPT_EXTRACTION_PROMPT = """\
You are reading a photo of a handwritten supplier receipt (karyana store purchase, \
Pakistan). Extract the receipt into JSON. Output ONLY the JSON object — no markdown \
fence, no commentary before or after.

Rules:
- Transcribe EXACTLY what is written. Item names may be romanized Urdu or English \
(e.g. "chai patti", "cheeni", "dal masoor") — keep them as written.
- NEVER guess a digit. If any part of a quantity, price, or total is unreadable, \
blurry, or ambiguous, do NOT output that number: instead add a short note to \
"unclear_parts" (e.g. "second line price unreadable") and omit the field.
- qty and unit_price must be plain numbers (no "Rs", no commas). unit is a short \
string if written (packet, kg, dozen), else null.
- stated_total is the receipt's written grand total. Copy it exactly if present, \
else null. Do NOT compute it yourself.
- supplier_name: the shop/supplier name if readable, else null.
- is_receipt: false if this image is not a receipt/bill/invoice at all (a person, \
scenery, a screenshot, a product photo, etc.).
- self_confidence: your own 0.0-1.0 confidence that you read this receipt correctly.

JSON shape:
{
  "is_receipt": true,
  "supplier_name": "Al-Madina Kiryana Store" | null,
  "items": [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350}
  ],
  "stated_total": 2560 | null,
  "unclear_parts": [],
  "self_confidence": 0.9
}"""


def repair_prompt(previous_output: str, problems: str) -> str:
    """Follow-up prompt when pydantic validation failed (repair-retry)."""
    return (
        "Your previous answer was not valid for this schema. Problems:\n"
        f"{problems}\n\n"
        "Your previous answer was:\n"
        f"{previous_output}\n\n"
        "Return the CORRECTED JSON object only — no markdown fence, no commentary. "
        "Keep the extraction rules: never guess digits; omit unreadable numbers and "
        "note them in unclear_parts."
    )
