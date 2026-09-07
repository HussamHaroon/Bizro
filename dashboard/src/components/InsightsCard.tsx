/* InsightsCard — v0.9 derived-insights widget (credit_agent.insights, GET
   /api/merchants/{id}/insights): three lists DERIVED from data the ledger
   already holds — item_lines + occurred_at + unit_price. No new tables, no
   forecasting, no ML: every row is a PATTERN from the past ("Based on your
   last N days"), never a prediction.

   Reading order = decision order: restock FIRST (the action — the SAME low/
   negative flags the InventoryCard shows, ranked by recent demand), then
   demand timing (when things sell), then price movers (what costs are doing).

   Honesty law (design.md §4.7): direction/flag marks are icon + WORD, never
   color alone; "flat" prices say flat instead of inventing a trend; an empty
   ledger says "not enough history yet" — numbers are never invented. Rows are
   separated by rule-lines, not nested shadows (Khata Modern tokens only). */

import type { MerchantInsights, PriceTrendRow, RestockRow } from '../types/schema';
import { formatPkr } from '../lib/format';
import { IconExpense, IconFlag, IconRejected, IconReport, IconSale } from './icons';

export interface InsightsCardProps {
  insights: MerchantInsights;
  className?: string;
}

const MAX_ROWS = 5;

function RestockRowLine({ r }: { r: RestockRow }) {
  return (
    <li className="flex min-h-touch flex-wrap items-center gap-x-3 gap-y-1 border-t-2 border-ink-line py-2.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink-line">{r.item}</p>
        <p className="text-xs text-ink-line opacity-70">
          in stock {r.in_stock}
          {r.unit ? ` ${r.unit}` : ''}
          {r.weekly_demand > 0 ? ` · ~${r.weekly_demand} sold/week` : ''}
        </p>
      </div>
      {r.flag === 'negative' ? (
        <span className="flex items-center gap-1 text-sm font-semibold text-ledger-red">
          <IconRejected className="h-5 w-5 shrink-0" aria-hidden="true" />
          negative
        </span>
      ) : (
        <span className="flex items-center gap-1 text-sm font-semibold text-ledger-red">
          <IconFlag className="h-5 w-5 shrink-0" aria-hidden="true" />
          low
        </span>
      )}
    </li>
  );
}

function DemandRowLine({ r }: { r: MerchantInsights['demand_timing'][number] }) {
  return (
    <li className="flex min-h-touch flex-wrap items-center gap-x-3 gap-y-1 border-t-2 border-ink-line py-2.5">
      <IconSale className="h-6 w-6 shrink-0 text-settled-teal" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink-line">{r.item}</p>
        <p className="text-xs text-ink-line opacity-70">
          {r.best_day}s · {r.best_window}
        </p>
      </div>
      <span className="font-numerals text-sm font-semibold tabular-nums text-ink-line">
        ~{r.weekly_units}/wk
      </span>
    </li>
  );
}

function PriceRowLine({ r }: { r: PriceTrendRow }) {
  const rising = r.direction === 'up';
  const flat = r.direction === 'flat';
  return (
    <li className="flex min-h-touch flex-wrap items-center gap-x-3 gap-y-1 border-t-2 border-ink-line py-2.5">
      <IconExpense
        className={`h-6 w-6 shrink-0 ${flat ? 'text-ink-line opacity-70' : rising ? 'text-ledger-red' : 'text-settled-teal'}`}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink-line">{r.item}</p>
        <p className="text-xs text-ink-line opacity-70">
          {formatPkr(r.first_median)} → {formatPkr(r.second_median)}
          {r.unit ? ` per ${r.unit}` : ''}
        </p>
      </div>
      {/* Icon + word, never color alone (§4.7): the direction word carries the
          signal; within ±1% the honest word is "flat", not a fake trend. */}
      <span
        className={`flex items-center gap-1 text-sm font-semibold ${
          flat ? 'text-ink-line opacity-70' : rising ? 'text-ledger-red' : 'text-ink-green'
        }`}
      >
        {!flat && <IconFlag className="h-5 w-5 shrink-0" aria-hidden="true" />}
        {r.direction} {Math.abs(r.pct_change)}%
      </span>
    </li>
  );
}

export function InsightsCard({ insights, className = '' }: InsightsCardProps) {
  const { demand_timing, restock_now, price_trends } = insights;
  const empty = demand_timing.length === 0 && restock_now.length === 0 && price_trends.length === 0;

  return (
    <section
      className={`bizro-card bizro-card-hero px-5 py-5 ${className}`}
      aria-labelledby="insights-card-title"
    >
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <IconReport className="h-9 w-9 text-ink-green" />
        <div className="min-w-0">
          <h2 id="insights-card-title" className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-[22px] font-semibold text-ink-line">Shop insights</span>
          </h2>
          <p className="text-xs text-ink-line opacity-75">Patterns from your entries — not predictions</p>
        </div>
        {restock_now.length > 0 && (
          <p className="ml-auto flex items-center gap-1.5 text-sm font-semibold text-ledger-red">
            <IconFlag className="h-5 w-5 shrink-0" aria-hidden="true" />
            {restock_now.length} {restock_now.length === 1 ? 'item to restock' : 'items to restock'}
          </p>
        )}
      </header>

      {empty ? (
        <p className="px-1 py-3 text-sm text-ink-line">
          Not enough history yet — keep sending voice notes and receipts.
        </p>
      ) : (
        <div className="flex flex-col gap-5">
          {/* 1. Restock — the ACTION first: flagged stock ranked by how fast
              each item actually sells (same flags as the stock card). */}
          {restock_now.length > 0 && (
            <section aria-labelledby="insights-restock-title">
              <h3 id="insights-restock-title" className="pb-1 text-sm font-semibold uppercase tracking-wide text-ink-line opacity-80">
                Restock soon
              </h3>
              <ul className="flex flex-col">
                {restock_now.slice(0, MAX_ROWS).map((r) => (
                  <RestockRowLine key={r.item} r={r} />
                ))}
              </ul>
              <p className="pt-2 text-xs text-ink-line opacity-70">{restock_now[0].note}</p>
            </section>
          )}

          {/* 2. Demand timing — when things sell (a rate over the window,
              never a forecast). */}
          {demand_timing.length > 0 && (
            <section aria-labelledby="insights-demand-title">
              <h3 id="insights-demand-title" className="pb-1 text-sm font-semibold uppercase tracking-wide text-ink-line opacity-80">
                When things sell
              </h3>
              <ul className="flex flex-col">
                {demand_timing.slice(0, MAX_ROWS).map((r) => (
                  <DemandRowLine key={r.item} r={r} />
                ))}
              </ul>
              <p className="pt-2 text-xs text-ink-line opacity-70">{demand_timing[0].note}</p>
            </section>
          )}

          {/* 3. Price movers — what supplier costs are doing (medians, so one
              misread receipt cannot dominate). */}
          {price_trends.length > 0 && (
            <section aria-labelledby="insights-price-title">
              <h3 id="insights-price-title" className="pb-1 text-sm font-semibold uppercase tracking-wide text-ink-line opacity-80">
                Price moves
              </h3>
              <ul className="flex flex-col">
                {price_trends.slice(0, MAX_ROWS).map((r) => (
                  <PriceRowLine key={r.item} r={r} />
                ))}
              </ul>
              <p className="pt-2 text-xs text-ink-line opacity-70">{price_trends[0].note}</p>
            </section>
          )}
        </div>
      )}
    </section>
  );
}
