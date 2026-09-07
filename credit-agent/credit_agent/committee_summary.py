"""One-page committee summary — the artifact a lending committee actually
reads (schema.md §12). Single self-contained print HTML: identity block,
readiness band + score, corroboration headline, top metrics, aging summary,
top-5 flags/notices, limitations footer, ledger-chain statement + QR.

Design rules inherited from the audit trail:
- every number comes from the report dict (already computed in plain Python);
  this module does NO arithmetic beyond display formatting;
- every interpolated string is HTML-escaped (model-extracted text is an XSS
  vector);
- no raw ISO dates on the page — formatting.py human labels only;
- the readiness score renders with its honest label: "readiness indicator
  (not a validated repayment predictor)";
- the ledger chain statement is read from the DB mirror (latest transaction
  entry_hash, server §11): NULL → "chain: not yet sealed", never a claim of
  integrity we cannot see.

The QR encodes the verification anchor (merchant id + chain tail hash) so a
committee member can check the sealed ledger against the server; when the
`qrcode` package is unavailable the hash degrades to text and the QR is
honestly marked pending.
"""

from __future__ import annotations

import base64
import html
import io
import uuid

from .formatting import format_date_label, format_datetime_label
from .rubric import INDICATOR_NOTE, LIMITATIONS

# Same D4-1 stamped-ledger palette as render.py — duplicated inline so this
# module stays self-contained (render.py may evolve independently).
PAPER, RAISED, INK = "#F5F1E6", "#FCF9F0", "#1F1B16"
GREEN, RED, GOLD, TEAL = "#0B5D3B", "#A6332B", "#E9A93D", "#1F7A6C"
BORDER = "3px solid #1F1B16"

BAND_FILLS = {
    "ready": (GREEN, "#FFFFFF"),
    "nearly": (GOLD, INK),
    "not_yet": (RED, "#FFFFFF"),
    "insufficient_data": (RAISED, INK),
}

# Shown when an older payload predates report_json.limitations (§12 added
# the key): the single source of truth is rubric.LIMITATIONS — same four
# standing limitations the report payload stores.
DEFAULT_LIMITATIONS = LIMITATIONS

VISIT_PLACEHOLDER = "capture on visit"
CHAIN_UNSEALED = "chain: not yet sealed"

MAX_NOTICES = 5


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def chain_tail(merchant_id, db_url: str | None = None) -> dict:
    """Latest transaction's entry_hash for this merchant, via the read-only
    mirror. NULL (or no rows) → not sealed. Read-only: this module never
    seals, never writes."""
    from sqlalchemy import select

    from .db_view import Transaction, get_sessionmaker

    mid = merchant_id if isinstance(merchant_id, uuid.UUID) else uuid.UUID(str(merchant_id))
    Session = get_sessionmaker(db_url)
    with Session() as session:
        row = session.execute(
            select(Transaction.entry_hash)
            .where(Transaction.merchant_id == mid)
            .order_by(Transaction.occurred_at.desc())
            .limit(1)
        ).first()
    h = row[0] if row else None
    return {"sealed": h is not None, "entry_hash": h}


