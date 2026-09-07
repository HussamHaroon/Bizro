"""Build docs/Bizro_Guide.pdf — the Deep Guide as a print-ready A4 PDF.

Style: NEOBRUTALIST / "Khata Modern" — the project's own design language
(site/src/styles.css + presentation/build_pitch.py), not a generic template:
cream paper, 3pt ink borders, hard offset ink shadows, gold/green/red/teal
stickers, Arial Black slabs.

Source of truth: docs/GUIDE.md (kept locally; *.md is gitignored by design).
Run from the repo root:

    python docs/build_guide_pdf.py

Pipeline (document-skills/pdf Report route with a documented deviation):
  1. body.pdf  — ReportLab Platypus, clickable auto-TOC (multiBuild), no cover
  2. cover.pdf — canvas-drawn neobrutalist cover (cover_render templates 01-09
                 have no neobrutalist variant; project tokens are authoritative)
  3. merge     — cover inserted as page 1 -> docs/Bizro_Guide.pdf

Palette = Khata Modern tokens (verbatim from site/src/styles.css / deck):
  cream #F5F1E6 · paper #FBF8F0 · ink #1F1B16 · green #0B5D3B ·
  red #A6332B · gold #E9A93D · teal #1F7A6C · shadows 3/5/8px ink offsets.
"""

from __future__ import annotations

import hashlib
import html
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BODY_PDF = os.path.join(REPO, "docs", "_guide_body.pdf")
COVER_PDF = os.path.join(REPO, "docs", "_guide_cover.pdf")
FINAL_PDF = os.path.join(REPO, "docs", "Bizro_Guide.pdf")

# ━━ Khata Modern tokens (project design system — see module docstring) ━━
CREAM = colors.HexColor("#F5F1E6")
PAPER = colors.HexColor("#FBF8F0")
INK = colors.HexColor("#1F1B16")
GREEN = colors.HexColor("#0B5D3B")
RED = colors.HexColor("#A6332B")
GOLD = colors.HexColor("#E9A93D")
TEAL = colors.HexColor("#1F7A6C")
SHADOW = INK  # hard offset shadows are always ink, never blurred

# ── Fonts (Windows host) ────────────────────────────────────────────────────
F = os.path.join("C:", os.sep, "Windows", "Fonts")
pdfmetrics.registerFont(TTFont("ArialBlack", os.path.join(F, "ariblk.ttf")))
pdfmetrics.registerFont(TTFont("Verdana", os.path.join(F, "verdana.ttf")))
pdfmetrics.registerFont(TTFont("Verdana-Bold", os.path.join(F, "verdanab.ttf")))
pdfmetrics.registerFont(TTFont("Consolas", os.path.join(F, "consola.ttf")))
pdfmetrics.registerFont(TTFont("Consolas-Bold", os.path.join(F, "consolab.ttf")))
registerFontFamily("Verdana", normal="Verdana", bold="Verdana-Bold")
registerFontFamily("Consolas", normal="Consolas", bold="Consolas-Bold")
registerFontFamily("ArialBlack", normal="ArialBlack", bold="ArialBlack")

SLAB = "ArialBlack"      # headings / stickers (the deck's SLAB face)
BODY_FONT = "Verdana"    # body (closest host grotesque to IBM Plex Sans)
CODE_FONT = "Consolas"

PAGE_W, PAGE_H = A4
MARGIN = 1.9 * cm
AVAIL_W = PAGE_W - 2 * MARGIN

# ── Styles ──────────────────────────────────────────────────────────────────
h2_style = ParagraphStyle(
    "H2", fontName=BODY_FONT, fontSize=11, leading=15, textColor=GREEN,
    spaceBefore=13, spaceAfter=2,
)
body_style = ParagraphStyle(
    "Body", fontName=BODY_FONT, fontSize=9.5, leading=15, textColor=INK,
    alignment=TA_LEFT, spaceBefore=0, spaceAfter=7,
)
lead_style = ParagraphStyle("Lead", parent=body_style, textColor=INK)
bullet_style = ParagraphStyle(
    "Bullet", parent=body_style, leftIndent=14, bulletIndent=3, spaceAfter=5,
)
numbered_style = ParagraphStyle(
    "Numbered", parent=body_style, leftIndent=20, firstLineIndent=-13,
    spaceAfter=7,
)
code_style = ParagraphStyle(
    "Code", fontName=CODE_FONT, fontSize=8.5, leading=12.5, textColor=INK,
    alignment=TA_LEFT,
)
h1_text_style = ParagraphStyle(
    "H1Text", fontName=SLAB, fontSize=13.5, leading=17, textColor=INK,
)
tbl_header_style = ParagraphStyle(
    "TblHeader", fontName=BODY_FONT, fontSize=8.5, leading=11,
    textColor=CREAM, alignment=TA_LEFT,
)
tbl_cell_style = ParagraphStyle(
    "TblCell", fontName=BODY_FONT, fontSize=8.5, leading=12, textColor=INK,
    alignment=TA_LEFT,
)
caption_style = ParagraphStyle(
    "Caption", fontName=BODY_FONT, fontSize=7.5, leading=10, textColor=INK,
)
toc_title_style = ParagraphStyle(
    "TocTitle", fontName=SLAB, fontSize=13.5, leading=17, textColor=INK,
)

MAX_KEEP_HEIGHT = A4[1] * 0.4


