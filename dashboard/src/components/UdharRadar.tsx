/* UdharRadar — design.md §7.1, the top differentiator widget: money owed TO the
   shopkeeper, per customer (schema.md §3 derived view). Total in ledger-red slab
   numerals with Urdu word form; per-customer share bars are red fills BUT the
   number + name always carry the signal (color never alone, §4.7). */

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
  const max = items.length ? items[0].outstanding_pkd : 0;

  return (
    <section className={`bizro-card px-4 py-4 ${className}`} aria-labelledby="udhar-radar-title">
      <header className="mb-3 flex items-center gap-3">
        <IconRadar className="h-8 w-8 text-ledger-red" />
        <div>
          <h2 id="udhar-radar-title" className="flex flex-wrap items-baseline gap-x-2">
            <T
              en="Udhar Radar"
              ur="ادھار راڈار"
              className="font-numerals text-lg font-semibold text-ink-black"
              urClassName="text-base font-semibold text-ink-black"
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
        <ul>
          {items.map((u) => (
            <li key={u.customer_id} className="bizro-rule-h flex items-center gap-3 py-2 last:border-b-0">
              <IconCustomer className="h-6 w-6 text-ink-green" />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="truncate font-semibold text-ink-black">{u.name}</span>
                  <span className="font-numerals font-semibold text-ledger-red">
                    {formatPkr(u.outstanding_pkd)}
                  </span>
                </div>
                {/* Share bar — the number+name carry the meaning; the bar is only
                    a proportional glance. */}
                <div
                  className="h-1.5 w-full overflow-hidden rounded-card bg-paper-cream"
                  role="img"
                  aria-label={pick(
                    `${u.name}: Rs ${u.outstanding_pkd.toLocaleString('en-PK')} outstanding`,
                    `${u.name}: ادھار ${u.outstanding_pkd.toLocaleString('en-PK')} روپے`,
                  )}
                >
                  <div
                    className="h-full rounded-card bg-ledger-red"
                    style={{ width: `${Math.max(4, Math.round((u.outstanding_pkd / max) * 100))}%` }}
                  />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