def _qr_data_uri(payload: str) -> str | None:
    """QR PNG as a data URI, or None when the qrcode package is missing —
    the caller then shows the hash as text and marks the QR pending."""
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(payload, box_size=3, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render_committee_summary_html(report: dict, db_url: str | None = None) -> str:
    merchant = report.get("merchant", {})
    mname = merchant.get("name") or "Bizro Merchant"
    mid = merchant.get("id", "")
    period = report.get("period", {})
    readiness = report.get("readiness", {})
    band = readiness.get("band", "insufficient_data")
    fill, text_on_fill = BAND_FILLS.get(band, BAND_FILLS["insufficient_data"])
    trust = report.get("trust") or {}
    officer = report.get("officer") or {}
    metrics = {m.get("key"): m for m in report.get("metrics", [])}

    def metric_display(key: str) -> str:
        m = metrics.get(key)
        return m.get("display") if m else "—"

    # --- corroboration headline ------------------------------------------------
    if trust:
        tier_rev = trust.get("revenue_by_tier") or {}
        corr = float(tier_rev.get("customer_confirmed", 0.0)) + float(
            tier_rev.get("third_party", 0.0)
        )
        total = trust.get("total_revenue_pkr")
        if total is None:
            total = sum(float(v) for v in tier_rev.values())
        trust_line = (
            f"<strong>{_esc(trust.get('corroboration_pct', 0))}%</strong> corroborated "
            f"revenue (PKR {_esc(f'{corr:,.0f}')} of PKR {_esc(f'{float(total or 0):,.0f}')})"
        )
    else:
        trust_line = "corroboration not yet measured for this report"

    # --- aging summary -----------------------------------------------------------
    ag = (officer.get("aging") or {})
    aging_bits = []
    for b in ag.get("buckets") or []:
        amt = _esc(f"{float(b.get('total', 0)):,.0f}")
        aging_bits.append(f"{_esc(b.get('bucket'))}d PKR {amt}")
    aging_line = " · ".join(aging_bits) if aging_bits else "no outstanding udhar"

    col = officer.get("collection") or {}
    rate = col.get("rate")
    rate_disp = "—" if rate is None else f"{float(rate) * 100:.0f}%"

    # --- top-5 flags/notices ------------------------------------------------------
    notices: list[str] = []
    for f in report.get("red_flags", []):
        notices.append(str(f.get("note_en") or f.get("flag")))
    dq = report.get("data_quality") or {}
    for n in dq.get("indicators") or []:
        notices.append(str(n))
    notices = notices[:MAX_NOTICES]
    notices_html = (
        "<ul>" + "".join(f"<li>{_esc(n)}</li>" for n in notices) + "</ul>"
        if notices
        else "<p>no flags or notices recorded</p>"
    )

    # --- limitations footer ---------------------------------------------------------
    limitations = report.get("limitations") or DEFAULT_LIMITATIONS
    limitations_html = "".join(f"<li>{_esc(x)}</li>" for x in limitations)

    # --- ledger chain statement + QR ---------------------------------------------------
    try:
        tail = chain_tail(mid, db_url)
    except Exception:
        tail = {"sealed": False, "entry_hash": None}  # mirror unavailable: honest default
    h = tail.get("entry_hash")
    if tail.get("sealed") and h:
        chain_line = (
            f"Ledger chain sealed — latest entry hash {_esc(str(h)[:16])}… "
            "(tamper-evident: any later edit is detectable server-side)"
        )
        qr_payload = f"bizro-verify:{mid}:{h}"
    else:
        chain_line = f"Ledger {CHAIN_UNSEALED} — entries not yet hash-sealed by the server"
        qr_payload = f"bizro-verify:{mid}:unsealed"

    qr = _qr_data_uri(qr_payload)
    if qr:
        qr_html = f"<img src='{qr}' alt='verification QR' width='110' height='110'>"
    else:
        qr_html = (
            "<div class='qrtext'>QR pending — qrcode package unavailable; "
            f"verification payload: {_esc(qr_payload)}</div>"
        )

    generated = report.get("generated_at_display") or format_datetime_label(
        report.get("generated_at")
    )
    period_label = period.get("label") or format_range_fallback(period)

    # §6.3: a report layer must surface the mock marker wherever it is present —
    # the committee one-pager is a report layer, same rule the full report
    # (render.py mock banner) already follows.
    mock_banner = (
        "<div class='mockband'>MOCK DATA — synthesized without live model calls</div>"
        if report.get("mock") else ""
    )

    css = f"""
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:{PAPER}; color:{INK};
         font:12.5px/1.45 "IBM Plex Sans","Noto Sans Urdu",sans-serif;
         padding:24px 20px; }}
  .sheet {{ max-width:780px; margin-inline:auto; }}
  .card {{ background:{RAISED}; border:{BORDER}; border-radius:2px;
           box-shadow:4px 4px 0 {INK}; padding:14px 18px; margin-bottom:14px; }}
  h1 {{ font-family:"Zilla Slab",serif; font-size:17px; margin:0;
        text-transform:uppercase; letter-spacing:.02em; }}
  h2 {{ font-family:"Zilla Slab",serif; font-size:12px; margin:0 0 6px;
        text-transform:uppercase; letter-spacing:.05em; }}
  table {{ width:100%; border-collapse:collapse; }}
  td,th {{ border-top:2px solid {INK}; padding:4px 8px; text-align:left; }}
  th {{ border-top:none; border-bottom:2px solid {INK}; font-size:10px;
       text-transform:uppercase; letter-spacing:.05em; }}
  .headrow {{ display:flex; justify-content:space-between; gap:12px;
              align-items:flex-start; }}
  .band {{ display:flex; align-items:center; gap:14px; margin-top:10px; }}
  .score {{ font-family:"Zilla Slab",serif; font-size:34px; line-height:1;
            padding:6px 14px; border:{BORDER}; border-radius:2px; }}
  .bandlabel {{ font-family:"Zilla Slab",serif; font-size:14px;
                text-transform:uppercase; font-weight:700; }}
  .note {{ font-size:10.5px; font-style:italic; }}
  .ur {{ direction:rtl; unicode-bidi:isolate; }}
  .mockband {{ background:{RED}; color:#FFFFFF; text-align:center;
               font-weight:700; text-transform:uppercase; letter-spacing:.06em;
               padding:8px; border:{BORDER}; border-radius:2px;
               box-shadow:4px 4px 0 {INK}; margin-bottom:14px; }}
  ul {{ margin:4px 0; padding-left:18px; }}
  li {{ margin:2px 0; }}
  .chain {{ font-size:11px; }}
  .limitations {{ font-size:10.5px; background:{PAPER}; }}
  .limitations li {{ margin:1px 0; }}
  .foot {{ font-size:10px; margin-top:8px; padding-top:6px;
           border-top:2px solid {INK}; }}
  .qrtext {{ width:110px; height:110px; border:2px dashed {INK};
             font-size:8.5px; padding:6px; overflow:hidden; }}
  @media print {{
    body {{ padding:0; background:#FFFFFF; }}
    .card {{ box-shadow:none; break-inside:avoid; }}
    .sheet {{ max-width:none; }}
  }}
"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Bizro Committee Summary — {_esc(mname)}</title>
<style>{css}</style></head><body>
<div class="sheet">
{mock_banner}
<div class="card">
  <div class="headrow"><h1>Committee Summary</h1>
    <span class="ur">کمیٹی کے لیے خلاصہ</span></div>
  <h2>Applicant</h2>
  <table>
    <tr><th>Name</th><td>{_esc(mname)}</td>
        <th>City</th><td>{VISIT_PLACEHOLDER}</td></tr>
    <tr><th>CNIC</th><td>{VISIT_PLACEHOLDER}</td>
        <th>Years trading</th><td>{VISIT_PLACEHOLDER}</td></tr>
    <tr><th>Period reviewed</th><td colspan="3">{_esc(period_label)}</td></tr>
  </table>
  <div class="band"><div class="score" style="background:{fill};color:{text_on_fill}">{_esc(readiness.get('score'))}</div>
    <div><div class="bandlabel">{_esc(band.replace('_', ' '))}</div>
    <div class="note">{INDICATOR_NOTE}</div></div></div>
  <p class="chain">{trust_line}</p>
</div>

<div class="card"><h2>Top metrics</h2>
  <table>
    <tr><th>Total entries</th><td class="n">{_esc(metric_display('entries'))}</td>
        <th>Months of records</th><td class="n">{_esc(metric_display('months'))}</td></tr>
    <tr><th>Net cash-flow</th><td class="n">{_esc(metric_display('cashflow'))}</td>
        <th>Udhar outstanding</th><td class="n">{_esc(metric_display('udhar'))}</td></tr>
    <tr><th>Collection rate</th><td class="n">{_esc(rate_disp)}</td>
        <th>Weekly consistency</th><td class="n">{_esc(metric_display('consistency'))}</td></tr>
  </table>
</div>

<div class="card"><h2>Receivables aging</h2>
  <p>{aging_line}</p>
</div>

<div class="card"><h2>Flags &amp; notices (top {min(MAX_NOTICES, len(notices)) or 0})</h2>
  {notices_html}
</div>

<div class="card chain">
  <h2>Ledger chain</h2>
  <div class="headrow"><p class="chain" style="flex:1">{chain_line}</p>{qr_html}</div>
</div>

<div class="card limitations">
  <h2>Limitations — read before deciding</h2>
  <ul>{limitations_html}</ul>
  <div class="foot">Generated: {_esc(generated)} ·
    Period: {_esc(period.get('start_display') or format_date_label(period.get('start')))} – {_esc(period.get('end_display') or format_date_label(period.get('end')))} ·
    {_esc(report.get('criteria_basis', 'criteria basis not recorded'))}</div>
</div>
</div></body></html>"""


def format_range_fallback(period: dict) -> str:
    """Period label for payloads missing the preformatted one."""
    start, end = period.get("start"), period.get("end")
    if start and end:
        return f"{format_date_label(start)} - {format_date_label(end)}"
    return "period not recorded"