def safe_keep_together(elements):
    total_h = 0
    for el in elements:
        _, h = el.wrap(AVAIL_W, A4[1])
        total_h += h
    if total_h <= MAX_KEEP_HEIGHT:
        return [KeepTogether(elements)]
    if len(elements) >= 2:
        return [KeepTogether(elements[:2])] + list(elements[2:])
    return list(elements)


# ━━ Neobrutalist primitives ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def neo_panel(content, bg=PAPER, border=2.5, shadow=4, pad=(7, 11), width=None):
    """Ink-bordered panel with a hard ink offset shadow.

    The shadow is faked with an outer 1-cell table filled ink: the inner
    panel sits at the cell's top-left, so the ink shows as a right/bottom
    offset slab (reportlab has no native SHADOW table command).
    `content` is a flowable or a list of flowables in one cell.
    """
    w = width if width is not None else AVAIL_W * 0.97
    t, b = pad
    inner = Table([[content]], colWidths=[w], hAlign="LEFT")
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), border, INK),
        ("TOPPADDING", (0, 0), (-1, -1), t),
        ("BOTTOMPADDING", (0, 0), (-1, -1), b),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
    ]))
    outer = Table([[inner]], colWidths=[w + shadow], hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SHADOW),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), shadow),
        ("BOTTOMPADDING", (0, 0), (-1, -1), shadow),
    ]))
    return outer


def mono(text: str) -> str:
    return f'<font face="{CODE_FONT}" size="8.6">{html.escape(text)}</font>'


def link(url: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}" color="#1F7A6C"><u>{html.escape(url)}</u></a>'


def heading(story, text, level=0):
    key = "h_" + hashlib.md5(text.encode()).hexdigest()[:8]
    if level == 0:
        story.append(CondPageBreak((PAGE_H - 2 * MARGIN) * 0.15))
        story.append(Spacer(1, 8))
        banner = neo_panel(
            [Paragraph(f'{html.escape(text.upper())}', h1_text_style)],
            bg=GOLD, border=3, shadow=5, pad=(8, 8), width=AVAIL_W * 0.97,
        )
        story.append(banner)
        # bookmark carrier: invisible paragraph right after the banner holds
        # the TOC anchor + attrs (the banner itself is a Table, not a Paragraph)
        carrier = Paragraph(
            f'<a name="{key}"/><font size="1"> </font>',
            ParagraphStyle("Carrier", fontName=BODY_FONT, fontSize=1, leading=1),
        )
        carrier.bookmark_name = text
        carrier.bookmark_level = 0
        carrier.bookmark_text = text
        carrier.bookmark_key = key
        story.append(carrier)
        story.append(Spacer(1, 10))
    else:
        p = Paragraph(f'<a name="{key}"/><b>{text}</b>', h2_style)
        p.bookmark_name = text
        p.bookmark_level = 1
        p.bookmark_text = text
        p.bookmark_key = key
        story.append(p)
        story.append(HRFlowable(width="100%", thickness=1.6, color=INK,
                                spaceBefore=1, spaceAfter=8))


def para(story, text, style=body_style):
    story.append(Paragraph(text, style))


def bullets(story, items):
    for it in items:
        story.append(Paragraph(it, bullet_style, bulletText="■"))
    story.append(Spacer(1, 2))


def numbered(story, items):
    for i, it in enumerate(items, 1):
        story.append(Paragraph(f"<b>{i}.</b> {it}", numbered_style))
    story.append(Spacer(1, 2))


def codeblock(story, code: str):
    esc = html.escape(code)
    esc = esc.replace("\n", "<br/>").replace("  ", "  ")
    story.append(Spacer(1, 3))
    story.extend(safe_keep_together([
        neo_panel([Paragraph(esc, code_style)], bg=PAPER, border=2.5, shadow=4,
                  pad=(7, 7)),
    ]))
    story.append(Spacer(1, 8))


def data_table(story, header, rows, ratios, caption=None):
    data = [[Paragraph(f"<b>{html.escape(h).upper()}</b>", tbl_header_style)
             for h in header]]
    for r in rows:
        data.append([Paragraph(c, tbl_cell_style) for c in r])
    widths = [r * AVAIL_W * 0.97 for r in ratios]
    t = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("BOX", (0, 0), (-1, -1), 3, INK),
        ("INNERGRID", (0, 0), (-1, -1), 1.4, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 1), (-1, -1), PAPER),
    ]))
    story.append(Spacer(1, 9))
    if caption:
        story.extend(safe_keep_together([
            t,
            Spacer(1, 4),
            Paragraph(html.escape(caption), caption_style),
        ]))
    else:
        story.append(t)
    story.append(Spacer(1, 10))


def callout(story, text):
    story.append(Spacer(1, 5))
    story.extend(safe_keep_together([
        neo_panel([Paragraph(text, lead_style)], bg=GOLD, border=3, shadow=5,
                  pad=(8, 8)),
    ]))
    story.append(Spacer(1, 10))


