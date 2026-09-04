/* ProgressCardButton (growth) — the ledger's share chip: opens the weekly
   ProgressCard in a modal overlay (house lightbox pattern, SourceMedia) with a
   Download action → offscreen 1200×675 canvas → toDataURL('image/png') →
   <a download="bizro-week.png"> click. Week numbers are derived from the
   transactions the ledger screen ALREADY fetched — no new API calls; the streak
   is the server's week-scoped value (schema.md §7.3). The chip only appears
   while viewing the CURRENT month: that is the one fetch guaranteed to cover
   the running week (a past month's window would build a wrong "this week"). */

import { useEffect, useMemo, useState } from 'react';
import { monthOf } from '../lib/format';
import type { Transaction, TransactionKind } from '../types/schema';
import { CARD_HEIGHT, CARD_WIDTH, ProgressCard, drawProgressCard } from './ProgressCard';
import type { WeekCardStats } from './ProgressCard';
import { IconSend } from './icons';

const FILE_NAME = 'bizro-week.png';

/** Last-7-days slice of the already-loaded month (rejected entries excluded —
    same rule as the ledger's sumKind) → the card's four numbers. */
function deriveWeekStats(txs: Transaction[], streakWeeks: number): WeekCardStats {
  const from = new Date();
  from.setDate(from.getDate() - 6);
  const fromDay = [
    from.getFullYear(),
    String(from.getMonth() + 1).padStart(2, '0'),
    String(from.getDate()).padStart(2, '0'),
  ].join('-');
  const week = txs.filter((t) => t.status !== 'rejected' && t.occurred_at.slice(0, 10) >= fromDay);
  const sumKind = (kinds: TransactionKind[]): number =>
    week.filter((t) => kinds.includes(t.kind)).reduce((s, t) => s + t.amount_pkr, 0);
  return {
    salesCount: week.filter((t) => t.kind === 'sale').length,
    // "Money in" — same recipe as the ledger hero stat: sales + udhar settlements.
    moneyIn: sumKind(['sale', 'udhar_settlement']),
    collected: sumKind(['udhar_settlement']),
    streakWeeks,
  };
}

export interface ProgressCardButtonProps {
  /** The month's transactions already fetched by the ledger screen (null while loading). */
  txs: Transaction[] | null;
  /** Month currently viewed — the chip renders only on the live month. */
  month: string;
  /** Server's week-scoped streak (0 when the optional endpoint is absent). */
  streakWeeks: number;
}

export function ProgressCardButton({ txs, month, streakWeeks }: ProgressCardButtonProps) {
  const [open, setOpen] = useState(false);

  const stats = useMemo(
    () => (txs ? deriveWeekStats(txs, streakWeeks) : null),
    [txs, streakWeeks],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const isCurrentMonth = month === monthOf(new Date().toISOString());
  if (!stats || !isCurrentMonth) return null;
  const cardStats = stats; // narrowed alias for the closures below

  async function download() {
    await document.fonts.ready; // the PNG must carry the real fonts, like the preview
    const canvas = document.createElement('canvas');
    canvas.width = CARD_WIDTH;
    canvas.height = CARD_HEIGHT;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    drawProgressCard(ctx, cardStats); // same pure draw → identical image
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = FILE_NAME;
    a.click();
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="bizro-btn-press inline-flex min-h-touch min-w-touch items-center gap-2 self-start rounded-chip border-[3px] border-ink-line bg-paper-raised px-4 text-sm font-semibold text-ink-line transition-colors duration-200 ease-out hover:bg-paper"
      >
        <IconSend className="h-5 w-5 text-ink-green" />
        Share this week
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop doubles as the close affordance (click outside closes). */}
          <button
            type="button"
            aria-label="Close"
            onClick={() => setOpen(false)}
            className="absolute inset-0 h-full w-full cursor-default bg-ink-line/80"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Weekly progress card"
            className="bizro-card relative w-full max-w-xl p-3 sm:p-4"
          >
            <ProgressCard stats={cardStats} className="block h-auto w-full" />
            <div className="mt-3 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="bizro-btn-quiet inline-flex min-h-touch items-center rounded-chip border-[3px] border-ink-line bg-paper-raised px-4 text-sm font-semibold text-ink-line"
              >
                Close
              </button>
              <button
                type="button"
                onClick={download}
                className="bizro-btn-press inline-flex min-h-touch items-center gap-2 rounded-button border-[3px] border-ink-line bg-fill-green px-5 text-sm font-semibold text-paper"
              >
                Download
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
