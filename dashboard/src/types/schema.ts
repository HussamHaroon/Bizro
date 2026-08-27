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

export type SourceType = 'voice' | 'photo' | 'manual';

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

/** schema.md §1 — canonical transaction JSON (pipeline output / API wire format). */
export interface Transaction {
  id: string;
  kind: TransactionKind;
  /** Always positive; direction is implied by kind (schema.md §1 rule). */
  amount_pkd: number;
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
  amount_pkd: number;
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
  model: string | null; // e.g. 'qwen3.7-plus'
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
  flags: { flag: Exclude<TransactionFlag, 'none'>; count: number; transaction_ids: string[] }[];
  sourcing: {
    total_entries: number;
    ai_entries: number; // source.type voice|photo
    ai_share: number; // 0..1
    avg_confidence: number | null; // over AI entries
    by_source: Record<
      SourceType,
      { entries: number; avg_confidence: number | null }
    >;
  };
  narrative_ur: string | null;
  line_items: CreditReportLineItem[];
}