# ── Page painter: cream page + ink frame + footer chip ──────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # ink page frame (the deck's slide frame, scaled down)
    canvas.setStrokeColor(INK)
    canvas.setLineWidth(2.2)
    canvas.rect(14, 14, PAGE_W - 28, PAGE_H - 28, fill=0, stroke=1)
    # header: running title, tracked caps
    canvas.setFont(BODY_FONT, 7.5)
    canvas.setFillColor(INK)
    canvas.drawString(MARGIN, PAGE_H - MARGIN + 6, "B I Z R O   —   D E E P   G U I D E")
    # footer: attribution left, page number in a bordered chip right
    canvas.setFont(BODY_FONT, 7)
    canvas.setFillColor(INK)
    canvas.drawString(MARGIN, MARGIN - 18,
                      "Bano Qabil x Alibaba Cloud AI Hackathon Pakistan 2026")
    n = str(canvas.getPageNumber())
    nw = stringWidth(n, BODY_FONT, 7.5)
    canvas.setLineWidth(1.6)
    canvas.rect(PAGE_W - MARGIN - nw - 10, MARGIN - 22, nw + 10, 14,
                fill=0, stroke=1)
    canvas.setFont(BODY_FONT, 7.5)
    canvas.drawString(PAGE_W - MARGIN - nw - 5, MARGIN - 18, n)
    canvas.restoreState()


class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, "bookmark_name"):
            self.notify("TOCEntry", (
                getattr(flowable, "bookmark_level", 0),
                getattr(flowable, "bookmark_text", ""),
                self.page,
                getattr(flowable, "bookmark_key", ""),
            ))


