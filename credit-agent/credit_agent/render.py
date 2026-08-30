"""Printable loan-officer artifact — self-contained HTML, D4-1 "stamped-ledger"
neobrutalism (binding art direction, design.md §4 top addendum).

Canvas ledger-paper `#F5F1E6`, ink `#1F1B16` text + 3px borders, hard offset
shadows (`5px 5px 0`, no blur, no gradients), radius <=2px, khata semantic fills
(green/red/gold/teal). The trust seal is a rubber stamp: dashed 2px ink border,
rotated -4deg, uppercase "AI-PARSED". Prints cleanly to PDF from a browser —
@media print flattens hard shadows to plain borders (toner-friendly).

Tokens: dashboard/design-tokens/tokens.json is read when keys exist, but every
D4-1 value below has an inline default (tokens.get(key, fallback)) — the token
file's D4-1 keys are being extended additively on another branch; do not rely
on their presence. Key names match the D4-1 extension (color.paper, inkLine,
greenFill/redFill/goldFill/tealFill, elevation.hardMd/borderCard, font.*).
Radius stays hardcoded at 2px: the D4-1 cap (<=2px) is binding even where the
not-yet-merged token file still carries the old 6px value.

Every interpolated value is HTML-escaped (bizro-security: model-extracted
strings are XSS vectors).
"""

from __future__ import annotations

import html
import json
import pathlib
from string import Template

_TOKENS_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "dashboard" / "design-tokens" / "tokens.json"
)

# D4-1 "stamped-ledger" palette — inline defaults so this file is self-sufficient.
D4 = {
    "paper": "#F5F1E6",        # ledger-paper canvas
    "raised": "#FCF9F0",       # card surface
    "ink": "#1F1B16",          # text + borders + hard shadow
    "green": "#0B5D3B",        # semantic fill — white text on it
    "red": "#A6332B",          # semantic fill — white text on it
    "gold": "#E9A93D",         # semantic fill — ink text on it
    "teal": "#1F7A6C",         # semantic fill — white text on it
    "border": "3px solid #1F1B16",
    "hard": "5px 5px 0 #1F1B16",
    "hard_sm": "3px 3px 0 #1F1B16",
    "radius": "2px",
    "numerals": '"Zilla Slab","IBM Plex Sans",serif',
    "body": '"IBM Plex Sans","Noto Sans Urdu","Noto Sans Arabic",sans-serif',
}


def _tokens() -> dict:
    try:
        with open(_TOKENS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}  # self-sufficient: D4-1 defaults below carry the render


def _d4() -> dict:
    """Merge token file (additive D4-1 keys, when present) over inline defaults."""
    t = _tokens()
    color, font, elev = t.get("color", {}), t.get("font", {}), t.get("elevation", {})
    v = dict(D4)
    v["paper"] = color.get("paper", D4["paper"])
    v["raised"] = color.get("paperRaised", D4["raised"])
    v["ink"] = color.get("inkLine", D4["ink"])
    v["green"] = color.get("greenFill", color.get("inkGreen", D4["green"]))
    v["red"] = color.get("redFill", color.get("ledgerRed", D4["red"]))
    v["gold"] = color.get("goldFill", D4["gold"])
    v["teal"] = color.get("tealFill", color.get("settledTeal", D4["teal"]))
    v["border"] = elev.get("borderCard", D4["border"])
    v["hard"] = elev.get("hardMd", D4["hard"])
    v["hard_sm"] = elev.get("hardSm", D4["hard_sm"])
    v["numerals"] = font.get("numerals", D4["numerals"])
    v["body"] = font.get("body", D4["body"])
    return v


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


# band -> (merged-palette key, text color on that fill) — color never the sole
# signal: the band is also spelled out in words (EN + Urdu) beside the chip.
BAND_FILLS = {
    "ready": ("green", "#FFFFFF"),
    "nearly": ("gold", D4["ink"]),
    "not_yet": ("red", "#FFFFFF"),
    "insufficient_data": ("raised", D4["ink"]),
}


def _stamp(extra_class: str = "") -> str:
    """Rubber stamp — the D4-1 trust seal: dashed ink border, -4deg, uppercase."""
    cls = f"stamp {extra_class}".strip()
    return (
        f'<span class="{cls}" role="img" aria-label="AI-parsed seal">AI-PARSED</span>'
    )


