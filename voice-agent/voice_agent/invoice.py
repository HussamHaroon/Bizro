"""Branded WhatsApp invoice renderer — Khata Modern house style (design.md §4).

HTML template built ONLY from dashboard/design-tokens/tokens.json values (token law:
no improvised colors/fonts). Rendered to PNG via Playwright using the SYSTEM EDGE
channel (verified working — voice-agent/notes.md §3); any failure falls back to a
ledger-style plain-text receipt. Rendering NEVER blocks the confirmation text path
(SKILL.md deliverable 4).

Torn/perforated top edge appears HERE ONLY (khata-modern skill: reserved for the
WhatsApp invoice image). Elevation rule: 1px rule-line borders, NO box-shadow.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import string
from pathlib import Path

from voice_agent.config import Settings, load_settings
from voice_agent.confirmation import amount_in_urdu_words, to_numeral_digits

# ---------------------------------------------------------------------------
# Token loading (token law)
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict | None = None


def load_tokens(settings: Settings | None = None) -> dict:
    global _TOKEN_CACHE
    if _TOKEN_CACHE is None:
        root = (settings or load_settings()).repo_root
        path = root / "dashboard" / "design-tokens" / "tokens.json"
        _TOKEN_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _TOKEN_CACHE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_invoice(
    transaction: dict,
    out_path: str | Path | None = None,
    *,
    settings: Settings | None = None,
) -> Path:
    """Render the invoice PNG for a schema.md §1 transaction dict.

    Returns the written path. Falls back to a plain-text receipt (also a valid path)
    if a headless browser is unavailable — never raises for rendering problems.
    """
    settings = settings or load_settings()
    out = Path(out_path) if out_path else _default_out_path(transaction, settings)
    out.parent.mkdir(parents=True, exist_ok=True)

    tokens = load_tokens(settings)
    page_html = build_invoice_html(transaction, tokens, settings.numeral_style)

    png = _render_png(page_html)
    if png is not None:
        out = out.with_suffix(".png")
        out.write_bytes(png)
        return out

    out = out.with_suffix(".txt")
    out.write_text(build_invoice_text(transaction, settings.numeral_style), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# HTML template (string.Template — CSS braces safe)
# ---------------------------------------------------------------------------

_KIND_VIEW = {
    # kind → (urdu label, english label, icon, direction word, color token key)
    "sale": ("فروخت", "CASH SALE", "◈", "وصول ہوئے", "settledTeal"),
    "expense": ("خرچ", "EXPENSE", "▼", "خرچ ہوئے", "ledgerRed"),
    "udhar_given": ("ادھار دیا", "UDHAR GIVEN", "▲", "ادھار دیے", "ledgerRed"),
    "udhar_settlement": ("ادھار وصول", "SETTLEMENT", "✓", "وصول ہوئے", "settledTeal"),
}

_URDU_MONTHS = [
    "جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون",
    "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر",
]

_TEMPLATE = string.Template("""<!DOCTYPE html>
<html lang="ur" dir="rtl">
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@500;700&family=Noto+Sans+Urdu:wght@400;700&family=Noto+Nastaliq+Urdu:wght@600&display=swap" rel="stylesheet">
<style>
  :root { }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:${pageBg}; font-family:${fontBody}; color:${inkBlack};
         -webkit-font-smoothing:antialiased; padding:24px; }
  #invoice { width:420px; margin:0 auto; background:${cardBg};
             border:1px solid ${ruleLine}; border-radius:6px; overflow:hidden; }

  /* torn/perforated top edge — reserved flourish (HERE ONLY) */
  .torn { display:block; width:100%; height:18px; }

  .head { background:${inkGreen}; color:${cardBg}; padding:14px 18px 10px;
          display:flex; justify-content:space-between; align-items:center; }
  .brand { font-family:${fontDisplay}; font-size:26px; line-height:1.9; direction:rtl; }
  .head-meta { font-size:11px; text-align:left; direction:ltr; opacity:.9; line-height:1.6; }

  .greet { font-family:${fontDisplay}; font-size:17px; line-height:2.6;
           text-align:center; padding:14px 18px 4px; color:${inkBlack}; }

  .kind { display:flex; align-items:center; gap:10px; justify-content:center;
          padding:6px 18px 12px; }
  .kind .icon { width:34px; height:34px; border-radius:50%; background:${kindColor};
                color:${cardBg}; display:flex; align-items:center; justify-content:center;
                font-size:16px; font-family:${fontNumerals}; }
  .kind .ur { font-size:20px; font-weight:700; color:${kindColor}; }
  .kind .en { font-size:10px; letter-spacing:2px; color:${inkBlack}; opacity:.65;
              font-family:${fontNumerals}; direction:ltr; }

  .amount { text-align:center; padding:2px 18px 14px; }
  .amount .digits { font-family:${fontNumerals}; font-size:52px; font-weight:700;
                    color:${kindColor}; direction:ltr; line-height:1.15; }
  .amount .digits .cur { font-size:22px; vertical-align:14px; color:${inkBlack}; }
  .amount .words { font-size:15px; padding-top:2px; }
  .amount .direction { font-size:13px; color:${inkBlack}; opacity:.75; padding-top:3px; }

  table.items { width:100%; border-collapse:collapse; margin:0 0 6px; }
  table.items th { font-size:11px; font-weight:400; color:${inkBlack}; opacity:.6;
                   border-top:1px solid ${ruleLine}; border-bottom:1px solid ${ruleLine};
                   padding:6px 10px; text-align:right; }
  table.items td { padding:7px 10px; border-bottom:1px solid ${ruleLine}; font-size:13px; }
  table.items .num { font-family:${fontNumerals}; direction:ltr; text-align:left; }
  tr:last-child td { border-bottom:1px solid ${ruleLine}; }

  .meta { padding:10px 18px 4px; font-size:13px; line-height:2; }
  .meta b { font-weight:700; }

  .seal-row { display:flex; align-items:center; gap:12px; padding:10px 18px 16px; }
  .seal { transform:rotate(-8deg); flex:0 0 auto; }
  .seal-copy { font-size:11px; line-height:1.9; }
  .seal-copy .en { font-family:${fontNumerals}; letter-spacing:1px; color:${sealGold};
                   font-weight:700; direction:ltr; display:block; }
  .seal-copy .conf { color:${inkBlack}; opacity:.7; }
  .edit-hint { margin:0 18px 14px; padding:8px 10px; border:1px solid ${ruleLine};
               border-radius:6px; font-size:12px; line-height:1.9; }

  .foot { border-top:1px solid ${ruleLine}; padding:9px 18px; font-size:11px;
          display:flex; justify-content:space-between; opacity:.8; }
  .mock-band { background:${ledgerRed}; color:${cardBg}; text-align:center;
               font-size:12px; letter-spacing:3px; padding:5px 0; direction:ltr;
               font-family:${fontNumerals}; }
