"""Branded WhatsApp invoice renderer — D4-1 "stamped-ledger" neobrutalism.

Owner ruling D4-1 (design.md §4 addendum, 2026-08-23) OVERRIDES the old
elevation rule for this surface: the invoice is now the strongest expression
of the stamp motif — ledger-cream canvas, 3px ink borders, hard offset
shadows (no blur, no gradients), radius <=2px, slab numerals BIG for the
amount, and the trust seal restyled as a rotated dashed RUBBER STAMP reading
"AI-PARSED" + confidence. §4.7 accessibility law is unchanged (icon+word,
digits AND words, color never the sole signal, AA contrast) — wording is now
SIMPLE ENGLISH everywhere (owner ruling 2026-09-04: all merchant-facing text
is simple English; only inbound voice notes stay Urdu).

Colors/fonts still come from dashboard/design-tokens/tokens.json (token law).
New D4-1 keys are read with `tokens.get(key, fallback)` so the renderer works
before/after the frontend-agent lands the additive token extension — existing
key names are never renamed. Rendered to PNG via Playwright using the SYSTEM
EDGE channel (verified working — voice-agent/notes.md §3); any failure falls
back to a plain-text receipt. Rendering NEVER blocks the confirmation text
path (SKILL.md deliverable 4).

Torn/perforated top edge appears HERE ONLY (khata-modern skill: reserved for
the WhatsApp invoice image) — restyled bolder under D4-1, still inside the
3px ink frame so it reads as a serrated ticket edge, not noise.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import string
from pathlib import Path

from voice_agent.config import Settings, load_settings
from voice_agent.confirmation import amount_in_english_words, to_numeral_digits

# ---------------------------------------------------------------------------
# Token loading (token law)
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict | None = None

# D4-1 fallback values for token keys the additive tokens.json extension will
# introduce. Single source of truth — tests import this to build the allowed
# color set. When tokens.json grows these keys, the file wins.
D4_TOKEN_FALLBACKS: dict[str, str] = {
    "ledgerCream": "#F5F1E6",   # canvas — ledger cream
    "ink": "#1F1B16",           # borders + text ink
    "goldAccent": "#E9A93D",    # gold accents (ink text on gold)
    "shadowHard": "5px 5px 0 #1F1B16",  # card — hard offset, zero blur
    "shadowHardSm": "3px 3px 0 #1F1B16",  # chips/stamp — same law, smaller
}


def load_tokens(settings: Settings | None = None) -> dict:
    global _TOKEN_CACHE
    if _TOKEN_CACHE is None:
        root = (settings or load_settings()).repo_root
        path = root / "dashboard" / "design-tokens" / "tokens.json"
        _TOKEN_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _TOKEN_CACHE


def _d4(tokens: dict, key: str) -> str:
    """D4-1 token with documented fallback (keys additive; never renamed)."""
    section, _, name = key.partition(".")
    return tokens.get(section, {}).get(name) or D4_TOKEN_FALLBACKS[name]


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
    # kind → (simple label, caps label, icon, direction word, color token key)
    "sale": ("Cash sale", "CASH SALE", "◈", "Money in", "settledTeal"),
    "expense": ("Expense", "EXPENSE", "▼", "Money out", "ledgerRed"),
    "udhar_given": ("Credit given", "UDHAR GIVEN", "▲", "Money out", "ledgerRed"),
    "udhar_settlement": ("Credit paid back", "SETTLEMENT", "✓", "Money in", "settledTeal"),
}

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Bolder D4-1 serration: 24px tall, 20px period (was 18px/15px), ink-green fill
# merging into the header band. Stays INSIDE the 3px ink frame (no fighting).
_TORN_PATH = (
    "M0,24 L0,12 L10,3 L30,13 L50,6 L70,15 L90,4 L110,14 L130,3 L150,13 L170,6 "
    "L190,15 L210,4 L230,14 L250,3 L270,13 L290,6 L310,15 L330,4 L350,14 L370,3 "
    "L390,13 L410,6 L430,15 L450,4 L470,14 L490,3 L510,13 L520,8 L520,24 Z"
)

_TEMPLATE = string.Template("""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Zilla+Slab:wght@500;700&family=Noto+Sans+Urdu:wght@400;700&family=Noto+Nastaliq+Urdu:wght@600&display=swap" rel="stylesheet">
<style>
  :root { }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:${ledgerCream}; font-family:${fontBody}; color:${ink};
         -webkit-font-smoothing:antialiased; }
  /* shot wrapper keeps the hard offset shadow inside the element screenshot */
  #shot { width:fit-content; margin:0 auto; padding:10px; background:${ledgerCream}; }
  #invoice { width:520px; background:${cardBg}; border:3px solid ${ink};
             border-radius:2px; box-shadow:${shadowHard}; overflow:hidden; }

  /* torn/perforated top edge — reserved flourish (HERE ONLY), bolder per D4-1 */
  .torn { display:block; width:100%; height:24px; }

  .head { background:${inkGreen}; color:${cardBg}; padding:14px 20px 12px;
          display:flex; justify-content:space-between; align-items:center;
          border-bottom:3px solid ${ink}; }
  .brand { line-height:1; direction:ltr; }
  .brand img { display:block; height:44px; width:auto; }
  .head-meta { font-size:12px; text-align:left; direction:ltr; line-height:1.7;
               font-family:${fontNumerals}; font-weight:600; opacity:.95; }
  .gold-strip { height:8px; background:${goldAccent}; border-bottom:3px solid ${ink}; }

  .greet { font-family:${fontDisplay}; font-size:18px; line-height:2.6;
           text-align:center; padding:16px 20px 4px; color:${ink}; }

  .kind { display:flex; align-items:center; gap:12px; justify-content:center;
          padding:8px 20px 12px; }
  .kind .icon { width:40px; height:40px; border-radius:2px; background:${kindColor};
                border:2px solid ${ink}; box-shadow:${shadowHardSm};
                color:${cardBg}; display:flex; align-items:center; justify-content:center;
                font-size:18px; font-family:${fontNumerals}; font-weight:700; }
  .kind .ur { font-size:22px; font-weight:700; color:${kindColor}; }
  .kind .en { font-size:11px; letter-spacing:2px; color:${ink}; direction:ltr;
              font-family:${fontNumerals}; font-weight:700;
              background:${goldAccent}; border:2px solid ${ink}; border-radius:2px;
              padding:3px 8px; }

  .amount { text-align:center; padding:4px 20px 16px; }
  .amount .digits { font-family:${fontNumerals}; font-size:78px; font-weight:700;
                    color:${kindColor}; direction:ltr; line-height:1.05; }
  .amount .digits .cur { font-size:26px; vertical-align:24px; color:${ink}; }
  .amount .words { font-size:16px; padding-top:4px; font-weight:600; }
  .amount .direction { font-size:13px; color:${ink}; opacity:.75; padding-top:3px; }

  table.items { width:100%; border-collapse:collapse; margin:0 0 8px; }
  table.items th { font-size:11px; font-weight:700; color:${ink};
                   border-top:2px solid ${ink}; border-bottom:2px solid ${ink};
                   padding:7px 12px; text-align:left; letter-spacing:1px; }
  table.items td { padding:8px 12px; border-bottom:1px solid ${ink}; font-size:13px; }
  table.items .num { font-family:${fontNumerals}; direction:ltr; text-align:left;
                     font-weight:600; }

  .meta { padding:12px 20px 4px; font-size:14px; line-height:2; }
  .meta b { font-weight:700; }

  /* trust seal → RUBBER STAMP (D4-1): dashed ink ring, rotated, AI-PARSED */
  .stamp-row { display:flex; align-items:center; gap:16px; padding:14px 20px 18px; }
  .stamp { transform:rotate(-6deg); flex:0 0 auto; direction:ltr; text-align:center;
           border:2px dashed ${stampInk}; border-radius:2px; padding:8px 14px;
           font-family:${fontNumerals}; background:transparent; }
  .stamp .t1 { font-size:17px; font-weight:700; letter-spacing:3px; color:${stampInk};
               text-transform:uppercase; }
  .stamp .t2 { font-size:11px; font-weight:600; letter-spacing:1px; color:${stampInk};
               margin-top:2px; }
  .stamp-copy .en { font-family:${fontNumerals}; letter-spacing:1.5px; color:${ink};
                    font-weight:700; direction:ltr; display:block; font-size:11px; }
  .stamp-copy .conf { color:${ink}; opacity:.75; font-size:12px; line-height:1.9; }
  .edit-hint { margin:0 20px 16px; padding:10px 12px; background:${goldAccent};
               border:2px solid ${ink}; border-radius:2px; box-shadow:${shadowHardSm};
               font-size:13px; line-height:1.9; font-weight:600; color:${ink}; }

  .foot { border-top:3px solid ${ink}; padding:10px 20px; font-size:11px;
          display:flex; justify-content:space-between; opacity:.85; }
  .mock-band { background:${ledgerRed}; color:${cardBg}; text-align:center;
               font-size:13px; font-weight:700; letter-spacing:4px; padding:6px 0;
               direction:ltr; border-top:3px solid ${ink};
               font-family:${fontNumerals}; }
