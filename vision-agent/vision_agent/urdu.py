"""Clean Urdu confirmations for expense entries (schema.md §1 confirmation_ur).

WhatsApp renders Urdu RTL natively — this IS the text-out path (design.md §2;
Urdu speech-out is a stretch goal, never assumed). Numerals render Western by
default and Eastern Arabic-Indic when NUMERAL_STYLE=urdu (schema.md §1).
"""

from __future__ import annotations

from typing import Any

from vision_agent.sanity import FlagDetail

_EASTERN = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹.")

# --- Urdu phrases (kept short, WhatsApp-friendly, no literary vocabulary) ---
_ITEMS_TMPL = "{item} {qty} {unit} × {price}"
SUPPLIER_FROM = "{supplier} سے"
EXPENSE_SAVED = "خرچ درج ہو گیا۔"
TOTAL_IS = "کل: {total} روپے۔"
CORRECT_Q = "کیا یہ درست ہے؟"
LOW_CONF_REPLY = (
    "تصویر صاف نہیں تھی، اس لیے کچھ چیزیں پڑھ نہیں سکا۔ "
    "براہ کرم کل رقم خود لکھ دیں، یا receipt کی واضح تصویر دوبارہ بھیجیں۔"
)
PRICE_ANOMALY_WARN = (
    "تنبیہ: {item} کی قیمت پچھلی خریداری سے بہت مختلف ہے "
    "(پچھلی بار {hist} روپے، اب {new} روپے)۔ کیا یہ درست ہے؟"
)
TOTAL_MISMATCH_WARN = (
    "تنبیہ: receipt پر کل {stated} روپے لکھا ہے مگر حساب {computed} روپے بنتا ہے۔ "
    "براہ کرم جانچ کر جواب دیں۔"
)
DUPLICATE_WARN = (
    "تنبیہ: یہی خریداری {minutes} منٹ پہلے بھی درج ہوئی تھی۔ "
    "اگر یہ دوبارہ بھیجی گئی ہے تو 'درست نہیں' جواب دیں۔"
)
NOT_A_RECEIPT_REPLY = (
    "معاف کیجیے گا، یہ تصویر receipt نہیں لگ رہی۔ "
    "براہ کرم خریداری کی receipt کی واضح تصویر بھیجیں۔"
)
UNREADABLE_RECEIPT_REPLY = (
    "receipt پڑھی نہیں جا سکی۔ براہ کرم روشنی میں، سیدھی اور قریب سے "
    "تصویر دوبارہ بھیجیں۔"
)


def fmt_number(value: float | int, style: str = "western") -> str:
    """Format a number for outbound Urdu text per NUMERAL_STYLE."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
    return text.translate(_EASTERN) if style == "urdu" else text


def _items_phrase(item_lines: list[dict[str, Any]], style: str, limit: int = 3) -> str:
    parts = []
    for line in item_lines[:limit]:
        unit = str(line.get("unit") or "").strip()
        parts.append(
            _ITEMS_TMPL.format(
                item=str(line.get("item", "")),
                qty=fmt_number(line.get("qty", 0), style),
                unit=unit,
                price=fmt_number(line.get("unit_price", 0), style),
            ).replace("  ", " ")
        )
    more = len(item_lines) - limit
    suffix = f" (+{fmt_number(more, style)})" if more > 0 else ""
    return ("؛ ".join(parts) + suffix).strip()


def confirmation_ur(
    supplier: str | None,
    amount_pkr: float,
    item_lines: list[dict[str, Any]],
    flag: str,
    flag_details: list[FlagDetail],
    numeral_style: str = "western",
) -> str:
    """Build the WhatsApp confirmation for an expense entry.

    Flag-aware: warnings the merchant can act on ride along with the standard
    "is this correct?" ask (SKILL.md: clarification in confirmation_ur).
    """
    by_kind = {detail.kind: detail for detail in flag_details}
    lines: list[str] = []

    if flag == "low_confidence":
        # The parse is unreliable — ask for the number rather than asserting one.
        readable = _items_phrase(item_lines, numeral_style) if item_lines else ""
        opener = (SUPPLIER_FROM.format(supplier=supplier) + " ") if supplier else ""
        parts = []
        if readable:
            parts.append(f"جو پڑھا: {opener}{readable}۔")
        parts.append(LOW_CONF_REPLY)
        return " ".join(parts)

    opener = (SUPPLIER_FROM.format(supplier=supplier) + " ") if supplier else ""
    body = f"{opener}{_items_phrase(item_lines, numeral_style)}۔ " if item_lines else ""
    lines.append(EXPENSE_SAVED)
    lines.append(f"{body}{TOTAL_IS.format(total=fmt_number(amount_pkr, numeral_style))}")

    if flag == "total_mismatch" and "total_mismatch" in by_kind:
        data = by_kind["total_mismatch"].data
        lines.append(
            TOTAL_MISMATCH_WARN.format(
                stated=fmt_number(data["stated_total"], numeral_style),
                computed=fmt_number(data["computed_total"], numeral_style),
            )
        )
    elif flag == "price_anomaly" and "price_anomaly" in by_kind:
        data = by_kind["price_anomaly"].data
        lines.append(
            PRICE_ANOMALY_WARN.format(
                item=data["item"],
                hist=fmt_number(data["historical_median"], numeral_style),
                new=fmt_number(data["unit_price"], numeral_style),
            )
        )
    elif flag == "duplicate_suspect" and "duplicate_suspect" in by_kind:
        data = by_kind["duplicate_suspect"].data
        lines.append(DUPLICATE_WARN.format(minutes=fmt_number(data["minutes_apart"], numeral_style)))

    lines.append(CORRECT_Q)
    return " ".join(lines)


def reject_reply_ur(reason: str) -> str:
    """Polite reject for ReceiptRejected (notes.md D-V5)."""
    return UNREADABLE_RECEIPT_REPLY if reason == "unreadable" else NOT_A_RECEIPT_REPLY
