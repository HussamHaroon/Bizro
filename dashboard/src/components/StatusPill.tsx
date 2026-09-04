/* StatusPill — schema.md §1 `status` (pending | confirmed | edited | rejected).
   Always icon + word (design.md §4.7 — never a bare colored dot). D4-1:
   sticker chip — tinted bg (10–14% alpha of the token color) + 2px ink-line
   border + radius 0 (square). Text pairs per tokens.css AA list: teal-ink on
   tint-teal, ledger-red on tint-red, ink-line on tint-gold / tint-neutral.
   Stickers stay SQUARE — the one rotated sticker per screen is the seal.

   D4r fix 1 (owner review 2026-08-29, row de-density): in ledger ROWS this is
   the ONE status chip — an optional `flag` folds the row's price/quality flag
   INTO the chip (▲ + flag word, red tint) instead of a second chip. The
   underlying status rides the title attribute; on AI rows the SealMark glyph
   still shows verified vs pending. */

import type { TransactionFlag, TransactionStatus } from '../types/schema';
import { IconCheck, IconEdited, IconPending, IconRejected } from './icons';

export interface StatusPillProps {
  status: TransactionStatus;
  /** Fold a transaction flag into the chip (rows only): ▲ + flag word, red. */
  flag?: Exclude<TransactionFlag, 'none'> | null;
  className?: string;
}

interface PillSpec {
  icon: typeof IconCheck;
  label: string;
  classes: string;
}

const SPECS: Record<TransactionStatus, PillSpec> = {
  pending: {
    icon: IconPending,
    label: 'Confirm pending',
    classes: 'bizro-tint-neutral text-ink-line',
  },
  confirmed: {
    icon: IconCheck,
    label: 'Verified',
    classes: 'bizro-tint-teal text-teal-ink',
  },
  edited: {
    icon: IconEdited,
    label: 'Edited',
    classes: 'bizro-tint-gold text-ink-line',
  },
  rejected: {
    icon: IconRejected,
    label: 'Rejected',
    classes: 'bizro-tint-red text-ledger-red',
  },
};

const FLAG_SPEC: Record<Exclude<TransactionFlag, 'none'>, string> = {
  price_anomaly: 'Price check',
  total_mismatch: 'Total check',
  duplicate_suspect: 'Duplicate?',
  low_confidence: 'Low confidence',
};

export function StatusPill({ status, flag = null, className = '' }: StatusPillProps) {
  // Flagged variant: the flag is the row's most urgent status signal, so its
  // word + ▲ glyph take the chip; the status word moves to the title (and the
  // SealMark / drill-down still carry it). Icon + word stays intact (§4.7).
  if (flag) {
    const f = FLAG_SPEC[flag];
    const st = SPECS[status];
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line bizro-tint-red px-2.5 py-1 text-xs font-semibold text-ledger-red ${className}`}
        title={`${f} — ${st.label}`}
      >
        <span aria-hidden="true">▲</span>
        {f}
        {/* QA wave-7 P2-1: edited-vs-confirmed is invisible once the flag takes
            the chip (title tooltips don't exist for low-literacy/mobile users),
            so the edited word must survive INSIDE the chip. */}
        {status === 'edited' && <> · Edited</>}
      </span>
    );
  }

  const { icon: Icon, label, classes } = SPECS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line px-2.5 py-1 text-xs font-semibold ${classes} ${className}`}
    >
      <Icon className="h-[18px] w-[18px]" />
      {label}
    </span>
  );
}