</style>
</head>
<body>
  <div id="shot"><div id="invoice">
    <svg class="torn" viewBox="0 0 520 24" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <path d="${tornPath}" fill="${inkGreen}"/>
    </svg>
    <div class="head">
      <div class="brand"><img src="${logoDataUri}" alt="Bizro" height="44"></div>
      <div class="head-meta">${merchantHtml}<br>${dateHtml}</div>
    </div>
    <div class="gold-strip"></div>

    <div class="greet">Thank you! Your entry is saved.</div>

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

    <div class="stamp-row">
      <div class="stamp">
        <div class="t1">AI-PARSED</div>
        <div class="t2">${stampConfidence}</div>
      </div>
      <div class="stamp-copy">
        <span class="en">ALIBABA CLOUD &middot; AI-PARSED</span>
        <span class="conf">Voice entry — read by AI</span>
      </div>
    </div>

    <div class="edit-hint">Something wrong? Reply "0" to this message and we will remove the entry.</div>

    <div class="foot">
      <span>Bizro — your digital ledger</span>
      <span style="direction:ltr">${txRef}</span>
    </div>
    ${mockBand}
  </div></div>
</body>
</html>""")



def _logo_data_uri() -> str:
    """Cream wordmark as a data URI (green band needs cream letters)."""
    import base64
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "assets" / "brand" / "wordmark-cream-96.png"
    if not p.is_file():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

def build_invoice_html(tx: dict, tokens: dict, numeral_style: str = "western") -> str:
    color = tokens["color"]
    font = tokens["font"]
    kind = tx.get("kind") or "udhar_given"
    kind_label, kind_en, kind_icon, kind_dir, kind_color_key = _KIND_VIEW[kind]
    kind_color = color[kind_color_key]

    amount = float(tx.get("amount_pkr") or 0)
    esc = html.escape

    merchant = (tx.get("merchant") or {}).get("display_name") or ""
    merchant_html = esc(merchant) if merchant else "Ledger — Bizro"

    when = _parse_when(tx.get("occurred_at"))
    date_html = f"{to_numeral_digits(when.day, numeral_style)} {_MONTHS[when.month-1]} {to_numeral_digits(when.year, numeral_style)}"

    cp = tx.get("counterparty") or {}
    cp_name = (cp.get("name") or "").strip()
    cp_html = f"<b>Customer:</b> {esc(cp_name)}" if cp_name else ""
    if kind == "expense" and cp_name:
        cp_html = f"<b>Supplier:</b> {esc(cp_name)}"

    flag = tx.get("flag") or "none"
    low_conf_html = ""
    if flag != "none":
        warn = (
            "Not sure about this entry — please confirm it."
            if flag == "low_confidence"
            else "Note: the item totals do not match the amount."
            if flag == "total_mismatch"
            else "Note: this entry needs your attention."
        )
        low_conf_html = (
            f'<div style="margin-top:6px;padding:6px 10px;border:2px solid {color["ledgerRed"]};'
            f'border-radius:2px;box-shadow:{_d4(tokens, "shadow.shadowHardSm")};'
            f'color:{color["ledgerRed"]};font-size:12px;line-height:1.9;font-weight:600">⚠ {warn}</div>'
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
            "<tr><th>Item</th><th style='text-align:left;direction:ltr'>Qty</th>"
            "<th style='text-align:left;direction:ltr'>Rate</th>"
            "<th style='text-align:left;direction:ltr'>Total</th></tr>"
            f"{rows}</table>"
        )

    src = tx.get("source") or {}
    conf = src.get("confidence")
    conf_pct = to_numeral_digits(int(round(conf * 100)), numeral_style) if isinstance(conf, (int, float)) else None
    stamp_conf = f"AI confidence {conf_pct}%" if conf_pct is not None else "AI confidence —"

    # Rubber-stamp ink: red when the entry needs attention, green when clean
    # (color + flag wording both signal — §4.7 color never the sole signal).
    stamp_ink = color["ledgerRed"] if flag != "none" else color["inkGreen"]

    mock_band = '<div class="mock-band">MOCK DATA — NOT A REAL ENTRY</div>' if tx.get("mock") else ""

    logo_uri = _logo_data_uri()
    return _TEMPLATE.substitute(
        logoDataUri=logo_uri,
        ledgerCream=_d4(tokens, "color.ledgerCream"),
        ink=_d4(tokens, "color.ink"),
        goldAccent=_d4(tokens, "color.goldAccent"),
        shadowHard=_d4(tokens, "shadow.shadowHard"),
        shadowHardSm=_d4(tokens, "shadow.shadowHardSm"),
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
        tornPath=_TORN_PATH,
        merchantHtml=merchant_html,
        dateHtml=date_html,
        kindUr=kind_label, kindEn=kind_en, kindIcon=kind_icon, kindDirection=kind_dir,
        amountDigits=to_numeral_digits(amount, numeral_style),
        amountWords=f"{amount_in_english_words(amount)} rupees",
        itemsHtml=items_html,
        counterpartyHtml=cp_html,
        lowConfidenceHtml=low_conf_html,
        stampInk=stamp_ink,
        stampConfidence=stamp_conf,
        txRef=esc(str(tx.get("source", {}).get("media_id") or "voice-entry")),
        mockBand=mock_band,
    )


# ---------------------------------------------------------------------------
# Text fallback (ledger-style plain receipt)
# ---------------------------------------------------------------------------


def build_invoice_text(tx: dict, numeral_style: str = "western") -> str:
    kind = tx.get("kind") or "udhar_given"
    kind_label, kind_en, _icon, kind_dir, _c = _KIND_VIEW[kind]
    amount = float(tx.get("amount_pkr") or 0)
    cp = (tx.get("counterparty") or {}).get("name") or ""
    when = _parse_when(tx.get("occurred_at"))
    digits = to_numeral_digits(amount, numeral_style)
    words = amount_in_english_words(amount)

    lines = [
        "*Bizro — Receipt*",
        f"{kind_label} ({kind_en}) — {kind_dir}",
        f"Amount: Rs. {digits} ({words} rupees)",
    ]
    if cp:
        lines.append(f"Customer: {cp}")
    if tx.get("item_lines"):
        lines.append("—")
        for li in tx["item_lines"]:
            lines.append(
                f"{li.get('item','')} ×{to_numeral_digits(li.get('qty',0), numeral_style)}"
                f" = {to_numeral_digits(li.get('line_total',0), numeral_style)}"
            )
    lines += [
        "—",
        f"Date: {to_numeral_digits(when.day, numeral_style)} {_MONTHS[when.month-1]} {to_numeral_digits(when.year, numeral_style)}",
        "AI-PARSED · Alibaba Cloud AI Verified — reply 0 if this is wrong.",
    ]
    if (tx.get("flag") or "none") != "none":
        lines.append("⚠ Not sure about this entry — please confirm it.")
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
                        viewport={"width": 560, "height": 1400}, device_scale_factor=2
                    )
                    page.goto(data_url, wait_until="domcontentloaded", timeout=20000)
                    try:
                        page.evaluate("() => document.fonts.ready")
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
                    # shoot the wrapper so the 5px hard shadow stays in frame
                    el = page.locator("#shot")
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
