"""Shared truthfulness helpers — the ONLY place dates and provider names are
formatted for users (red-team audit 2026-09-04, defects 3 + 4).

Dates: every user-visible date/time is rendered as e.g. "Sep 3, 2026, 7:51 pm"
and ranges as "Jun 6, 2026 - Sep 1, 2026" — never a raw ISO string. Labels are
computed in Pakistan Standard Time (UTC+5, no DST) so the dashboard, the
printable HTML and the tests all agree deterministically.

Provider: the model provider is DERIVED AT RUNTIME from the DASHSCOPE_BASE_URL
host — the URL the model calls actually go to. "Alibaba Cloud Model Studio" is
only ever claimed when the host actually is one; unknown hosts are labeled with
the host itself (an honest, checkable claim instead of a guessed brand).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

PKT = timezone(timedelta(hours=5))  # Asia/Karachi — fixed offset, no DST

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# The base URL narrative.py calls when DASHSCOPE_BASE_URL is unset — provider
# derivation must mirror the real call target, so the defaults match.
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

_PROVIDER_BY_HOST = {
    "openrouter.ai": "OpenRouter",
    "dashscope.aliyuncs.com": "Alibaba Cloud Model Studio",
    "dashscope-intl.aliyuncs.com": "Alibaba Cloud Model Studio",
}


def provider_from_base_url(base_url: str | None) -> str:
    """Provider label for the host model calls ACTUALLY go to (defect 4)."""
    url = (base_url or "").strip() or DEFAULT_BASE_URL
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "unknown provider"
    if host in _PROVIDER_BY_HOST:
        return _PROVIDER_BY_HOST[host]
    if host == "aliyuncs.com" or host.endswith(".aliyuncs.com"):
        return "Alibaba Cloud Model Studio"
    if host.endswith(".openrouter.ai"):
        return "OpenRouter"
    return host  # honest fallback: name the host, never a guessed brand


def ensure_aware(value) -> datetime | None:
    """Coerce a datetime / ISO string to an aware datetime. Naive values are
    read as UTC — that is how SQLite round-trips the aware datetimes
    report.py/aggregates.py write (Postgres returns aware ones directly)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def month_key(value) -> str | None:
    """'YYYY-MM' in PKT — the single month computation that every month count,
    header range and bar set derives from (defect 1)."""
    dt = ensure_aware(value)
    if dt is None:
        return None
    pkt = dt.astimezone(PKT)
    return f"{pkt.year:04d}-{pkt.month:02d}"


def format_date_label(value) -> str:
    """'Jun 6, 2026' (PKT). Accepts datetimes, full ISO strings and bare
    'YYYY-MM-DD' dates."""
    dt = ensure_aware(value)
    if dt is None:
        return str(value if value is not None else "")
    pkt = dt.astimezone(PKT)
    return f"{MONTHS[pkt.month - 1]} {pkt.day}, {pkt.year}"


def format_datetime_label(value) -> str:
    """'Sep 3, 2026, 7:51 pm' (PKT) — the audit's required human format."""
    dt = ensure_aware(value)
    if dt is None:
        return str(value if value is not None else "")
    pkt = dt.astimezone(PKT)
    hour = pkt.hour % 12 or 12
    ampm = "am" if pkt.hour < 12 else "pm"
    return f"{MONTHS[pkt.month - 1]} {pkt.day}, {pkt.year}, {hour}:{pkt.minute:02d} {ampm}"


def format_range_label(start, end) -> str:
    """'Jun 6, 2026 - Sep 1, 2026'."""
    return f"{format_date_label(start)} - {format_date_label(end)}"
