

# server/schema.md — Shared Transaction Schema

**v0.1 — authored by the Orchestrator so every pipeline agent builds against one
contract from the first minute. Owner from now on: backend-agent.** Any change to this
file is a cross-agent contract change: flag the Orchestrator first (AGENTS.md §1), don't
just edit it. Version bumps get logged in STATUS.md.

Implements design.md §7.2 (audit trail on every AI-parsed entry: source reference +
confidence) and §7.1 (Udhar Radar as a derived view, not a separate table).

## 1. Canonical transaction JSON — pipeline output / API wire format

This is what `voice_agent`, `vision_agent` (and any manual-entry path) must return, and
what `server` persists and `credit_agent` consumes:

```json
{
  "kind": "sale | expense | udhar_given | udhar_settlement",
  "amount_pkd": 5000,
  "currency": "PKR",
  "counterparty": { "name": "Ahmad", "phone": null },
  "description": "Udhar given to Ahmad",
  "item_lines": [
    { "item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700 }
  ],
  "occurred_at": "2026-08-21T19:03:00+05:00",
  "source": {
    "type": "voice | photo | manual",
    "media_id": "<uuid of media blob, null for manual>",
    "model": "qwen3.5-omni-plus | qwen-vl-ocr | qwen3.5-ocr | null",
    "confidence": 0.87,
    "raw_output": { "transcript": "..." }
  },
  "flag": "none | price_anomaly | total_mismatch | duplicate_suspect | low_confidence",
  "status": "pending | confirmed | edited | rejected",
  "confirmation_ur": "احمد کو 5000 روپے ادھر دیے۔ کیا یہ درست ہے؟"
}
```

Rules:
- `amount_pkd` is always **positive**; direction is implied by `kind`.
  - `sale` — customer paid (cash in).
  - `expense` — merchant spent (supplier purchase; OCR receipts land here).
  - `udhar_given` — merchant extended credit to a customer (money owed **to** merchant — Udhar Radar).
  - `udhar_settlement` — customer repaid part/all of an udhar.
- `counterparty` present for `sale`, `udhar_given`, `udhar_settlement` (customer) and
  optionally for `expense` (supplier name from the receipt, if readable).
- `source.confidence` ∈ [0,1] is **required** for every AI-parsed entry (audit trail).
  Entries with confidence < 0.75 (`CONFIDENCE_CONFIRM_THRESHOLD`, env-tunable) are stored
  `status=pending` until the merchant confirms (WhatsApp reply or dashboard edit).
- `confirmation_ur` — clean Urdu text (WhatsApp renders RTL natively). This IS the
  text-out path; voice-out is a stretch goal, not assumed (design.md §2).
- Numerals in outbound text: Western digits by default (`NUMERAL_STYLE=western|urdu`
  env, decided by the real-user test design.md §4.2 calls for).
- `item_lines` present for OCR-parsed expenses; empty list otherwise.
- Unknown/ambiguous parse → the pipeline must NOT guess: return
  `flag=low_confidence`, `status=pending`, and a clarification question in
  `confirmation_ur`.

## 2. Postgres schema (SQLAlchemy models live in `server/app/db.py`)

