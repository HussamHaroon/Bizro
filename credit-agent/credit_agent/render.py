"""Printable loan-officer artifact — self-contained HTML, Khata Modern house style.

Inline CSS from dashboard/design-tokens/tokens.json (single source of truth). Every
interpolated value is HTML-escaped (bizro-security: model-extracted strings are
XSS vectors). Prints cleanly to PDF from a browser (no heavyweight PDF deps).
"""

from __future__ import annotations

import html
import json
import pathlib

_TOKENS_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "dashboard" / "design-tokens" / "tokens.json"
)


def _tokens() -> dict:
    with open(_TOKENS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _seal_svg(color: str) -> str:
    return (
        f'<svg class="seal" viewBox="0 0 40 40" width="34" height="34" role="img" '
        f'aria-label="AI verified"><circle cx="20" cy="20" r="17" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-dasharray="3 2"/>'
        f'<path d="M13 20l5 5 9-10" fill="none" stroke="{color}" stroke-width="2.5"/></svg>'
    )


BAND_COLORS = {
    "ready": "settledTeal",
    "nearly": "sealGold",
    "not_yet": "ledgerRed",
    "insufficient_data": "ruleLine",
}


def render_report_html(report: dict) -> str:
    t = _tokens()["color"]
    band = report.get("readiness", {}).get("band", "insufficient_data")
    band_color = t.get(BAND_COLORS.get(band, "ruleLine"), "#211E1A")
    mock = bool(report.get("mock"))
    merchant = report.get("merchant", {}).get("name", "Bizro Merchant")
    period = report.get("period", {})

    metrics_rows = "".join(
        f"<tr><td>{_esc(m.get('label_en'))} <span class='ur'>({_esc(m.get('label_ur'))})</span></td>"
        f"<td class='num'>{_esc(m.get('display'))}</td>"
        f"<td class='prov'>voice {_esc(m.get('provenance', {}).get('voice_pct', 0))}% · "
        f"photo {_esc(m.get('provenance', {}).get('photo_pct', 0))}% · "
        f"conf {_esc(m.get('provenance', {}).get('median_confidence'))}</td></tr>"
        for m in report.get("metrics", [])
    )

    def _line_row(li: dict) -> str:
        amount = f"PKR {li.get('amount_pkd', 0):,.0f}"
        conf = li.get("confidence")
        conf_disp = "—" if conf is None else str(conf)
        return (
            f"<tr><td>{_esc(li.get('label'))}</td>"
            f"<td class='num'>{_esc(amount)}</td>"
            f"<td>{_esc(li.get('source_type'))} · {_esc(li.get('source_model') or '—')}</td>"
            f"<td class='num'>{_esc(conf_disp)}</td></tr>"
        )

    line_rows = "".join(_line_row(li) for li in report.get("line_items", []))

    flags_html = "".join(
        f"<li>{_esc(f.get('note_en'))} — <span class='ur'>{_esc(f.get('note_ur'))}</span></li>"
        for f in report.get("red_flags", [])
    ) or "<li>None</li>"

    mock_banner = (
        f"<div class='mock'>MOCK DATA — synthesized without live model calls</div>"
        if mock else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Bizro Credit Readiness — {_esc(merchant)}</title>
<style>
  :root {{
    --ink-green:{t['inkGreen']}; --paper:{t['paperCream']}; --red:{t['ledgerRed']};
    --gold:{t['sealGold']}; --teal:{t['settledTeal']}; --ink:{t['inkBlack']};
    --rule:{t['ruleLine']}; --raised:{t['paperCreamRaised']};
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
         font:14px/1.55 "IBM Plex Sans","Noto Sans Arabic",sans-serif; padding:32px; }}
  .card {{ background:var(--raised); border:1px solid var(--rule); border-radius:6px;
           padding:20px 24px; margin-bottom:16px; max-width:820px; margin-inline:auto; }}
  h1 {{ font-size:20px; margin:0 0 2px; color:var(--ink-green); }}
  .sub {{ color:var(--ink); opacity:.75; font-size:13px; }}
  .ur {{ direction:rtl; unicode-bidi:isolate; }}
  .band {{ display:flex; align-items:center; gap:14px; margin:14px 0 4px; }}
  .score {{ font-family:"Zilla Slab","IBM Plex Sans",serif; font-size:44px;
            color:{band_color}; line-height:1; }}
  .num {{ font-family:"Zilla Slab","IBM Plex Sans",serif; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
  td,th {{ border-top:1px solid var(--rule); padding:7px 8px; text-align:left;
           vertical-align:top; }}
  th {{ border-top:none; font-size:12px; text-transform:uppercase; letter-spacing:.04em;
        opacity:.7; }}
  td.num {{ text-align:right; white-space:nowrap; }}
  .prov {{ font-size:12px; opacity:.7; }}
  .mock {{ background:var(--red); color:#fff; text-align:center; font-weight:600;
           padding:6px; border-radius:4px; margin-bottom:14px; }}
  .seal {{ vertical-align:-8px; margin-inline-start:8px; }}
  .foot {{ font-size:12px; opacity:.7; margin-top:10px; }}
  @media print {{ body{{padding:12mm}} .card{{break-inside:avoid}} }}
</style></head><body>
{mock_banner}
<div class="card">
  <h1>Credit Readiness Report {_seal_svg(t['sealGold'])}</h1>
  <div class="sub">{_esc(merchant)} · {_esc(period.get('start'))} → {_esc(period.get('end'))}</div>
  <div class="band"><div class="score">{_esc(report.get('readiness',{}).get('score'))}</div>
    <div><strong>{_esc(band.replace('_',' '))}</strong><br>
    <span class="ur">{_esc(report.get('readiness',{}).get('label_ur'))}</span></div></div>
</div>
<div class="card"><strong>Summary</strong>
  <p class="ur" style="line-height:2">{_esc(report.get('narrative_ur'))}</p></div>
<div class="card"><strong>Metrics</strong>
  <table><tr><th>Metric</th><th style="text-align:right">Value</th><th>Provenance</th></tr>
  {metrics_rows}</table></div>
<div class="card"><strong>Red flags</strong><ul>{flags_html}</ul></div>
<div class="card"><strong>Line items (audit trail)</strong>
  <table><tr><th>Item</th><th style="text-align:right">Amount</th><th>Source</th>
  <th style="text-align:right">Conf.</th></tr>{line_rows}</table>
  <div class="foot">Criteria basis: {_esc(report.get('criteria_basis'))} ·
  Model: {_esc(report.get('model'))} · Generated: {_esc(report.get('generated_at'))}</div>
</div>
</body></html>"""


def save_report_html(report: dict, out_path: str) -> str:
    html_text = render_report_html(report)
    pathlib.Path(out_path).write_text(html_text, encoding="utf-8")
    return out_path
