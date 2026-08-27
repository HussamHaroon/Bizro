/* CashflowChart — D1-1 §3: the credit screen's monthly in/out becomes a clean
   SVG grouped bar chart (settled-teal in / ledger-red out, rounded 4px caps,
   rule-line gridlines, value labels on hover/focus of a month group). The
   exact-number table stays in the DOM as visually-hidden markup at the call
   site, so screen-reader quality does not regress. Color is never the only
   signal: legend words + the sr-only table + per-group aria-labels carry the
   numbers. */

import { useState } from 'react';
import { T, useT } from '../i18n';
import { formatPkr, urduMonth } from '../lib/format';

export interface CashflowMonth {
  month: string; // YYYY-MM
  inflow_pkd: number;
  outflow_pkd: number;
  net_pkd: number;
  entries: number;
}

export interface CashflowChartProps {
  months: CashflowMonth[];
}

const W = 640;
const H = 250;
const TOP = 28;
const BOTTOM = H - 34;
const LEFT = 12;
const RIGHT = W - 12;
const BAR_W = 26;
const BAR_GAP = 8;
const GROUP_GAP = 26;
const ROUNDS = [10_000, 20_000, 50_000, 100_000, 200_000];

function niceMax(v: number): number {
  for (const r of ROUNDS) if (v <= r) return r;
  return Math.ceil(v / 100_000) * 100_000;
}

function shortMonth(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-GB', { month: 'short' });
}

export function CashflowChart({ months }: CashflowChartProps) {
  const { mode, pick } = useT();
  const [active, setActive] = useState<string | null>(null);

  if (months.length === 0) return null;

  const max = niceMax(Math.max(1, ...months.map((m) => Math.max(m.inflow_pkd, m.outflow_pkd))));
  const slot = (RIGHT - LEFT - GROUP_GAP) / months.length;

  return (
    <div className="flex flex-col gap-2">
      {/* Legend — color + word, never color alone. */}
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-semibold text-ink-black">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-card bg-settled-teal" aria-hidden="true" />
          <T en="Money in" ur="آمدنی" />
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-card bg-ledger-red" aria-hidden="true" />
          <T en="Money out" ur="خرچ" />
        </span>
      </p>

      {/* Mobile-first (D3): below sm the chart keeps its full-width geometry
          (bars + value labels stay readable — amounts are never truncated) and
          scrolls horizontally inside a labeled, keyboard-focusable region with
          a right-edge fade + swipe hint as the scroll affordance. sm+ fits
          whole. Printing flattens the scroll (print:min-w-0 / overflow). */}
      <div className="relative sm:static">
        <div
          className="overflow-x-auto rounded-button print:overflow-visible"
          role="region"
          tabIndex={0}
          aria-label={pick('Monthly cash-flow bars — scrollable', 'ماہانہ نقد رواں — پھیرا جا سکتا ہے')}
        >
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full min-w-[560px] print:min-w-0"
            role="group"
            aria-label={pick('Monthly cash-flow bars', 'ماہانہ نقد رواں')}
          >
        {/* rule-line gridlines at quarters */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <line
            key={p}
            x1={LEFT}
            x2={RIGHT}
            y1={BOTTOM - p * (BOTTOM - TOP)}
            y2={BOTTOM - p * (BOTTOM - TOP)}
            stroke="var(--bizro-rule-line)"
            strokeWidth="1"
            strokeDasharray={p === 0 ? undefined : '3 4'}
          />
        ))}

        {months.map((m, i) => {
          const cx = LEFT + GROUP_GAP / 2 + slot * i + slot / 2;
          const inH = Math.max(2, (m.inflow_pkd / max) * (BOTTOM - TOP));
          const outH = Math.max(2, (m.outflow_pkd / max) * (BOTTOM - TOP));
          const inX = cx - BAR_W - BAR_GAP / 2;
          const outX = cx + BAR_GAP / 2;
          const isActive = active === m.month;
          const label = pick(
            `${shortMonth(m.month)} — in ${formatPkr(m.inflow_pkd)}, out ${formatPkr(m.outflow_pkd)}, net ${formatPkr(Math.abs(m.net_pkd))}${m.net_pkd < 0 ? ' negative' : ''}`,
            `${urduMonth(m.month)} — آمدنی ${m.inflow_pkd.toLocaleString('en-PK')} روپے، خرچ ${m.outflow_pkd.toLocaleString('en-PK')} روپے`,
          );
          return (
            <g
              key={m.month}
              tabIndex={0}
              role="img"
              aria-label={label}
              onMouseEnter={() => setActive(m.month)}
              onMouseLeave={() => setActive((cur) => (cur === m.month ? null : cur))}
              onFocus={() => setActive(m.month)}
              onBlur={() => setActive((cur) => (cur === m.month ? null : cur))}
            >
              {isActive && (
                <rect
                  x={cx - slot / 2 + 2}
                  y={TOP - 20}
                  width={slot - 4}
                  height={BOTTOM - TOP + 34}
                  rx="4"
                  fill="var(--bizro-paper-cream)"
                  stroke="var(--bizro-rule-line)"
                />
              )}
              <rect x={inX} y={BOTTOM - inH} width={BAR_W} height={inH} rx="4" fill="var(--bizro-settled-teal)" />
              <rect x={outX} y={BOTTOM - outH} width={BAR_W} height={outH} rx="4" fill="var(--bizro-ledger-red)" />
              {isActive && (
                <g fontFamily="var(--bizro-font-numerals)" fontSize="12" fontWeight="600" textAnchor="middle">
                  <text x={inX + BAR_W / 2} y={BOTTOM - inH - 6} fill="var(--bizro-settled-teal)">
                    {(m.inflow_pkd / 1000).toFixed(m.inflow_pkd % 1000 === 0 ? 0 : 1)}k
                  </text>
                  <text x={outX + BAR_W / 2} y={BOTTOM - outH - 6} fill="var(--bizro-ledger-red)">
                    {(m.outflow_pkd / 1000).toFixed(m.outflow_pkd % 1000 === 0 ? 0 : 1)}k
                  </text>
                </g>
              )}
              <text
                x={cx}
                y={H - 14}
                textAnchor="middle"
                fontFamily="var(--bizro-font-body)"
                fontSize="13"
                fontWeight="600"
                fill="var(--bizro-ink-black)"
                opacity="0.85"
              >
                {mode === 'ur' ? urduMonth(m.month) : mode === 'en' ? shortMonth(m.month) : `${shortMonth(m.month)} · ${urduMonth(m.month)}`}
              </text>
            </g>
          );
        })}
          </svg>
        </div>
        {/* Scroll affordance (phones only): right-edge fade over the scroll
            region — the token's raised-paper color to transparent. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-[linear-gradient(to_left,var(--bizro-paper-cream-raised),transparent)] sm:hidden"
        />
      </div>
      <p className="flex items-center gap-1 text-xs text-ink-black opacity-70 sm:hidden">
        <T en="Swipe for more months" ur="مزید مہینوں کے لیے پھیریں" />
        <span aria-hidden="true" className="font-numerals font-semibold">→</span>
      </p>
    </div>
  );
}