</style>
</head>
<body>
  <div id="invoice">
    <svg class="torn" viewBox="0 0 420 18" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M0,18 L0,10 L15,3 L30,12 L45,2 L60,11 L75,4 L90,12 L105,2 L120,10 L135,3 L150,12 L165,2 L180,11 L195,4 L210,12 L225,2 L240,10 L255,3 L270,12 L285,2 L300,11 L315,4 L330,12 L345,2 L360,10 L375,3 L390,12 L405,2 L420,10 L420,18 Z"
            fill="${inkGreen}"/>
    </svg>
    <div class="head">
      <div class="brand">بِزرو</div>
      <div class="head-meta">${merchantHtml}<br>${dateHtml}</div>
    </div>

    <div class="greet">شکریہ! آپ کا اندراج محفوظ ہو گیا</div>

    <div class="kind">
      <span class="icon">${kindIcon}</span>
      <span class="ur">${kindUr}</span>
      <span class="en">${kindEn}</span>
    </div>

    <div class="amount">
      <div class="digits"><span class="cur">Rs.</span> ${amountDigits}</div>
      <div class="words">(${amountWords})</div>
      <div class="direction">${kindDirection} — ${kindUr}</div>
    </div>

    ${itemsHtml}

    <div class="meta">
      ${counterpartyHtml}
      ${lowConfidenceHtml}
    </div>

    <div class="seal-row">
      <svg class="seal" width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
        <circle cx="32" cy="32" r="30" fill="none" stroke="${sealGold}" stroke-width="2.5"/>
        <circle cx="32" cy="32" r="24.5" fill="none" stroke="${sealGold}" stroke-width="1"/>
        <path id="sealArc" d="M32,32 m-19,0 a19,19 0 1,1 38,0 a19,19 0 1,1 -38,0"
              fill="none" stroke="none"/>
        <text font-size="6.2" fill="${sealGold}" font-family="Georgia, serif" letter-spacing="1.1">
          <textPath href="#sealArc" startOffset="4%">ALIBABA CLOUD AI VERIFIED · BIZRO ·</textPath>
        </text>
        <text x="32" y="30" text-anchor="middle" font-size="13" font-weight="bold"
              fill="${sealGold}" font-family="Georgia, serif">AI</text>
        <text x="32" y="42" text-anchor="middle" font-size="10" fill="${sealGold}"
              font-family="Georgia, serif">✓</text>
      </svg>
      <div class="seal-copy">
        <span class="en">ALIBABA CLOUD AI VERIFIED</span>
        <span class="conf">${confidenceLine}</span>
      </div>
    </div>

    <div class="edit-hint">اگر یہ اندراج غلط ہو تو اِس پیغام کے جواب میں "غلط" لکھیں۔</div>

    <div class="foot">
      <span>بِزرو — آپ کے کھاتے کی ڈیجیٹل یاد</span>
      <span style="direction:ltr">${txRef}</span>
    </div>
    ${mockBand}
  </div>
