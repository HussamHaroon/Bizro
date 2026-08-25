/* ReceiptCard — design.md §4.4: cream card, thin rule-line border, torn/perforated
   top edge via ONE inline SVG, amount in slab numerals. The flourish is reserved
   for receipt-like summaries (month total, invoice preview) — never applied to
   every card. NO box-shadow (elevation rule: rule-lines read as "register"). */

import type { ReactNode } from 'react';
import { T } from '../i18n';

export interface ReceiptCardProps {
  title: string;
  titleUr: string;
  meta?: string;
  children: ReactNode;
  className?: string;
}

/** Deterministic perforation path across a 240-wide viewBox; scales horizontally
    with preserveAspectRatio="none" so the teeth stretch smoothly at any width. */
const TOOTH = 20;
const TOP_Y = 4.5;
const BUMP = `a ${TOOTH / 2} ${TOP_Y} 0 0 1 ${TOOTH} 0`;
const PERF_FILL = `M0 10 L0 ${TOP_Y} ${BUMP.repeat(12)} L240 10 Z`;
const PERF_EDGE = `M0 ${TOP_Y} ${BUMP.repeat(12)}`;

export function ReceiptCard({ title, titleUr, meta, children, className = '' }: ReceiptCardProps) {
  return (
    <section className={`w-full ${className}`}>
      <svg
        className="block w-full"
        height="10"
        viewBox="0 0 240 10"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <path d={PERF_FILL} fill="var(--bizro-paper-cream-raised)" />
        <path d={PERF_EDGE} fill="none" stroke="var(--bizro-rule-line)" strokeWidth="1" />
      </svg>
      <div className="rounded-b-card border-x border-b border-rule-line bg-paper-raised px-4 py-4 sm:px-5">
        <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="flex flex-wrap items-baseline gap-x-2">
            <T
              en={title}
              ur={titleUr}
              className="font-numerals text-lg font-semibold text-ink-black"
              urClassName="text-base font-semibold text-ink-black"
            />
          </h2>
          {meta && <p className="text-xs text-ink-black opacity-75">{meta}</p>}
        </header>
        {children}
      </div>
    </section>
  );
}