def build_body():
    doc = TocDocTemplate(
        BODY_PDF, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN + 8,
        bottomMargin=MARGIN + 8,
        title="Bizro — Deep Guide",
        author="Bizro — hackathon build team",
        creator="Z.ai",
        subject="Technical and demo manual for the Bizro WhatsApp voice-khata copilot",
    )
    story = []

    # ── Contents ──
    story.append(Paragraph("CONTENTS", h1_text_style))
    story.append(HRFlowable(width="100%", thickness=2.2, color=INK,
                            spaceBefore=4, spaceAfter=12))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC1", fontName=BODY_FONT, fontSize=10, leading=19,
                       leftIndent=14, firstLineIndent=-14, textColor=INK),
        ParagraphStyle("TOC2", fontName=BODY_FONT, fontSize=8.5, leading=15,
                       leftIndent=34, firstLineIndent=-14, textColor=GREEN),
    ]
    story.append(toc)
    story.append(Spacer(1, 14))
    story.extend(safe_keep_together([
        neo_panel([Paragraph(
            "This guide was generated from the verified working manual on "
            "4 September 2026. Every file path, command, model name and status "
            "code in it was checked against the repository or the live "
            "deployment on that date. This PDF is built by "
            + mono("docs/build_guide_pdf.py") + " (run it to rebuild); the "
            "repo overview is " + mono("README.md") + ".", body_style)],
            bg=PAPER, border=2.5, shadow=4, pad=(7, 7)),
    ]))
    story.append(PageBreak())

    # ── 1 · Local setup ──
    heading(story, "1 · Local setup, end to end", 0)
    heading(story, "Prerequisites", 1)
    bullets(story, [
        "Python 3.12+ (the repo was developed on 3.14), Node 18+, Git Bash on Windows or any POSIX shell.",
        "Optional: a DashScope API key (Alibaba Cloud Model Studio) for live model calls, "
        "WhatsApp Cloud API credentials for live messaging, a Neon Postgres URL. "
        "<b>Zero credentials is a valid state</b> — everything runs mocked and clearly labeled.",
    ])
    heading(story, "Install and configure", 1)
    codeblock(story,
              "python -m venv .venv\n"
              "source .venv/Scripts/activate    # Git Bash on Windows\n"
              "python -m pip install -r requirements.txt\n"
              "cp .env.example .env")
    para(story,
         "The root " + mono("requirements.txt") + " is the union of the server and the three agent "
         "packages (FastAPI, SQLAlchemy, httpx, pydantic, edge-tts, ffmpeg via imageio-ffmpeg, "
         "pytest). Model credentials are env-only — see the table in " + mono("README.md") +
         " and " + mono(".env.example") + ".")
    heading(story, "Run the server", 1)
    codeblock(story,
              "python credit-agent/scripts/seed_demo.py    # demo merchants, only if DB empty\n"
              "python -m uvicorn server.app.main:app --reload --port 8000")
    para(story,
         "The server binds paths to the repo root, so it can be started from anywhere. On boot it "
         "logs which integrations are live vs mock (and never logs the database password — see "
         + mono("_safe_db_label") + " in " + mono("server/app/main.py") + "). Check "
         + link("http://localhost:8000/health") + " for the same information in JSON.")
    para(story,
         "With the frontends built (" + mono("npm run build") + " in " + mono("dashboard/") + " and "
         + mono("site/") + "), the server alone serves the landing page at " + mono("/") +
         " and the dashboard at " + mono("/ledger") + " — exactly the production topology "
         "(" + mono("server/app/main.py") + ", static router at the bottom of the file). If no "
         "dashboard build exists, the SPA fallback returns a plain instruction message instead of a 500.")
    heading(story, "Run the dashboard and site dev servers", 1)
    codeblock(story,
              "cd dashboard && npm install && npm run dev   # http://localhost:5173\n"
              "cd site && npm install && npm run dev        # second terminal")
    para(story,
         "Both Vite configs proxy API routes to the backend on " + mono(":8000") + ": "
         + mono("dashboard/vite.config.ts") + " forwards " + mono("/api") + " and " + mono("/webhook") +
         "; " + mono("site/vite.config.ts") + " additionally forwards " + mono("/ledger") + ", "
         + mono("/credit") + ", " + mono("/settings") + " and " + mono("/assets") +
         " so cross-app links work in dev. Keep the server running — the dev proxies expect it.")
    heading(story, "One-command alternative", 1)
    para(story,
         mono("bash scripts/run_demo.sh") + " does all of the above: venv, install, UI builds "
         "(skip with " + mono("BIZRO_SKIP_UI=1") + "), seeding when the DB is empty, then serves on "
         + mono(":8000") + ".")

    # ── 2 · Webhook flow ──
    heading(story, "2 · The WhatsApp webhook flow", 0)
    para(story,
         "Entry point: " + mono("server/app/webhook.py") + ". " + mono("GET /webhook/whatsapp") +
         " is the Meta verification handshake (constant-time token compare). "
         + mono("POST /webhook/whatsapp") + " is the ingest path. Step by step for a voice note:")
    numbered(story, [
        "<b>Signature check.</b> With " + mono("WHATSAPP_APP_SECRET") + " set (it is, in production), "
        "every request must carry a valid " + mono("X-Hub-Signature-256") + " (HMAC-SHA256 of the raw "
        "body). Verification lives in " + mono("server/app/whatsapp_client.py") +
        " (constant-time compare). Unsigned posts get 403 — with one carve-out: the simulator "
        "envelope is accepted unsigned, and only for the three public demo numbers "
        + mono("923001234567") + ", " + mono("923009999888") + ", " + mono("923009111222") + ".",
        "<b>Dedup.</b> Meta redelivers. The " + mono("wamid") + " is claimed in "
        + mono("processed_messages") + " before any processing; a repeat delivery is acknowledged "
        "as deduped and never re-processed.",
        "<b>Merchant upsert</b> by " + mono("wa_id") + ". A WhatsApp profile name is only used at "
        "account creation — it is attacker-controlled text and can never rename an existing "
        "merchant's ledger.",
        "<b>Media bytes.</b> Either from the simulator envelope (" + mono("bizro_sim.media_b64") +
        ", base64 inline — this is what the landing-page mic and the dashboard simulator send), or "
        "the real two-step Graph API download (metadata, then bytes) in "
        + mono("server/app/whatsapp_client.py") + ".",
        "<b>Validation.</b> Size caps (16 MB audio, 5 MB image) and magic-byte sniffing in "
        + mono("server/app/media.py") + ". An Ogg page labeled as a photo, or an executable, is "
        "rejected with a polite reply; nothing is stored.",
        "<b>Storage — the audit trail.</b> Bytes land at " + mono("media/<yyyy>/<mm>/<uuid>.<ext>") +
        " plus a " + mono("media_blobs") + " row with the sha256 and a durable BYTEA copy of the "
        "bytes (serverless disk is ephemeral; the database copy survives cold starts). "
        + mono("GET /api/media/{id}") + " serves from disk when present, else straight from "
        "Postgres, else 410 (" + mono("server/app/api.py") + ").",
        "<b>Pipeline.</b> " + mono("server/app/dispatch.py") + " lazily imports "
        + mono("voice_agent.pipeline.process_voice_note") + " (audio) or "
        + mono("vision_agent.pipeline.process_receipt_image") + " (photo). Receipts also get the "
        "merchant's recent expense history so the vision pipeline can raise price-anomaly and "
        "duplicate-suspect flags. If an agent package were missing, a clearly-labeled synthetic "
        "server fallback runs instead (mock marker, sub-threshold confidence, entry stays "
        "pending) — never silently.",
        "<b>Persist.</b> Pipeline output is validated as a schema transaction and written with full "
        "provenance: " + mono("source_type") + ", " + mono("source_model") + ", " + mono("confidence") +
        ", " + mono("raw_model_output") + " are immutable; the first human edit snapshots the "
        "original values into " + mono("transactions.original_values") + ". Confidence below "
        + mono("CONFIDENCE_CONFIRM_THRESHOLD") + " (0.75) forces " + mono("status=pending") +
        " until the merchant confirms.",
        "<b>Reply.</b> The confirmation text is stored as an " + mono("outbound_messages") +
        " row and delivered via the Graph API — as an interactive message with one-tap "
        "Correct/Edit buttons while the entry is pending. Delivery failure never discards the "
        "saved entry (demo numbers are outside Meta's test allow-list, so this path is exercised "
        "constantly).",
    ])
    para(story,
         "Text messages follow a parallel branch: confirm/reject words (" + mono("1") + "/" +
         mono("0") + ", English or Urdu) act on the latest pending entry; onboarding triggers get "
         "the welcome sequence; anything else is parsed as a free-text transaction exactly like a "
         "voice transcript. Button presses (correct/edit payloads) act on the latest pending entry "
         "too. Every reply — confirmation, clarification, rejection, onboarding — gets an "
         + mono("outbound_messages") + " row; nothing reaches the merchant without one.")
    callout(story,
            "<b>Failure classes stay honest.</b> A parse miss (no amount, non-transaction, schema "
            "violation) sends a clarification and persists nothing; a genuine model timeout or "
            "outage sends a busy reply and persists nothing. The two never swap copy.")

    # ── 3 · Qwen model stack ──
    heading(story, "3 · The Qwen model stack", 0)
    para(story,
         "Everything runs on Alibaba Cloud Model Studio via the DashScope OpenAI-compatible "
         "endpoint (" + mono("/chat/completions") + "). Production uses the international base URL "
         + mono("https://dashscope-intl.aliyuncs.com/compatible-mode/v1") + " (visible in "
         + mono("GET /health") + "). The thin client is " + mono("server/app/dashscope_client.py") +
         " for the server and per-agent copies for the pipelines.")
    bullets(story, [
        "<b>Speech to text — qwen3-asr-flash.</b> " + mono("STT_PROVIDER=qwen") + " sends the "
        "audio as a base64 data-URI " + mono("input_audio") + " content item in a "
        "chat-completions call (" + mono("voice-agent/voice_agent/stt_client.py") +
        "). This is the production primary.",
        "<b>STT fallback — Groq Whisper.</b> Any qwen3-asr-flash failure (container format "
        "rejection, quota, network — anything) falls back automatically to "
        + mono("whisper-large-v3-turbo") + " on Groq (free tier, " + mono("STT_API_KEY") +
        "). A voice note is never lost to a transcriber hiccup; the fallback is logged.",
        "<b>Transaction parsing — qwen-flash</b> (" + mono("MODEL_VOICE") + "). One prompt "
        "produces the structured transaction JSON (Urdu-aware: phonetic English number words, "
        "mixed script). One repair-retry fires if the output fails schema validation "
        "(" + mono("voice-agent/voice_agent/pipeline.py") + "). Typed WhatsApp text messages go "
        "through the same parser with " + mono('source.type="text"') + ".",
        "<b>Receipt OCR — qwen-vl-ocr</b> (" + mono("MODEL_OCR_VL") + ", selected by "
        + mono("OCR_MODEL=vl") + "). " + mono("vision-agent/vision_agent/adapters.py") +
        " keeps a second real adapter, qwen3.5-ocr (" + mono("MODEL_OCR_NEW") + "), for the "
        "bake-off; the winner is an env switch, reversible and auditable. Unparseable model "
        "output is surfaced as an unreadable extraction and a polite retry — the pipeline never "
        "guesses.",
        "<b>Credit narrative — qwen-flash</b> (" + mono("MODEL_REASONING") + "). The score itself "
        "is a deterministic rubric over real aggregates (" + mono("credit-agent/credit_agent/rubric.py") +
        "); the model writes the short narrative stored in " + mono("credit_reports") +
        ". The stored key is " + mono("narrative_ur") + " — a historical name; the text is simple "
        "English by design (" + mono("credit-agent/credit_agent/narrative.py") + ").",
    ])
    para(story,
         "Mock semantics (" + mono("MOCK_MODE") + " in " + mono("server/app/config.py") + "): "
         + mono("auto") + " = real calls when the key exists, clearly-labeled synthetic output "
         "otherwise; " + mono("always") + " = always mock (demo-safe); " + mono("never") +
         " = refuse to fake (a missing key raises). Every mock payload carries "
         + mono('"mock": true') + ". " + mono("llm_guard.py") + " at the repo root counts live "
         "calls and can hard-stop at a daily budget (used when the endpoint points at OpenRouter's "
         "free tier instead of DashScope).")

    # ── 4 · Demo walkthrough ──
    heading(story, "4 · Demo walkthrough", 0)
    heading(story, "The seeded merchants", 1)
    data_table(
        story,
        ["Store", "wa_id (public demo number)", "Role in the demo"],
        [["Al-Madina Kiryana Store", mono("923009999888"),
          "The healthy case: 88 entries June–September 2026 (count verified against the live "
          "API on 2026-09-04), regular sales/udhar/receipt mix, a real readiness verdict."],
         ["Bilal Ki Dukan", mono("923009111222"),
          "The contrast case: sparse logging with a gap, to show what “not ready” "
          "looks like."]],
        [0.24, 0.24, 0.52],
        caption="Seeded by credit-agent/scripts/seed_demo.py; both numbers are public simulator constants.",
    )
    para(story,
         mono("GET /api/merchants") + " orders the healthy store first, so a judge landing on "
         + mono("/ledger") + " or " + mono("/credit") + " opens on the full story, not the thin "
         "sandbox. Any real merchant's number is reduced to a last-4 hint on that endpoint.")
    heading(story, "The simulator surfaces", 1)
    bullets(story, [
        "<b>Dashboard " + mono("/simulator") + "</b> — a WhatsApp-shaped chat backed by real API "
        "calls: send a note, watch the parse land in the ledger, reply " + mono("1") + " to "
        "confirm, poll " + mono("GET /api/merchants/{id}/outbound") + " for Bizro's replies. "
        "Confirmation bubbles lazily get a stamped invoice image (rendered, stored as a normal "
        "media blob, pinned into the outbound row — " + mono("_ensure_invoice_media") + " in "
        + mono("server/app/api.py") + ").",
        "<b>" + mono("server/scripts/simulate_inbound.py") + "</b> — posts simulator envelopes "
        "from the CLI (default sandbox number " + mono("923001234567") + ").",
        "<b>" + mono("server/scripts/demo_flow.py") + "</b> — the rehearsal driver: seeds if "
        "empty, drives the whole story over real HTTP (or in-process with " + mono("--local") +
        "), prints a judge-facing timeline with per-step timings, and exits non-zero the moment "
        "any step fails. Rehearse with it, not on stage.",
        "<b>Landing-page hero</b> (" + mono("site/src/hero-demo.ts") + ") — the “Tap to record "
        "a note” card records real browser audio (MediaRecorder) and POSTs it to the live "
        + mono("/webhook/whatsapp") + " in the exact simulator envelope. The invoice card then "
        "renders what the server actually parsed (kind, amount, counterparty, confidence); "
        "missing fields render as unknown, mock markers as-is.",
    ])
    heading(story, "Suggested two-minute flow", 1)
    numbered(story, [
        "Land on " + link("https://bizro-pk.vercel.app") + " — hero card: record a short note "
        "(“sold ghee to Rahmat for three thousand cash”), stop, watch the parsed "
        "invoice appear.",
        "Open " + mono("/ledger") + " — Al-Madina's four months of history; tap a demo-marked "
        "row, open its audit trail (the original media, model, confidence).",
        "Open " + mono("/credit") + " — the Credit Readiness report for Al-Madina, then switch "
        "to Bilal Ki Dukan for the contrast.",
        "Open " + mono("/simulator") + " — send a fresh note live, confirm with " + mono("1") + ".",
    ])

    # ── 5 · Real vs mock ──
    heading(story, "5 · What is real vs mock", 0)
    callout(story,
            "<b>The honesty law.</b> Every mock is labeled, every failure is visible, and nothing "
            "synthetic is ever presented as a real model result. This rule governs the whole "
            "codebase (referenced in code as STATUS.md D0-3).")
    para(story, "<b>Real in production right now:</b>", lead_style)
    bullets(story, [
        "The WhatsApp Cloud API webhook and outbound sends (System User token, signature "
        "enforced — " + mono("/health") + " reports both live).",
        "Neon Postgres persistence: merchants, transactions with provenance, outbound log, "
        "credit reports, and the media bytes themselves.",
        "All model calls on DashScope: qwen3-asr-flash (STT), qwen-flash (parse, narrative), "
        "qwen-vl-ocr (OCR). " + mono("/health") + " shows the live base URL.",
        "The audit trail: original audio/photo bytes served back from " + mono("/api/media") + ".",
        "Urdu voice replies via edge-tts (" + mono("POST /api/tts") + ", voice "
        + mono("ur-PK-AsadNeural") + ").",
    ])
    para(story, "<b>Mock or seeded, and labeled as such:</b>", lead_style)
    bullets(story, [
        "The two seeded demo merchants and the sandbox ledger — dashboard rows carry a visible "
        "“Demo data — seeded example entries” marker "
        "(" + mono("dashboard/src/components/MockBanner.tsx") + ").",
        "Server-fallback pipeline output when an agent package is absent "
        "(" + mono("server/app/dispatch.py") + ") — mock-flagged, low confidence, stays pending.",
        "Any model call made without a key under " + mono("MOCK_MODE=auto") + " — every payload "
        "carries " + mono('"mock": true') + ", and the landing-page hero displays the marker "
        "verbatim instead of hiding it.",
        "WhatsApp sends to demo numbers are refused by Meta (outside the test allow-list); the "
        "entry stays saved and the UI shows “saved, not delivered” rather than pretending "
        "the message arrived.",
    ])

    # ── 6 · Security ──
    heading(story, "6 · Security posture", 0)
    data_table(
        story,
        ["Setting", "Default", "Why"],
        [[mono("RATE_LIMIT_WEBHOOK_PER_HOUR"), "30 / hour",
          "The webhook triggers paid AI calls — a tight per-IP hourly budget."],
         [mono("RATE_LIMIT_GENERAL_PER_MIN"), "120 / minute",
          "Everything else, per IP."],
         [mono("CONFIDENCE_CONFIRM_THRESHOLD"), "0.75",
          "Parses below this stay pending until the merchant confirms."],
         ["Media caps (audio / image)", "16 MB / 5 MB",
          "Enforced with magic-byte sniffing before anything touches disk."]],
        [0.38, 0.17, 0.45],
        caption="All limits are env-tunable per request; 429s carry Retry-After.",
    )
    bullets(story, [
        "<b>Webhook signature.</b> " + mono("X-Hub-Signature-256") + " HMAC-SHA256 over the raw "
        "body, constant-time compare, enforced whenever " + mono("WHATSAPP_APP_SECRET") +
        " is set. The only unsigned path is the simulator envelope, and only for the three "
        "public demo numbers — a forged " + mono("bizro_sim") + " marker from any other "
        + mono("wa_id") + " is still a 403.",
        "<b>Headers and CSP.</b> Every response carries " + mono("nosniff") + ", "
        + mono("X-Frame-Options: DENY") + ", a strict referrer policy, a permissions-policy "
        "limited to the app's own camera/mic use, and a CSP of " + mono("default-src 'self'") +
        " with no third-party script origins (" + mono("server/app/middleware_security.py") + ").",
        "<b>Inbound media.</b> Size caps and magic-byte sniffing before anything touches disk; "
        "executables and mismatched content types are rejected.",
        "<b>Untrusted model output.</b> Parsed strings are length-capped before they enter "
        "prompts; transaction JSON is marked UNTRUSTED in the reminder-draft prompt; "
        "HTML-escaping on rendered artifacts; the CSV export neutralizes formula injection "
        "(" + mono("=") + "/" + mono("+") + "/" + mono("-") + "/" + mono("@") + " prefixes) and is "
        "UTF-8-BOM + CRLF so Excel opens Urdu correctly (" + mono("server/app/api.py") + ").",
        "<b>Privacy.</b> Real merchant phone numbers never appear on public endpoints (last-4 "
        "hint only); the database DSN is logged without its password.",
    ])

    # ── 7 · Ops ──
    heading(story, "7 · Ops", 0)
    bullets(story, [
        "<b>Deploy.</b> " + mono("bash scripts/deploy.sh") + " builds both frontends, runs "
        + mono("vercel deploy --prod") + ", re-points the four aliases (" + mono("bizro-pk") +
        ", " + mono("getbizro") + ", " + mono("bizro-app") + ", " + mono("bizro-ai") + " "
        + mono(".vercel.app") + "), and curls " + mono("/health") + " and " + mono("/") +
        " for 200s. Prereq: " + mono("npx vercel login") + " once, env vars set in the Vercel "
        "dashboard.",
        "<b>Vercel shape.</b> " + mono("api/index.py") + " wraps the FastAPI app as one "
        "serverless function (region " + mono("sin1") + ", 60 s max duration — " + mono("vercel.json") +
        "); static assets route to " + mono("site/dist") + " and " + mono("dashboard/dist") +
        ". On serverless, " + mono("MEDIA_DIR") + " is " + mono("/tmp/media") + " and SQLite would "
        "be ephemeral — hence Neon.",
        "<b>Durable media.</b> Every media blob is stored twice: the dated filesystem tree and a "
        "BYTEA column in Postgres. " + mono("/api/media/{id}") + " prefers disk, falls back to "
        "the database across cold starts, and 410s only if both are gone.",
        "<b>Observability.</b> " + mono("GET /health") + " reports integration live/mock status, "
        "signature enforcement, pipeline import status, and the confidence threshold — the same "
        "check the deploy script and the QA live walk (" + mono("qa/live_walk/live_walk.py") +
        ") use.",
    ])

    # ── 8 · Troubleshooting ──
    heading(story, "8 · Troubleshooting", 0)
    bullets(story, [
        "<b>403 “invalid signature” on your own POSTs</b> — you set "
        + mono("WHATSAPP_APP_SECRET") + ", so unsigned posts are rejected outside the demo "
        "sandbox. Use the simulator envelope with a demo " + mono("wa_id") + ", or sign the body.",
        "<b>Everything says “mock”</b> — no " + mono("DASHSCOPE_API_KEY") +
        " in the environment, or " + mono("MOCK_MODE=always") + ". " + mono("/health") +
        " tells you which integration is mock and why.",
        "<b>The “dashboard not built” message at " + mono("/ledger") + "</b> — run "
        + mono("npm install && npm run build") + " in " + mono("dashboard/") + ", or use its "
        "dev server.",
        "<b>Log line “Qwen ASR failed ... falling back”</b> — expected resilience, not "
        "an error: the note was transcribed by Whisper instead. Frequent fallbacks usually mean "
        "a container format qwen3-asr rejects; the decode step ("
        + mono("voice-agent/voice_agent/decode.py") + ") normalizes most formats first.",
        "<b>429s during local testing</b> — the per-IP limiter; raise "
        + mono("RATE_LIMIT_GENERAL_PER_MIN") + "/" + mono("RATE_LIMIT_WEBHOOK_PER_HOUR") +
        " in the env, or restart the server (windows reset on boot).",
        "<b>Reports 500 only in production</b> — historically the Neon password being masked "
        "when passed to credit-agent; the fix lives in " + mono("server/app/dispatch.py") +
        " (" + mono("render_as_string(hide_password=False)") + "). If it reappears, start there.",
        "<b>TTS returns 502</b> — honest failure (budget/network); the frontend skips audio "
        "rather than faking it. Retry, or check " + mono("MEDIA_DIR") + " writability.",
        "<b>A Meta redelivery created a duplicate entry</b> — it should not: dedup is keyed on "
        + mono("wamid") + " in " + mono("processed_messages") + ". If you see duplicates, check "
        "that table and the claim logic at the top of the POST handler in "
        + mono("server/app/webhook.py") + ".",
    ])

    # end panel: fills the final page and closes the guide with the three
    # commands a judge or new developer actually needs next.
    story.append(Spacer(1, 18))
    story.extend(safe_keep_together([
        neo_panel([
            Paragraph("<b>WHERE TO GO NEXT</b>", h2_style),
            Spacer(1, 4),
            Paragraph("Live product and status: " + link("https://bizro-pk.vercel.app")
                      + "  (JSON status at " + mono("/health") + ")", body_style),
            Paragraph("One-command local demo: " + mono("bash scripts/run_demo.sh"), body_style),
            Paragraph("Rehearse the judge flow: " + mono("python server/scripts/demo_flow.py"), body_style),
            Paragraph("Rebuild this guide: " + mono("python docs/build_guide_pdf.py")
                      + " (the content lives in the script)", body_style),
            Spacer(1, 3),
        ], bg=PAPER, border=3, shadow=5, pad=(9, 11)),
    ]))

    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)


