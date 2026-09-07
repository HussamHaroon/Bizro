/* Type definitions mirroring server/schema.md §1 (canonical transaction JSON) and §3
   (Udhar Radar derived view) EXACTLY. Cross-agent contract — if schema.md changes, this
   file changes with it (flag the Orchestrator first, AGENTS.md §1).
   The `id` field is the DB primary key (schema.md §2 transactions.id) carried on API
   list responses so the dashboard can call PATCH /api/transactions/{id}/confirm etc. */

export type TransactionKind =
  | 'sale'
  | 'expense'
  | 'udhar_given'
  | 'udhar_settlement';

/** 'text' = a typed WhatsApp message parsed by the same pipeline as voice
    (server ck_tx_source_type widened 2026-09-04). */
export type SourceType = 'voice' | 'photo' | 'text' | 'manual';

export type TransactionFlag =
  | 'none'
  | 'price_anomaly'
  | 'total_mismatch'
  | 'duplicate_suspect'
  | 'low_confidence';

export type TransactionStatus = 'pending' | 'confirmed' | 'edited' | 'rejected';

/** schema.md §1 — `source` block of a transaction. */
export interface TransactionSource {
  type: SourceType;
  /** uuid of the media blob (media_blobs.id); null for manual entries. */
  media_id: string | null;
  /** model id that parsed it, e.g. qwen3.5-omni-plus / qwen-vl-ocr / qwen3.5-ocr; null for manual. */
  model: string | null;
  /** ∈ [0,1]; REQUIRED for every AI-parsed entry (audit trail, design.md §7.2). */
  confidence: number | null;
  raw_output?: { transcript?: string } | Record<string, unknown> | null;
}

/** schema.md §1 — one line of an OCR-parsed receipt. */
export interface ItemLine {
  item: string;
  qty: number;
  unit: string;
  unit_price: number;
  line_total: number;
}

/** schema.md §11 — trust tier on every wire row (server/app/schemas.py
    transaction_to_wire: null tier renders as "self_reported"). The ladder:
    self_reported (the merchant told us) → customer_confirmed (the counterparty
    on the entry confirmed it) → third_party (an external party — e.g. the
    distributor via POST /transactions/{id}/verify-supplier — confirmed it). */
export type TrustTier = 'self_reported' | 'customer_confirmed' | 'third_party';

/** schema.md §1 — canonical transaction JSON (pipeline output / API wire format). */
export interface Transaction {
  id: string;
  kind: TransactionKind;
  /** Always positive; direction is implied by kind (schema.md §1 rule). */
  amount_pkr: number;
  currency: 'PKR';
  counterparty: { name: string; phone: string | null } | null;
  description: string | null;
  item_lines: ItemLine[];
  occurred_at: string; // ISO 8601 with offset, e.g. 2026-08-21T19:03:00+05:00
  source: TransactionSource;
  flag: TransactionFlag;
  status: TransactionStatus;
  /** Clean Urdu confirmation text (text-out path per design.md §2). */
  confirmation_ur: string | null;
  /* ---- §11 integrity chain (transaction_to_wire) -----------------------------
     Optional in TS: rows from a pre-§11 server simply lack them, and the UI
     renders the neutral default instead of erroring. Edits never rewrite the
     sealed hash — a mismatch IS the "amended after sealing" signal. */
  trust_tier?: TrustTier | null;
  entry_hash?: string | null;
  prev_entry_hash?: string | null;
}

/** GET /api/merchants/{id}/ledger/verify (schema.md §11, server/app/ledger.py
    verify_chain). Tamper-EVIDENT, not tamper-PROOF: an edit after sealing is a
    visible amendment (still auditable via original_values), a broken link is a
    vanished/out-of-band row. The verdict goes to the officer; the officer decides. */
export interface LedgerVerifyResult {
  valid: boolean;
  /** Sealed rows that were recomputed. */
  checked: number;
  /** Transaction ids whose CURRENT fields no longer match their sealed hash. */
  amended_after_sealing: string[];
  /** Rows with no seal yet (inserted by a pre-sealing path). */
  unsealed: number;
  broken_at: string | null;
  details: { tx_id: string; problem: string; [key: string]: unknown }[];
}

/** schema.md §3 — Udhar Radar derived view: outstanding per customer.
    outstanding = Σ(udhar_given) − Σ(udhar_settlement) over confirmed+pending. */
export interface UdharOutstanding {
  customer_id: string;
  name: string;
  phone: string | null;
  outstanding_pkd: number;
}

