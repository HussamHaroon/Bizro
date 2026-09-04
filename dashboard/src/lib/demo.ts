/* Shared honesty helper (audit WOUND 4): seeded demo history carries
   `mock: true` inside source.raw_output. Both the ledger row and its audit
   drill-down must label those rows as examples instead of presenting them as
   real AI parses. Lives outside the components so LedgerRow ↔ AuditTrail stay
   acyclic (LedgerRow renders AuditTrail). */

import type { Transaction } from '../types/schema';

export function isDemoRow(t: Transaction): boolean {
  const raw = t.source.raw_output as Record<string, unknown> | null | undefined;
  return !!raw && raw.mock === true;
}
