/* Canonical §6.5 report (server/schema.md) → CreditReportPreview screen shape.
   The screen's shape predates the v0.2 ruling (types/schema.ts header); this
   adapter keeps the accessibility-tested screen untouched while the wire stays
   canonical. Skeleton stats are derived from transactions (same logic as the
   mock), then authoritative fields from the live payload win. */

import type { CreditReportPreview, CreditReportLineItem, Transaction } from '../types/schema';
import { deriveReportPreview } from './mockData';

/* eslint-disable @typescript-eslint/no-explicit-any */
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
  };
}

export function isCanonicalReport(payload: any): boolean {
  return Boolean(payload?.readiness?.band !== undefined);
}