/* ---- v0.3 addendum (schema.md §7 / D1-2) --------------------------------------
   GET /api/merchants — loan-officer merchant picker. The special id 'me' resolves
   server-side to the first merchant (single-merchant demo default). */

export interface MerchantSummary {
  id: string;
  display_name: string;
  wa_id: string;
}

/* ---- v0.3 addendum (schema.md §7.2–7.3, ruling D3-1) ---------------------------
   GET /api/merchants/{id}/report/history → {"history": [{generated_at, score,
   band}, …]} oldest→newest from credit_reports (dashboard: trend sparkline).
   GET /api/merchants/{id}/streak → {streak_weeks, best_streak_weeks,
   current_week_positive} — consecutive Mon–Sun PKT weeks with net cash-flow > 0;
   zero-entry weeks break the streak (dashboard: ledger hero chip).
   Both are OPTIONAL endpoints: the client returns null on any absence and the
   UI degrades to nothing — a missing feature, never an error. */

export interface ReadinessHistoryPoint {
  generated_at: string; // ISO 8601
  score: number; // 0–100
  band: string; // readiness level, e.g. ready | almost | not_yet
}

export interface SavingsStreak {
  streak_weeks: number;
  best_streak_weeks: number;
  current_week_positive: boolean;
}

/* ---- v0.4 addendum (schema.md §8, ruling D4-2) — per-merchant settings --------
   GET  /api/merchants/{id}/settings → the row below; a MISSING row is 200 with
   the implied defaults (language 'mixed', numeral_style mirroring the server
   NUMERAL_STYLE env) and updated_at null — never a 404. The 'me' sentinel id
   is honored. PUT with any subset of the two fields → validates, upserts,
   returns the MERGED row with a fresh updated_at; unknown keys are a 422. */

/** schema.md §8 merchant_settings.language CHECK constraint. */
export type LanguageSetting = 'ur' | 'en' | 'mixed';

/** schema.md §8 merchant_settings.numeral_style CHECK constraint. */
export type NumeralStyle = 'western' | 'urdu';

/** GET/PUT /api/merchants/{id}/settings response (server/app/api.py
   _settings_to_wire). updated_at is null until the merchant first saves. */
export interface MerchantSettings {
  language: LanguageSetting;
  numeral_style: NumeralStyle;
  updated_at: string | null;
}

/** PUT body — any subset (extra keys are a server-side 422, so the client
   type stays closed too). */
export interface MerchantSettingsPut {
  language?: LanguageSetting;
  numeral_style?: NumeralStyle;
}

/* ---- Credit Readiness report preview ----------------------------------------
   GET /api/merchants/{id}/report/preview (schema.md §4). schema.md fixes the storage
   row (credit_reports: report_json JSONB + narrative_ur) but not the JSON's internal
   shape — credit-agent owns the final contract. This is the frontend's DRAFT v0
   consumption shape; every line item references a Transaction so the audit drill-down
   (source + confidence, design.md §7.2) is derived from real transaction data, never
   fabricated. Align with credit-agent before wiring the live endpoint. */

export type ReadinessLevel = 'ready' | 'almost' | 'not_yet';

export interface CreditReportLineItem {
  transaction_id: string;
  /** Short human label for the report row, e.g. "Weekly supplier purchase". */
  label: string;
  label_ur: string;
  month: string; // YYYY-MM the entry falls in
  amount_pkr: number;
  /** Audit-trail fields (design.md §7.2) — snapshot from the referenced transaction. */
  audit: {
    source_type: SourceType;
    media_id: string | null;
    model: string | null;
    confidence: number | null;
    status: TransactionStatus;
    flag: TransactionFlag;
  };
}

