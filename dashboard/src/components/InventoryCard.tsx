/* InventoryCard — v0.9 derived-stock widget (server/app/inventory.py): per-item
   stock computed from EXISTING transactions' item_lines — receipts add, sales +
   udhar remove (schema.md §1 direction; no new tables, the udhar-radar pattern).

   Honesty law (§9 disclosure framing): a NEGATIVE in_stock is DATA, shown with
   the word "negative" in ledger-red — never hidden, never "corrected". Flag
   marks are icon + WORD, never color alone (design.md §4.7); the number always
   carries the signal. Rows are separated by rule-lines, not nested shadows
   (Khata Modern tokens only). Compact: at most MAX_ROWS rows, then a count. */

import type { InventoryItem, InventoryView } from '../types/schema';
import { IconFlag, IconPending, IconRejected } from './icons';

const MAX_ROWS = 6;

export interface InventoryCardProps {
  view: InventoryView;
  className?: string;
}

function flagWord(flag: InventoryItem['flag']): string | null {
  return flag === 'negative' ? 'negative' : flag === 'low' ? 'low' : null;
}

export function InventoryCard({ view, className = '' }: InventoryCardProps) {
  const flagged = view.items.filter((i) => i.flag !== 'ok').length;

  return (
    <section
      className={`bizro-card bizro-card-hero px-5 py-5 ${className}`}
      aria-labelledby="inventory-card-title"
    >
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <IconPending className="h-9 w-9 text-ink-green" />
        <div className="min-w-0">
          <h2 id="inventory-card-title" className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-[22px] font-semibold text-ink-line">Stock on hand</span>
          </h2>
          <p className="text-xs text-ink-line opacity-75">What your shelves hold, from your receipts</p>
        </div>
        {flagged > 0 && (
          /* Icon + word, never color alone (§4.7) — the header states the count. */
          <p className="ml-auto flex items-center gap-1.5 text-sm font-semibold text-ledger-red">
            <IconFlag className="h-5 w-5 shrink-0" aria-hidden="true" />
            {flagged} {flagged === 1 ? 'item needs restocking' : 'items need restocking'}
          </p>
        )}
      </header>

      {view.items.length === 0 ? (
        <p className="px-1 py-3 text-sm text-ink-line">
          Send receipt photos to track stock — items appear here as you log purchases and sales.
        </p>
      ) : (
        <ul className="flex flex-col">
          {view.items.slice(0, MAX_ROWS).map((it) => {
            const word = flagWord(it.flag);
            return (
              <li
                key={it.item}
                className="flex min-h-touch flex-wrap items-center gap-x-3 gap-y-1 border-t-2 border-ink-line py-2.5 first:border-t-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink-line">{it.item}</p>
                  <p className="text-xs text-ink-line opacity-70">
                    bought {it.bought} · sold {it.sold}
                    {it.unit ? ` (${it.unit})` : ''}
                  </p>
                </div>
                {word && (
                  <span className="flex items-center gap-1 text-sm font-semibold text-ledger-red">
                    {it.flag === 'negative' ? (
                      <IconRejected className="h-5 w-5 shrink-0" aria-hidden="true" />
                    ) : (
                      <IconFlag className="h-5 w-5 shrink-0" aria-hidden="true" />
                    )}
                    {word}
                  </span>
                )}
                <span
                  className={`font-numerals text-lg font-semibold tabular-nums ${
                    word ? 'text-ledger-red' : 'text-ink-green'
                  }`}
                >
                  {it.in_stock}
                  {it.unit ? ` ${it.unit}` : ''}
                </span>
              </li>
            );
          })}
          {view.items.length > MAX_ROWS && (
            <li className="border-t-2 border-ink-line py-2.5 text-xs text-ink-line opacity-70">
              +{view.items.length - MAX_ROWS} more items in this ledger
            </li>
          )}
        </ul>
      )}

      {/* The server's derivation note — the fine print that keeps the card an
          honest disclosure (stock is DERIVED; a negative is a data-quality
          signal, not an accusation). */}
      {view.items.length > 0 && view.note && (
        <p className="mt-3 border-t-2 border-ink-line pt-3 text-xs leading-relaxed text-ink-line opacity-70">
          {view.note}
        </p>
      )}
    </section>
  );
}