</body>
</html>""")


def build_invoice_html(tx: dict, tokens: dict, numeral_style: str = "western") -> str:
    color = tokens["color"]
    font = tokens["font"]
    kind = tx.get("kind") or "udhar_given"
    kind_ur, kind_en, kind_icon, kind_dir, kind_color_key = _KIND_VIEW[kind]
    kind_color = color[kind_color_key]

    amount = float(tx.get("amount_pkd") or 0)
    esc = html.escape

    merchant = (tx.get("merchant") or {}).get("display_name") or ""
    merchant_html = esc(merchant) if merchant else "کھاتہ — Bizro"

    when = _parse_when(tx.get("occurred_at"))
    date_html = f"{to_numeral_digits(when.day, numeral_style)} {_URDU_MONTHS[when.month-1]} {to_numeral_digits(when.year, numeral_style)}"

    cp = tx.get("counterparty") or {}
    cp_name = (cp.get("name") or "").strip()
    cp_html = f"<b>گاہک:</b> {esc(cp_name)}" if cp_name else ""
    if kind == "expense" and cp_name:
        cp_html = f"<b>سوداگر:</b> {esc(cp_name)}"

    flag = tx.get("flag") or "none"
    low_conf_html = ""
    if flag != "none":
        warn = "یہ اندراج پکا نہیں — تصدیق ضروری ہے" if flag == "low_confidence" else "توجہ: رقم میں فرق ہے" if flag == "total_mismatch" else "توجہ بھیجانا ضروری ہے"
        low_conf_html = (
            f'<div style="margin-top:6px;padding:6px 10px;border:1px solid {color["ledgerRed"]};'
            f'border-radius:6px;color:{color["ledgerRed"]};font-size:12px;line-height:1.9">⚠ {warn}</div>'
        )

    rows = ""
    for line in tx.get("item_lines") or []:
        rows += (
            "<tr>"
            f"<td>{esc(str(line.get('item','')))}</td>"
            f"<td class='num'>{to_numeral_digits(line.get('qty',0), numeral_style)}</td>"
            f"<td class='num'>{to_numeral_digits(line.get('unit_price',0), numeral_style)}</td>"
            f"<td class='num'>{to_numeral_digits(line.get('line_total',0), numeral_style)}</td>"
            "</tr>"
        )
    items_html = ""
    if rows:
        items_html = (
            '<table class="items">'
            "<tr><th>چیز</th><th style='text-align:left;direction:ltr'>Qty</th>"
            "<th style='text-align:left;direction:ltr'>Rate</th>"
            "<th style='text-align:left;direction:ltr'>Total</th></tr>"
            f"{rows}</table>"
        )

    src = tx.get("source") or {}
    conf = src.get("confidence")
    conf_line = (
        f"AI امانت: {to_numeral_digits(int(round(conf*100)), numeral_style)}%"
        if isinstance(conf, (int, float)) else "AI امانت: —"
    )

    mock_band = '<div class="mock-band">MOCK DATA — NOT A REAL ENTRY</div>' if tx.get("mock") else ""

    return _TEMPLATE.substitute(
        pageBg=color["paperCream"],
        cardBg=color["paperCreamRaised"],
        inkGreen=color["inkGreen"],
        inkBlack=color["inkBlack"],
        ruleLine=color["ruleLine"],
        sealGold=color["sealGold"],
        kindColor=kind_color,
        ledgerRed=color["ledgerRed"],
        fontBody=font["body"],
        fontNumerals=font["numerals"],
        fontDisplay=font["displayUrdu"],
        merchantHtml=merchant_html,
        dateHtml=date_html,
        kindUr=kind_ur, kindEn=kind_en, kindIcon=kind_icon, kindDirection=kind_dir,
        amountDigits=to_numeral_digits(amount, numeral_style),
        amountWords=f"{amount_in_urdu_words(amount)} روپے",
        itemsHtml=items_html,
        counterpartyHtml=cp_html,
        lowConfidenceHtml=low_conf_html,
        confidenceLine=conf_line,
        txRef=esc(str(tx.get("source", {}).get("media_id") or "voice-entry")),
        mockBand=mock_band,
    )


# ---------------------------------------------------------------------------
# Text fallback (ledger-style plain receipt)
# ---------------------------------------------------------------------------


def build_invoice_text(tx: dict, numeral_style: str = "western") -> str:
    kind = tx.get("kind") or "udhar_given"
    kind_ur, kind_en, _icon, kind_dir, _c = _KIND_VIEW[kind]
    amount = float(tx.get("amount_pkd") or 0)
    cp = (tx.get("counterparty") or {}).get("name") or ""
    when = _parse_when(tx.get("occurred_at"))
    digits = to_numeral_digits(amount, numeral_style)
    words = amount_in_urdu_words(amount)

    lines = [
        "*بِزرو — رسید*",
        f"{kind_ur} ({kind_en}) — {kind_dir}",
        f"رقم: Rs. {digits} ({words} روپے)",
    ]
    if cp:
        lines.append(f"گاہک: {cp}")
    if tx.get("item_lines"):
        lines.append("—")
        for li in tx["item_lines"]:
            lines.append(
                f"{li.get('item','')} ×{to_numeral_digits(li.get('qty',0), numeral_style)}"
                f" = {to_numeral_digits(li.get('line_total',0), numeral_style)}"
            )
    lines += [
        "—",
        f"تاریخ: {to_numeral_digits(when.day, numeral_style)} {_URDU_MONTHS[when.month-1]} {to_numeral_digits(when.year, numeral_style)}",
        "Alibaba Cloud AI Verified — اگر غلط ہو تو جواب میں لکھیں۔",
    ]
    if (tx.get("flag") or "none") != "none":
        lines.append("⚠ یہ اندراج پکا نہیں — تصدیق ضروری ہے")
    if tx.get("mock"):
        lines.append("MOCK DATA — NOT A REAL ENTRY")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rendering internals
# ---------------------------------------------------------------------------


def _render_png(page_html: str) -> bytes | None:
    """Playwright render via system Edge/Chromium. Returns None on ANY failure
    (not installed, no browser, timeout) — caller falls back to text."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        import urllib.parse

        data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(page_html)
        with sync_playwright() as p:
            for channel in ("msedge", "chrome", None):
                try:
                    browser = (
                        p.chromium.launch(channel=channel, headless=True)
                        if channel else p.chromium.launch(headless=True)
                    )
                except Exception:
                    continue
                try:
                    page = browser.new_page(
                        viewport={"width": 480, "height": 900}, device_scale_factor=2
                    )
                    page.goto(data_url, wait_until="domcontentloaded", timeout=20000)
                    try:
                        page.evaluate("() => document.fonts.ready")
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
                    el = page.locator("#invoice")
                    return el.screenshot(type="png")
                finally:
                    browser.close()
        return None
    except Exception:
        return None


def _default_out_path(tx: dict, settings: Settings) -> Path:
    ref = (tx.get("source") or {}).get("media_id") or "entry"
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return settings.repo_root / "media" / "invoices" / f"invoice_{ref}_{stamp}"


def _parse_when(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    try:
        return dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return dt.datetime.now(dt.timezone.utc)
