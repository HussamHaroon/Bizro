
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
