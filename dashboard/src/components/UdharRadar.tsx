/* UdharRadar — design.md §7.1, the top differentiator widget: money owed TO the
   shopkeeper, per customer (schema.md §3 derived view). D1-1 §4 art direction:
   proportional horizontal bars — ink-green fill on a rule-line track, rounded
   caps — for the TOP-3 customers; name + Rs amount + Urdu word form on every
   row. Total stays ledger-red slab numerals with the Urdu word form. The bar is
   only a proportional glance; number + name always carry the signal (§4.7). */

import type { UdharOutstanding } from '../types/schema';
import { AmountText } from './AmountText';
import { IconCustomer, IconRadar } from './icons';
import { formatPkr } from '../lib/format';
import { T, useT } from '../i18n';

export interface UdharRadarProps {
  items: UdharOutstanding[];
  className?: string;
}

export function UdharRadar({ items, className = '' }: UdharRadarProps) {
  const { pick } = useT();
  const total = items.reduce((s, u) => s + u.outstanding_pkd, 0);
  const top3 = items.slice(0, 3);
  const max = top3.length ? top3[0].outstanding_pkd : 0;

  return (
    <section className={`bizro-card bizro-card-hero bizro-card-hover px-5 py-5 ${className}`} aria-labelledby="udhar-radar-title">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <IconRadar className="h-9 w-9 text-ledger-red" />
        <div className="min-w-0">
          <h2 id="udhar-radar-title" className="flex flex-wrap items-baseline gap-x-2">
            <T
              en="Udhar Radar"
              ur="ادھار راڈار"
              className="font-numerals text-xl font-semibold text-ink-black"
              urClassName="text-xl font-semibold text-ink-black"
            />
          </h2>
          <p className="text-xs text-ink-black opacity-75">
            <T en="Who owes you" ur="کون مقروض ہے" />
          </p>
        </div>
        {total > 0 && (
          <div className="ml-auto text-right">
            <AmountText value={total} tone="out" size="lg" showWords />
          </div>
        )}
      </header>

      {items.length === 0 ? (
        <p className="px-1 py-3 text-sm text-ink-black">
          <T en="No udhar outstanding — everyone has paid up." ur="کوئی ادھار باقی نہیں" />
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {top3.map((u) => (
            <li key={u.customer_id} className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="flex min-w-0 items-center gap-2">
                  <IconCustomer className="h-6 w-6 shrink-0 text-ink-green" />
                  <span className="truncate font-semibold text-ink-black">{u.name}</span>
                </span>
                <span className="text-right">
                  <span className="font-numerals text-lg font-semibold tabular-nums text-ledger-red">
                    {formatPkr(u.outstanding_pkd)}
                  </span>
                </span>
              </div>
              {/* Proportional bar — ink-green fill on the rule-line track; the
                  number + name carry the meaning, the bar is a glance. */}
              <div
                className="h-2 w-full overflow-hidden rounded-card bg-rule-line"
                role="img"
                aria-label={pick(
                  `${u.name}: Rs ${u.outstanding_pkd.toLocaleString('en-PK')} outstanding`,
                  `${u.name}: ادھار ${u.outstanding_pkd.toLocaleString('en-PK')} روپے`,
                )}
              >
                <div
                  className="h-full rounded-card bg-ink-green transition-[width] duration-200 ease-out"
                  style={{ width: `${Math.max(4, Math.round((u.outstanding_pkd / max) * 100))}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