Postgres is the production target (design.md §8); dev default is SQLite via
`DATABASE_URL` — keep DDL Postgres-compatible (JSONB→JSON on SQLite is handled by
SQLAlchemy's JSON type with `.variant()`).

```sql
CREATE TABLE merchants (
  id            UUID PRIMARY KEY,
  wa_id         TEXT UNIQUE NOT NULL,          -- WhatsApp phone id (wa_id from webhook)
  display_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE media_blobs (                     -- raw audit trail, never deleted
  id            UUID PRIMARY KEY,
  merchant_id   UUID REFERENCES merchants(id),
  kind          TEXT NOT NULL CHECK (kind IN ('voice','image')),
  mime_type     TEXT NOT NULL,
  storage_path  TEXT NOT NULL,                 -- on-disk under /media (gitignored)
  sha256        TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customers (
  id            UUID PRIMARY KEY,
  merchant_id   UUID REFERENCES merchants(id),
  name          TEXT NOT NULL,
  phone         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (merchant_id, lower(name))
);

CREATE TABLE transactions (
  id              UUID PRIMARY KEY,
  merchant_id     UUID REFERENCES merchants(id) NOT NULL,
  customer_id     UUID REFERENCES customers(id),
  kind            TEXT NOT NULL CHECK (kind IN ('sale','expense','udhar_given','udhar_settlement')),
  amount_pkd      NUMERIC(12,2) NOT NULL CHECK (amount_pkd > 0),
  currency        TEXT NOT NULL DEFAULT 'PKR',
  description     TEXT,
  item_lines      JSONB,
  occurred_at     TIMESTAMPTZ NOT NULL,
  source_type     TEXT NOT NULL CHECK (source_type IN ('voice','photo','manual')),
  source_media_id UUID REFERENCES media_blobs(id),
  source_model    TEXT,
  confidence      NUMERIC(4,3),
  raw_model_output JSONB,
  flag            TEXT NOT NULL DEFAULT 'none',
  status          TEXT NOT NULL DEFAULT 'pending',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tx_merchant_time ON transactions (merchant_id, occurred_at DESC);

CREATE TABLE outbound_messages (               -- what we sent, for the audit trail
  id             UUID PRIMARY KEY,
  merchant_id    UUID REFERENCES merchants(id),
  transaction_id UUID REFERENCES transactions(id),
  kind           TEXT NOT NULL,                -- confirmation_text | invoice_image | flag_warning | nudge
  body           TEXT,
  media_path     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE credit_reports (
  id            UUID PRIMARY KEY,
  merchant_id   UUID REFERENCES merchants(id),
  period_start  DATE NOT NULL,
  period_end    DATE NOT NULL,
  model         TEXT,
  report_json   JSONB NOT NULL,
  narrative_ur  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 3. Udhar Radar (derived view, Day 2)

Outstanding per customer = Σ(`udhar_given`) − Σ(`udhar_settlement`) over confirmed+
pending transactions, grouped by `customer_id`. Exposed via API and rendered as a
dashboard widget. No new tables.

## 4. Server API surface (backend-agent owns; pipelines never call each other)

- `POST /webhook/whatsapp` — Meta webhook ingest (audio / image / text messages)
- `GET  /webhook/whatsapp` — Meta verification handshake (`hub.challenge`)
- `GET  /api/merchants/{id}/transactions?from=&to=&kind=`
- `GET  /api/merchants/{id}/udhar` — outstanding per customer
- `POST /api/transactions/{id}/confirm` — merchant confirmed a pending entry
- `PATCH /api/transactions/{id}` — correction; keeps original values alongside (audit)
- `GET  /api/merchants/{id}/report/preview` — generate/read latest credit report
- `GET  /health` — liveness + which integrations are live vs mock

## 5. Environment contract (`.env.example` is canonical)

`DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, `MODEL_VOICE`, `MODEL_OCR_VL`,
`MODEL_OCR_NEW`, `MODEL_REASONING`, `OCR_MODEL=vl|new`, `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`,
`DATABASE_URL`, `MOCK_MODE=auto|always|never`, `CONFIDENCE_CONFIRM_THRESHOLD`,
`NUMERAL_STYLE`.

## 6. v0.2 addendum — Day-0 Arbiter rulings (2026-08-21)

Rulings from wave-1 merge review; binding on all agents. Schema stays v0.2 until the
next Orchestrator-blessed bump.

1. **`transactions.original_values`** (JSONB, nullable, additive — implemented by
   backend-agent): first-edit snapshot taken by the audit-preserving PATCH in §4.
   Provenance columns (`source_*`, `raw_model_output`, `original_values`) are immutable
   once written. BLESSED.
2. **Unknown amount is never persisted.** When a pipeline cannot determine the amount
   with confidence it returns `amount_pkd: null` + `flag=low_confidence` +
   `confirmation_ur` holding the clarification question; the server sends the
   clarification and persists NOTHING. The `amount_pkd > 0` CHECK stands; persisting 0
   or a guess is a contract violation.
3. **Mock marker convention.** Any model-client response produced under mock mode carries
   top-level `"mock": true`; when persisted it lives at `source.raw_output.mock`. The
   field is OMITTED (not `false`) for real calls. Dashboard/report layers must surface a
   "mock data" banner whenever the marker is present.
4. **Rejection path** (vision-agent's `ReceiptRejected` pattern, blessed as standard):
   non-receipt/unusable inputs return `{rejected: true, reply_ur: "..."}` (or raise the
   pipeline's rejection error, which the server catches equivalently). The server sends
   the polite Urdu reply and persists nothing.
5. **`credit_reports.report_json` canonical skeleton** (frontend's draft + credit-agent's
   scope converge on this; credit-agent owns field-level refinement within it):

```json
{
  "period": { "start": "2026-06-01", "end": "2026-08-21" },
  "readiness": { "score": 0, "band": "ready|nearly|not_yet|insufficient_data", "label_ur": "..." },
  "metrics": [
    { "key": "txn_consistency", "label_en": "...", "label_ur": "...",
      "value": 0, "display": "...",
      "provenance": { "voice_pct": 0, "photo_pct": 0, "manual_pct": 0, "median_confidence": 0 } }
  ],
  "line_items": [ { "ref": "transaction id", "label": "...", "amount_pkd": 0,
      "source_type": "voice|photo|manual", "source_media_id": null,
      "source_model": null, "confidence": null } ],
  "red_flags": [ { "flag": "price_anomaly", "count": 0, "note_en": "...", "note_ur": "..." } ],
  "criteria_basis": "general-microfinance-pending-mawakhat | mawakhat-confirmed",
  "model": "qwen3.7-plus", "generated_at": "ISO-8601"
}
```
   Every `line_items` entry MUST carry the four audit fields (design.md §7.2).
   `criteria_basis` may never claim `mawakhat-confirmed` until the Day-2 outreach answer
   lands in `docs/mawakhat-criteria.md`.
6. **`occurred_at` typing** (integration finding D0-12): in-process pipeline inputs accept
   a tz-aware `datetime` OR an ISO-8601 string (coerce, don't reject — the two wave-1
   pipelines diverged on this); the canonical dict/wire form is ALWAYS the ISO-8601
   string per §1's example.
7. **Mutation responses carry the wire row top-level** (QA sweep 2026-08-22, C-1/C-2):
   `POST /api/transactions/{id}/confirm` and `PATCH /api/transactions/{id}` return the
   full §1 wire transaction object as the response body (PATCH additionally includes
   `original_values` alongside). No `{ok, transaction:{…}}` wrappers — the dashboard
   consumes the row directly.
8. **Webhook idempotency table** (F-5): new table `processed_messages(message_id TEXT
   PRIMARY KEY, processed_at TIMESTAMPTZ)` — the webhook inserts-or-ignores the wamid
   before dispatching; a duplicate (Meta redelivery) returns 200 with
   `{"deduped": true}` and processes nothing. A transaction may never double-create
   from one message.
9. **Ambiguous/unparseable input → clarification, never silence** (F-1, completes §6.2):
   pipelines return `amount_pkd: null` + `flag=low_confidence` + `confirmation_ur`
   holding the clarification question (never 0.0); the server sends that reply, logs it
   to `outbound_messages`, persists NO transaction, and reports the message handled
   successfully. Pipeline rejection objects (§6.4) follow the same path with their
   `reply_ur`.
10. **Amount upper bound** (E-1): `amount_pkd` validates `0 < amount ≤ 10_000_000`
    (PKR 1 crore) everywhere it enters — pipeline pydantic models and the server's
    PATCH/confirm boundary.
11. **Mock marker on stored rows** (F-2): when a pipeline runs under mock, the persisted
    `raw_model_output` carries `"mock": true` (§6.3 applies to stored rows, not just
    client responses).

---

## 7. v0.3 addendum — multi-entry envelope (2026-10-22, local ruling — NOT pushed)

A single voice note / typed message may name SEVERAL people with SEPARATE amounts.
Collapsing them into one summed total is a forbidden failure. The pipeline's multi
entry points therefore return an ENVELOPE, not a bare transaction dict:

    {"transactions": [<schema.md §1 dicts>...], "reply_text": <combined confirmation>}

Rules:
- One transaction row PER person+purpose, each linked to the SAME source media id.
- An entry with an unclear amount gets amount_pkr=null + flag=low_confidence; its
  SIBLINGS' certain entries stay clean (per-entry confidence overrides note-level).
- The combined reply enumerates every person with THEIR amount and asks the confirm
  question exactly once. Amounts are never summed across entries.
- COLLAPSE GUARD (voice_agent/numbers.py): when the transcript signals more
  scale-amounts + person-joins than returned entries, a clarification entry is
  appended — a merged total is never silently persisted.
- Server: dispatch.persist_transactions_batch persists N rows + ONE outbound
  confirmation; webhook paths consume the envelope for voice AND typed text.
- Legacy single-entry functions remain as wrappers: single-entry notes behave
  byte-identically; multi-person notes yield a clarification for legacy callers.

## 8. v0.4 addendum — dual-engine STT cross-check (2026-10-22, local ruling — NOT pushed)

Every voice note MAY be transcribed by TWO independent engines (primary: Groq
whisper-large-v3-turbo / Qwen ASR; secondary: OpenAI Whisper via OPENAI_API_KEY,
STT_CROSSCHECK=auto|on|off). The agreement record lives in
`source.raw_output.stt_crosscheck`:

    {"agreed": bool, "similarity": float, "threshold": float,
     "confidence_delta": +0.10|-0.10,
     "primary_preview": "...", "secondary_preview": "..."}

- similarity ≥ STT_AGREE_THRESHOLD (0.80) over normalized transcripts (digit/script
  folding, stt_crosscheck.normalize_transcript) = agreement → every entry from that
  note gets source.confidence += STT_AGREE_BONUS (clamped to [0,1]).
- Below threshold → confidence −= STT_DISAGREE_PENALTY; both previews stay in the
  audit trail so the divergence is reviewable, and low entries stay pending for the
  merchant to confirm (existing threshold rule).
- One engine failing degrades gracefully: the other's transcript is used, no
  crosscheck record, unchanged confidence. Both failing = STTError (busy/ask-again).

## 9. v0.5 addendum — data-quality & consistency indicators (2026-10-22, local ruling — NOT pushed)

Owner decision: Bizro does NOT build a merchant "verifier"/lie-detector. Every
input is merchant-volunteered, so omission is undetectable; a verification claim
would be technically false, adoption-poisonous, and a demo kill (the judge
question "what does it actually verify?" has no honest answer).

What ships instead: `credit_reports.report_json.data_quality` — disclosures
computed from ledger internals only (credit_agent/data_quality.py):
- backfill: entries with created_at − occurred_at > 7 days (ratio)
- burst_insertion: ≥8 entries created within any 24h window
- stock_coherence: per item, sold qty vs purchased qty from item_lines
  (violations where sold > bought × 1.05)
- window_spike: trailing-14-day daily sales ÷ in-period baseline (≥3× flagged)
- provenance: photo/voice/manual % of the ledger
- indicators[]: plain-English disclosures for the loan officer; basis_note
  states they assert nothing about intent and are not a trust score.
True verification (supplier confirmations, mobile-money anchors) is future
scope — it requires data outside the merchant's control.

## 10. v0.6 addendum — anti-fabrication forensics (2026-10-22, local ruling — NOT pushed)

Threat (owner): a merchant fabricates paper entries for months and photographs
them daily. §9's behavior disclosures don't catch a DISCIPLINED fabricator.
Response: price fabrication by attacking what the faker does NOT control.
All outputs are DISCLOSURES on the data-quality card — patterns, never verdicts.

- vision: ReceiptExtraction gains `bill_number` + `supplier_phone` (PRINTED on
  the distributor's bill book — merchant-external data); OCR prompt extracts
  them. `vision_agent/exif.py` extracts camera capture time/model from EXIF.
  Both stored in `source.raw_output.receipt_meta`.
- credit: `forensics.compute_forensics` → `report_json.data_quality.forensics`:
  bill numbers reused across dates; bill-sequence inversions vs claim dates;
  EXIF capture-time > 3 days from claim; partial-EXIF stripping fingerprint;
  round-amount share ≥ 0.9; verbatim amount repeats ≥ 4; daily-sales CV < 0.25.
- server: `POST /api/transactions/{id}/verify-supplier` — the REAL anchor:
  sends a yes/no confirmation WhatsApp to the extracted supplier phone
  (receipt_meta first, customer record fallback) and logs the request on the
  audit trail (kind=supplier_verification_request, mock-safe). Reply matching
  is future scope; the request trail is the anchor for now.

Known limits (honest): heuristics, not validated forensics; a sophisticated
fraudster can forge bill numbers and strip EXIF — each layer raises cost, the
supplier handshake is the layer that ultimately doesn't depend on the merchant.

## 11. v0.8 addendum — ledger integrity chain (2026-09-07, local — NOT pushed)

Implemented in server/app/ledger.py + tests (server/tests/test_integrity_chain.py):
every transaction row is sealed at insert with entry_hash = sha256(prev_hash |
merchant_id | kind | amount | occurred_at | description | item_lines canonical |
source_media_id | created_at), chained per merchant via prev_entry_hash.
GET /api/merchants/{id}/ledger/verify recomputes and reports amended-after-sealing
rows and chain gaps (deletions) — tamper-EVIDENT by design; edits/deletes never
rewrite hashes. Timestamps normalize to UTC before hashing (SQLite reads naive).
Wire rows carry entry_hash / prev_entry_hash / trust_tier. Timestamps normalize to
UTC before hashing (SQLite reads naive). Wire rows carry entry_hash /
prev_entry_hash / trust_tier (§12). Backfill seals pre-chain rows idempotently.
