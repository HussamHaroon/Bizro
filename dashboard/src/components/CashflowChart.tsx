/* CashflowChart — D1-1 §3, D4-1 restyle: the credit screen's monthly in/out
   SVG grouped bar chart — FLAT fills (green-fill in / red-fill out) with 2px
   ink-line strokes on every bar, square caps, gridlines as 1px ink at 20%
   alpha, and sticker value chips (raised, ink-bordered, tiny tilt) on
   hover/focus of a month group. The exact-number table stays in the DOM as
   visually-hidden markup at the call site, so screen-reader quality does not
   regress. Color is never the only signal: legend words + the sr-only table +
   per-group aria-labels carry the numbers. */

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
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-semibold text-ink-line">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-chip border border-ink-line bg-fill-green" aria-hidden="true" />
          <T en="Money in" ur="آمدنی" />
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-chip border border-ink-line bg-fill-red" aria-hidden="true" />
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
        {/* D4-1 gridlines: 1px ink at 20% alpha; the baseline rides 2px ink. */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <line
            key={p}
            x1={LEFT}
            x2={RIGHT}
            y1={BOTTOM - p * (BOTTOM - TOP)}
            y2={BOTTOM - p * (BOTTOM - TOP)}
            stroke={p === 0 ? 'var(--bizro-ink-line)' : 'var(--bizro-gridline)'}
            strokeWidth={p === 0 ? 2 : 1}
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
                  fill="var(--bizro-paper)"
                  stroke="var(--bizro-ink-line)"
                  strokeWidth="2"
                />
              )}
              {/* D4-1 bars: flat fill + 2px ink-line stroke, square caps. */}
              <rect
                x={inX}
                y={BOTTOM - inH}
                width={BAR_W}
                height={inH}
                fill="var(--bizro-green-fill)"
                stroke="var(--bizro-ink-line)"
                strokeWidth="2"
              />
              <rect
                x={outX}
                y={BOTTOM - outH}
                width={BAR_W}
                height={outH}
                fill="var(--bizro-red-fill)"
                stroke="var(--bizro-ink-line)"
                strokeWidth="2"
              />
              {/* Sticker value chips (D4-1): raised, ink-bordered, tiny tilt —
                  the exact figures always live in the sr-only table. When the
                  pair's bar tops sit in the same band, the two chips would
                  collide — one combined chip carries both values instead. */}
              {isActive &&
                (() => {
                  const topIn = BOTTOM - inH;
                  const topOut = BOTTOM - outH;
                  const inK = `${(m.inflow_pkd / 1000).toFixed(m.inflow_pkd % 1000 === 0 ? 0 : 1)}k`;
                  const outK = `${(m.outflow_pkd / 1000).toFixed(m.outflow_pkd % 1000 === 0 ? 0 : 1)}k`;
                  const chip = (
                    x: number,
                    top: number,
                    label: string,
                    text: string,
                  ) => (
                    <g key={`${label}-${x}`} transform={`rotate(-3 ${x} ${top - 16})`}>
                      <rect
                        x={x - (label.length * 4 + 7)}
                        y={top - 26}
                        width={label.length * 8 + 14}
                        height={20}
                        fill="var(--bizro-paper-raised)"
                        stroke="var(--bizro-ink-line)"
                        strokeWidth="2"
                      />
                      <text x={x} y={top - 11.5} fill={text}>
                        {label}
                      </text>
                    </g>
                  );
                  if (Math.abs(topIn - topOut) >= 26) {
                    return (
                      <g fontFamily="var(--bizro-font-numerals)" fontSize="12" fontWeight="700" textAnchor="middle">
                        {chip(inX + BAR_W / 2, topIn, inK, 'var(--bizro-ink-green)')}
                        {chip(outX + BAR_W / 2, topOut, outK, 'var(--bizro-ledger-red)')}
                      </g>
                    );
                  }
                  const label = `${inK} · ${outK}`;
                  return (
                    <g
                      fontFamily="var(--bizro-font-numerals)"
                      fontSize="12"
                      fontWeight="700"
                      textAnchor="middle"
                      transform={`rotate(-3 ${cx} ${Math.min(topIn, topOut) - 16})`}
                    >
                      <rect
                        x={cx - (label.length * 4 + 8)}
                        y={Math.min(topIn, topOut) - 26}
                        width={label.length * 8 + 16}
                        height={20}
                        fill="var(--bizro-paper-raised)"
                        stroke="var(--bizro-ink-line)"
                        strokeWidth="2"
                      />
                      <text x={cx} y={Math.min(topIn, topOut) - 11.5}>
                        <tspan fill="var(--bizro-ink-green)">{inK}</tspan>
                        <tspan fill="var(--bizro-ink-line)" opacity="0.55"> · </tspan>
                        <tspan fill="var(--bizro-ledger-red)">{outK}</tspan>
                      </text>
                    </g>
                  );
                })()}
              <text
                x={cx}
                y={H - 14}
                textAnchor="middle"
                fontFamily="var(--bizro-font-body)"
                fontSize="13"
                fontWeight="600"
                fill="var(--bizro-ink-line)"
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
            region — the card's raised-paper color to transparent (a functional
            mask, not a decorative gradient). */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-[linear-gradient(to_left,var(--bizro-paper-raised),transparent)] sm:hidden"
        />
      </div>
      <p className="flex items-center gap-1 text-xs text-ink-line opacity-70 sm:hidden">
        <T en="Swipe for more months" ur="مزید مہینوں کے لیے پھیریں" />
        <span aria-hidden="true" className="font-numerals font-semibold">→</span>
      </p>
    </div>
  );
}