export interface CreditReportPreview {
  mock: boolean;
  merchant: { id: string; display_name: string };
  period: { start: string; end: string }; // YYYY-MM-DD
  generated_at: string;
  /** Pre-formatted PKT label from the payload, e.g. "Sep 3, 2026, 7:51 pm".
      Absent → the screen formats generated_at itself. */
  generated_at_display?: string | null;
  model: string | null; // the model id ACTUALLY used, e.g. 'minimax/minimax-m3:free'
  /** Provider the SERVER derived from its own base URL at generation time.
      Null/absent → no provider is claimed (honest absence, audit defect 4). */
  model_provider?: string | null;
  readiness: {
    level: ReadinessLevel;
    score_0_100: number;
    summary_en: string;
    summary_ur: string;
  };
  monthly_cashflow: {
    month: string; // YYYY-MM
    inflow_pkd: number; // sales + udhar settlements
    outflow_pkd: number; // expenses + udhar given
    net_pkd: number;
    entries: number;
  }[];
  consistency: {
    months_active: number;
    avg_entries_per_week: number;
    longest_gap_days: number;
  };
  flags: {
    flag: Exclude<TransactionFlag, 'none'>;
    count: number;
    /** Traceable entry ids behind the flag (canonical red_flags[].refs). */
    transaction_ids: string[];
    /** Honest reason when the payload stored no refs (red_flags[].refs_reason). */
    reason?: string | null;
  }[];
  sourcing: {
    total_entries: number;
    ai_entries: number; // source.type voice|photo|text (anything not manual)
    ai_share: number; // 0..1
    avg_confidence: number | null; // over AI entries
    by_source: Record<
      SourceType,
      { entries: number; avg_confidence: number | null }
    >;
  };
  narrative_ur: string | null;
  line_items: CreditReportLineItem[];
  /* ---- v0.7 (in flight, optional per contract) ------------------------------- */
  trust?: ReportTrustBlock | null;
  officer?: OfficerPackBlock | null;
  /** Honest disclosures — what this report does NOT know (schema.md §9:
      every input is merchant-volunteered; omission is not detectable). */
  limitations?: string[] | null;
}

/* ---- v0.7 addendum (credit-agent, landing in parallel) — officer pack ---------
   Additions to report_json the credit agent is shipping: a `trust` block
   (corroboration), an `officer` block (visit metrics), and root `limitations`.
   EVERY field is optional here by contract: the UI renders a section when its
   fields exist and hides it gracefully when they don't (optional chaining +
   empty-state fallbacks), so the build works against today's API AND tomorrow's.
   Field names below mirror the credit-agent's planned wire keys; unknown extra
   keys on the payload are ignored. */

/** report_json.trust — corroboration across the ledger, 0..100 ("_pct" suffix
    is the wire convention; absent → no corroboration claim is rendered). */
export interface ReportTrustBlock {
  corroboration_pct?: number | null;
}

/** One aging bucket. `bucket` is the server's label (e.g. "0-30", "31-60",
    "60+"); amount_pkr is the outstanding sum in it; count is optional. */
export interface OfficerAgingBucket {
  bucket: string;
  amount_pkr: number;
  count?: number | null;
}

/** One weekly-activity point. Accepts both plausible wire shapes: a bare
    number per week or an object with the week label + entries count. */
export interface OfficerWeekPoint {
  week?: string | null;
  entries: number;
}

/** report_json.officer — the loan-officer pack, computed by the credit agent
    over ledger internals only. Absent block → the whole section stays hidden. */
export interface OfficerPackBlock {
  /** Outstanding by days-outstanding bucket, oldest last. */
  aging?: OfficerAgingBucket[] | null;
  /** Collected ÷ billed over the period. Both wire spellings accepted;
      `collection_rate` may be a 0..1 fraction OR already a percentage —
      the renderer normalizes (≤1 → ×100). */
  collection_rate?: number | null;
  collection_rate_pct?: number | null;
  /** Largest single debtor's share of outstanding, 0..100. WARN > 40. */
  top_debtor_concentration_pct?: number | null;
  /** Entries per week, oldest→newest (recent weeks last). */
  weekly_activity?: OfficerWeekPoint[] | number[] | null;
  /** Percent drop in activity vs the prior baseline, when the server flags
      one; null/absent → no alert banner. */
  activity_drop_pct?: number | null;
}

/* ---- v0.9 addendum (inventory agent) — derived stock, no new tables ----------
   GET /api/merchants/{id}/inventory → per-item stock DERIVED from existing
   transactions' item_lines: bought = Σ qty over `expense` lines (goods IN),
   sold = Σ qty over `sale` + `udhar_given` lines (goods OUT — udhar_settlement
   is money-only per schema.md §1). Names merge case/whitespace-insensitively
   (credit_agent.data_quality._norm_item). flag: "negative" when sold exceeds
   bought (a data-quality disclosure in the §9 stock_coherence spirit — shown,
   never hidden), "low" when in_stock ≤ max(2, 10% of bought), else "ok".
   OPTIONAL endpoint: the client returns null on any absence and the card
   doesn't render — a missing feature, never an error. */

export interface InventoryItem {
  item: string;
  unit: string | null;
  bought: number;
  sold: number;
  in_stock: number;
  flag: 'ok' | 'low' | 'negative';
}

export interface InventoryView {
  merchant_id: string;
  items: InventoryItem[];
  /** Server's honest derivation note — surfaces on the card as fine print. */
  note: string;
}