_CSS = Template("""
  * { box-sizing:border-box; }
  body { margin:0; background:$paper; color:$ink;
         font:14px/1.55 $body; padding:34px 26px; }
  .sheet { max-width:860px; margin-inline:auto; }
  .card { background:$raised; border:$border; border-radius:$radius;
          box-shadow:$hard; padding:22px 26px; margin-bottom:26px; }
  h1 { font-family:$numerals; font-size:22px; margin:0; letter-spacing:.02em;
       text-transform:uppercase; }
  .headrow { display:flex; align-items:flex-start; justify-content:space-between;
             gap:14px; }
  .sub { font-size:13px; margin-top:4px; font-weight:600; }
  .ur { direction:rtl; unicode-bidi:isolate; }
  .stamp { display:inline-block; border:2px dashed $ink; color:$ink;
           text-transform:uppercase; font-weight:700; letter-spacing:.1em;
           font-size:12px; padding:5px 12px; border-radius:$radius;
           transform:rotate(-4deg); white-space:nowrap; flex:none; }
  .band { display:flex; align-items:center; gap:20px; margin-top:18px; }
  .score { font-family:$numerals; font-size:54px; line-height:1;
           display:inline-block; padding:10px 24px; border:$border;
           border-radius:$radius; box-shadow:$hard_sm; }
  .bandlabel { font-family:$numerals; font-size:20px; text-transform:uppercase;
               letter-spacing:.03em; font-weight:700; }
  .num { font-family:$numerals; }
  table { width:100%; border-collapse:collapse; margin-top:12px; }
  td,th { border-top:2px solid $ink; padding:8px 10px; text-align:left;
          vertical-align:top; }
  th { border-top:none; border-bottom:$border; font-size:11px;
       text-transform:uppercase; letter-spacing:.06em; text-align:left; }
  td.num, th.num { text-align:right; white-space:nowrap; }
  .prov { font-size:12px; }
  .mock { background:$red; color:#FFFFFF; text-align:center; font-weight:700;
          text-transform:uppercase; letter-spacing:.06em; padding:8px;
          border:$border; border-radius:$radius; box-shadow:$hard_sm;
          margin-bottom:22px; }
  .flags li { border-left:6px solid $red; padding-left:12px; margin:8px 0;
              font-weight:600; }
  .cardhead { display:flex; align-items:center; justify-content:space-between;
              gap:14px; }
  .cardhead strong { font-family:$numerals; font-size:15px; text-transform:uppercase;
                     letter-spacing:.04em; }
  .foot { font-size:12px; margin-top:12px; padding-top:8px; border-top:2px solid $ink; }
  /* print: flatten hard shadows to plain borders, un-rotate the stamp (D4-1 ④) */
  @media print {
    body { padding:10mm; background:#FFFFFF; }
    .card, .score, .mock { box-shadow:none; }
    .stamp { transform:none; }
    .card { break-inside:avoid; }
  }
""")


def render_report_html(report: dict) -> str:
    v = _d4()
    band = report.get("readiness", {}).get("band", "insufficient_data")
    fill_vkey, fill_text = BAND_FILLS.get(band, BAND_FILLS["insufficient_data"])
    band_fill = v[fill_vkey]
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

    css = _CSS.substitute(
        paper=v["paper"], raised=v["raised"], ink=v["ink"], border=v["border"],
        hard=v["hard"], hard_sm=v["hard_sm"], radius=v["radius"],
        numerals=v["numerals"], body=v["body"], red=v["red"],
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Bizro Credit Readiness — {_esc(merchant)}</title>
<style>{css}</style></head><body>
<div class="sheet">
{mock_banner}
<div class="card">
  <div class="headrow"><h1>Credit Readiness Report</h1>{_stamp()}</div>
  <div class="sub">{_esc(merchant)} · {_esc(period.get('start'))} → {_esc(period.get('end'))}</div>
  <div class="band"><div class="score" style="background:{band_fill};color:{fill_text}">{_esc(report.get('readiness',{}).get('score'))}</div>
    <div><div class="bandlabel">{_esc(band.replace('_',' '))}</div>
    <span class="ur">{_esc(report.get('readiness',{}).get('label_ur'))}</span></div></div>
</div>
<div class="card"><div class="cardhead"><strong>Summary</strong></div>
  <p class="ur" style="line-height:2">{_esc(report.get('narrative_ur'))}</p></div>
<div class="card"><div class="cardhead"><strong>Metrics</strong></div>
  <table><tr><th>Metric</th><th class="num">Value</th><th>Provenance</th></tr>
  {metrics_rows}</table></div>
<div class="card"><div class="cardhead"><strong>Red flags</strong></div><ul class="flags">{flags_html}</ul></div>
<div class="card"><div class="cardhead"><strong>Line items (audit trail)</strong>{_stamp()}</div>
  <table><tr><th>Item</th><th class="num">Amount</th><th>Source</th>
  <th class="num">Conf.</th></tr>{line_rows}</table>
  <div class="foot">Criteria basis: {_esc(report.get('criteria_basis'))} ·
  Model: {_esc(report.get('model'))} · Generated: {_esc(report.get('generated_at'))}</div>
</div>
</div></body></html>"""


def save_report_html(report: dict, out_path: str) -> str:
    html_text = render_report_html(report)
    pathlib.Path(out_path).write_text(html_text, encoding="utf-8")
    return out_path
