/* LedgerIntegrityChip — schema.md §11 verdict as a chip: the hash chain over
   the merchant's ledger, recomputed server-side by GET /api/merchants/{id}/
   ledger/verify. Tamper-EVIDENT, not tamper-PROOF (ledger.py header) — and the
   chip says exactly that, because the honest framing IS the feature:

     sealed + valid        settled-teal — "Chain intact · N sealed"
     N amended after seal  gold — "N amended after sealing" + the framing line:
                             amended ≠ hidden, it is the audit working (edits
                             stay visible via original_values)
     broken chain          ledger-red — "Chain broken at <id>" — a sealed link
                             vanished; the gap IS the detection

   OPTIONAL endpoint: fetch failure / older server → the chip renders nothing
   (a missing feature, never an error, never a fake "all good"). Icon + word
   always (§4.7); the `result` prop lets galleries and tests force a state
   without any network. */

import { useEffect, useState } from 'react';
import { fetchLedgerVerify } from '../api/client';
import type { LedgerVerifyResult } from '../types/schema';
import { IconCheck, IconEdited, IconFlag } from './icons';

export interface LedgerIntegrityChipProps {
  /** Force a verdict (gallery / tests / already-fetched data). When omitted
      the chip fetches it itself; null hides the chip (honest absence). */
  result?: LedgerVerifyResult | null;
  /** Explicit merchant id (committee view); defaults to the active merchant. */
  merchantId?: string;
  className?: string;
}

export function LedgerIntegrityChip({ result, merchantId, className = '' }: LedgerIntegrityChipProps) {
  const [fetched, setFetched] = useState<LedgerVerifyResult | null>(null);

  useEffect(() => {
    if (result !== undefined) return; // a forced verdict owns the render
    let alive = true;
    setFetched(null); // merchant switch → fresh verdict, never a stale one
    fetchLedgerVerify(merchantId).then((v) => {
      if (alive) setFetched(v);
    });
    return () => {
      alive = false;
    };
  }, [result, merchantId]);

  const v = result !== undefined ? result : fetched;
  if (!v) return null;
  // Nothing sealed and nothing unsealed = nothing to claim — no empty bravado.
  if (v.checked === 0 && v.unsealed === 0) return null;

  const broken = v.broken_at != null;
  const amendedCount = Array.isArray(v.amended_after_sealing) ? v.amended_after_sealing.length : 0;
  const unsealedNote = v.unsealed > 0 ? ` · ${v.unsealed} unsealed` : '';

  const chip =
    broken || amendedCount > 0 ? (
      broken ? (
        <span
          className="inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line bizro-tint-red px-2.5 py-1 text-xs font-semibold text-ledger-red"
          title="A sealed link in the hash chain is missing — the gap is the detection"
        >
          <IconFlag className="h-[18px] w-[18px]" />
          Chain broken · entry {v.broken_at}
        </span>
      ) : (
        <span
          className="inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line bizro-tint-gold px-2.5 py-1 text-xs font-semibold text-ink-line"
          title="These entries were edited after the seal — every edit stays visible in the audit trail (original_values)"
        >
          <IconEdited className="h-[18px] w-[18px]" />
          {amendedCount} {amendedCount === 1 ? 'entry' : 'entries'} amended after sealing
        </span>
      )
    ) : (
      <span
        className="inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line bizro-tint-teal px-2.5 py-1 text-xs font-semibold text-teal-ink"
        title="Every sealed entry's hash recomputed server-side and matched — no silent edits, no missing links"
      >
        <IconCheck className="h-[18px] w-[18px]" />
        Chain intact · {v.checked} sealed{unsealedNote}
      </span>
    );

  return (
    <span
      role="status"
      className={`inline-flex flex-wrap items-center gap-x-2 gap-y-1 ${className}`}
    >
      {chip}
      {broken ? (
        <span className="text-xs text-ledger-red">
          A sealed link is missing — the gap is the detection.
        </span>
      ) : amendedCount > 0 ? (
        <span className="text-xs text-ink-line opacity-75">
          Amended ≠ hidden — every edit stays visible in the audit trail.
        </span>
      ) : (
        <span className="text-xs text-ink-line opacity-75">
          Hash-sealed · tamper-evident, not tamper-proof.
        </span>
      )}
    </span>
  );
}