# ── Neobrutalist cover (canvas-drawn; A4, bottom-left origin) ───────────────
def _chip(c, x, y, text, font, size, fg, bg, pad_x=8, pad_y=5, border=2.2):
    w = stringWidth(text, font, size) + 2 * pad_x
    h = size + 2 * pad_y + 2
    c.setFillColor(INK)
    c.rect(x + 3, y - 3, w, h, fill=1, stroke=0)      # hard shadow
    c.setFillColor(bg)
    c.setStrokeColor(INK)
    c.setLineWidth(border)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(fg)
    c.setFont(font, size)
    c.drawString(x + pad_x, y + pad_y, text)
    return w


def build_cover():
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas as pdfcanvas

    c = pdfcanvas.Canvas(COVER_PDF, pagesize=A4)
    W, H = A4
    # cream field + ink frame
    c.setFillColor(CREAM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(INK)
    c.setLineWidth(3)
    c.rect(18, 18, W - 36, H - 36, fill=0, stroke=1)

    # kicker chip
    _chip(c, 44, H - 96, "TECHNICAL GUIDE  ·  DEMO MANUAL", SLAB, 11, INK, GOLD)

    # hero: BIZRO in ink over a gold offset slab
    c.setFont(SLAB, 104)
    c.setFillColor(GOLD)
    c.drawString(54, H - 266, "BIZRO")
    c.setFillColor(INK)
    c.drawString(44, H - 256, "BIZRO")

    # sub-title + red underline bar
    c.setFont(SLAB, 30)
    c.setFillColor(GREEN)
    c.drawString(46, H - 310, "THE DEEP GUIDE")
    tw = stringWidth("THE DEEP GUIDE", SLAB, 30)
    c.setFillColor(RED)
    c.rect(46, H - 322, tw, 6, fill=1, stroke=0)

    # ledger ruling: dashed teal line
    c.setStrokeColor(TEAL)
    c.setLineWidth(2)
    c.setDash(12, 9)
    c.line(46, H - 344, W - 60, H - 344)
    c.setDash()

    # summary panel (paper, ink border, hard shadow)
    summary = ("How a WhatsApp voice note becomes a lender-legible credit record: "
               "local setup, the webhook pipeline, the Qwen model stack and its "
               "fallbacks, the demo walkthrough, what is real versus mock, the "
               "security posture, and operations. Every claim verified against "
               "the code or the live deployment.")
    lines = simpleSplit(summary, BODY_FONT, 10.5, 438)
    panel_h = 30 + 16 * len(lines)
    px, py, pw = 46, H - 384 - panel_h, 470
    c.setFillColor(INK)
    c.rect(px + 6, py - 6, pw, panel_h, fill=1, stroke=0)
    c.setFillColor(PAPER)
    c.setStrokeColor(INK)
    c.setLineWidth(3)
    c.rect(px, py, pw, panel_h, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(BODY_FONT, 10.5)
    ty = py + panel_h - 24
    for ln in lines:
        c.drawString(px + 16, ty, ln)
        ty -= 16

    # model stickers
    _chip(c, 46, py - 48, "QWEN3-ASR-FLASH", SLAB, 9.5, CREAM, GREEN)
    _chip(c, 46 + stringWidth("QWEN3-ASR-FLASH", SLAB, 9.5) + 36, py - 48,
          "QWEN-FLASH", SLAB, 9.5, CREAM, RED)
    _chip(c, 46 + stringWidth("QWEN3-ASR-FLASH", SLAB, 9.5)
          + stringWidth("QWEN-FLASH", SLAB, 9.5) + 70, py - 48,
          "QWEN-VL-OCR", SLAB, 9.5, CREAM, TEAL)

    # footer meta: two short lines left, URL chip right-aligned to the frame
    # (one long line previously ran under the chip and clipped)
    c.setFillColor(INK)
    c.setFont(BODY_FONT, 8.5)
    c.drawString(46, 52, "Bano Qabil x Alibaba Cloud AI Hackathon Pakistan 2026")
    c.drawString(46, 38, "4 September 2026")
    badge_w = stringWidth("BIZRO-PK.VERCEL.APP", SLAB, 9) + 16
    _chip(c, W - 24 - badge_w - 3, 36, "BIZRO-PK.VERCEL.APP", SLAB, 9, INK, PAPER)

    c.showPage()
    c.save()


def merge():
    from pypdf import PdfReader, PdfWriter

    try:
        from pypdf import Transformation  # pypdf >= 3.9 top-level
    except ImportError:  # older layouts
        from pypdf.generic import Transformation

    A4_W, A4_H = 595.28, 841.89

    def normalize(page):
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        if abs(w - A4_W) > 2 or abs(h - A4_H) > 2:
            page.add_transformation(Transformation().scale(sx=A4_W / w, sy=A4_H / h))
            page.mediabox.lower_left = (0, 0)
            page.mediabox.upper_right = (A4_W, A4_H)
        return page

    writer = PdfWriter()
    writer.add_page(normalize(PdfReader(COVER_PDF).pages[0]))
    for page in PdfReader(BODY_PDF).pages:
        writer.add_page(normalize(page))
    writer.add_metadata({
        "/Title": "Bizro — Deep Guide",
        "/Author": "Bizro — hackathon build team",
        "/Creator": "Z.ai",
        "/Subject": "Technical and demo manual for the Bizro WhatsApp voice-khata copilot",
    })
    with open(FINAL_PDF, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    build_body()
    print("body ok:", BODY_PDF)
    build_cover()
    print("cover ok:", COVER_PDF)
    merge()
    print("final:", FINAL_PDF)
