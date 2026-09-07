/* Canonical §6.5 report (server/schema.md) → CreditReportPreview screen shape.
   The screen's shape predates the v0.2 ruling (types/schema.ts header); this
   adapter keeps the accessibility-tested screen untouched while the wire stays
   canonical. Skeleton stats are derived from transactions (same logic as the
   mock), then authoritative fields from the live payload win. */

import type { CreditReportPreview, CreditReportLineItem, OfficerPackBlock, Transaction } from '../types/schema';
import { deriveReportPreview } from './mockData';

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Canonical credit-agent officer block → the screen's OfficerPackBlock.
    The wire uses GROUPED OBJECTS (`officer.aging = {buckets: [...]}`,
    `officer.collection = {rate}`, `officer.concentration = {top_share}`,
    `officer.activity = {weeks}`) while the renderers accept the flat screen
    shape; without this mapping the whole officer pack silently hid on the live
    path (qa 2026-09-07 P1). Legacy flat shapes pass through untouched, so
    hand-built fixtures keep working. Absent pieces stay absent — honest
    absence, never a fabricated number. */
export function normalizeCanonicalOfficer(o: any): OfficerPackBlock | null {
  if (!o || typeof o !== 'object') return null;
  // aging: {buckets:[{bucket, total, customers?}]} | [{bucket, amount_pkr, count?}]
  let aging: OfficerPackBlock['aging'] = null;
  if (Array.isArray(o.aging)) {
    aging = o.aging;
  } else if (o.aging && typeof o.aging === 'object' && Array.isArray(o.aging.buckets)) {
    aging = o.aging.buckets
      .filter((b: any) => !!b && typeof b.bucket === 'string' && typeof b.total === 'number')
      .map((b: any) => ({
        bucket: b.bucket,
        amount_pkr: b.total,
        count: Array.isArray(b.customers) ? b.customers.length : (b.count ?? null),
      }));
  }
  const collection = o.collection_rate_pct ?? o.collection_rate ?? o.collection?.rate;
  const concentration = o.top_debtor_concentration_pct ?? o.concentration?.top_share;
  // weekly: activity.weeks[].count | weekly_activity number[] | {entries}
  let weekly: OfficerPackBlock['weekly_activity'] = null;
  if (o.weekly_activity !== undefined && o.weekly_activity !== null) {
    weekly = o.weekly_activity;
  } else if (Array.isArray(o.activity?.weeks)) {
    weekly = o.activity.weeks
      .filter((w: any) => !!w && typeof w.count === 'number')
      .map((w: any) => ({ week: typeof w.start === 'string' ? w.start : null, entries: w.count }));
  }
  const block: OfficerPackBlock = {
    aging,
    collection_rate: typeof collection === 'number' && Number.isFinite(collection) ? collection : null,
    top_debtor_concentration_pct:
      typeof concentration === 'number' && Number.isFinite(concentration) ? concentration : null,
    weekly_activity: weekly,
    activity_drop_pct: typeof o.activity_drop_pct === 'number' && Number.isFinite(o.activity_drop_pct) ? o.activity_drop_pct : null,
  };
  return block;
}

export function adaptCanonicalReport(
  canonical: any,
  transactions: Transaction[],
): CreditReportPreview {
  const derived = deriveReportPreview(transactions);
  const band: string = canonical?.readiness?.band ?? 'not_yet';
  const level = band === 'ready' ? 'ready' : band === 'nearly' ? 'almost' : 'not_yet';

  const canonicalLines = new Map<string, any>(
    (canonical?.line_items ?? []).map((li: any) => [String(li.ref), li]),
  );
  const line_items: CreditReportLineItem[] = derived.line_items.map((li) => {
    const c = canonicalLines.get(li.transaction_id);
    if (!c) return li;
    return {
      ...li,
      amount_pkr: c.amount_pkr ?? li.amount_pkr,
      audit: {
        ...li.audit,
        source_type: c.source_type ?? li.audit.source_type,
        media_id: c.source_media_id ?? li.audit.media_id,
        model: c.source_model ?? li.audit.model,
        confidence: c.confidence ?? li.audit.confidence,
      },
    };
  });

  // v0.7 trust evidence rides along (qa 2026-09-07 P1: the adapter previously
  // DROPPED trust/officer/limitations, hiding corroboration, the officer pack,
  // aging/collection/concentration and the payload's own limitations on the
  // live demo path).
  const trust = canonical?.trust ?? null;
  const limitations = Array.isArray(canonical?.limitations) ? canonical.limitations : null;
  const officer = normalizeCanonicalOfficer(canonical?.officer);

  return {
    ...derived,
    mock: Boolean(canonical?.mock),
    merchant: {
      id: String(canonical?.merchant?.id ?? derived.merchant.id),
      display_name: canonical?.merchant?.name ?? derived.merchant.display_name,
    },
    period: canonical?.period ?? derived.period,
    generated_at: canonical?.generated_at ?? derived.generated_at,
    generated_at_display: canonical?.generated_at_display ?? null,
    model: canonical?.model ?? derived.model,
    // Runtime attribution (audit defect 4): the provider the SERVER derived
    // from its own base URL. Never invented client-side — absent means the
    // screen claims no provider at all.
    model_provider: canonical?.model_provider ?? null,
    readiness: {
      ...derived.readiness,
      level,
      score_0_100: canonical?.readiness?.score ?? derived.readiness.score_0_100,
      summary_ur: canonical?.readiness?.label_ur ?? derived.readiness.summary_ur,
    },
    flags: (canonical?.red_flags ?? []).map((f: any) => ({
      flag: f.flag,
      count: f.count,
      // Audit defect 2: the payload's own refs are the traceable ids; the
      // screen falls back to same-flag loaded entries only when they're absent.
      transaction_ids: Array.isArray(f.refs) ? f.refs.map(String) : [],
      reason: typeof f.refs_reason === 'string' ? f.refs_reason : null,
    })),
    narrative_ur: canonical?.narrative_ur ?? derived.narrative_ur,
    line_items,
    trust,
    officer,
    limitations,
  };
}

export function isCanonicalReport(payload: any): boolean {
  return Boolean(payload?.readiness?.band !== undefined);
}
