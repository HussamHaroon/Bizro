/* HeroStat — D1-1 art direction §2, D4-1 restyle: the month summary as
   large-format stats — slab-BLACK numerals, clamp(2.5rem → 4.5rem), on a
   stamped paper card (.bizro-card + hover lift). Label in small-caps
   letter-spaced 13px; the tone color rides on the label icon, never the
   numeral alone (§4.7). The number counts up on mount (300ms ease-out, one
   easing curve — NOT a second animation loop; skipped entirely under
   prefers-reduced-motion). English-only (owner directive 2026-09-04): the
   ur prop is accepted from older call sites but never rendered. */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';

/** 0 → target over `duration` ms, ease-out quad. Reduced motion = instant. */
export function useCountUp(target: number, duration = 300): number {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !Number.isFinite(target) || target === 0) {
      setDisplay(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - (1 - p) * (1 - p);
      setDisplay(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return display;
}

export type HeroTone = 'in' | 'out' | 'neutral';

export interface HeroStatProps {
  /** English label — the only one rendered. */
  en: string;
  /** Ignored — the dashboard renders English only. */
  ur?: string;
  value: number;
  tone: HeroTone;
  /** Icon + word pair (§4.7) — the label word carries the meaning. */
  icon: ReactNode;
}

/** D4-1: hero numerals are SLAB BLACK (ink-line) — the biggest marks on the
    page; money direction rides on the paired icon + label word, never color
    alone (§4.7). */
const TONE_CLASS: Record<HeroTone, string> = {
  in: 'text-ink-line',
  out: 'text-ink-line',
  neutral: 'text-ink-line',
};

const ICON_TONE_CLASS: Record<HeroTone, string> = {
  in: 'text-settled-teal',
  out: 'text-ledger-red',
  neutral: 'text-ink-green',
};

export function HeroStat({ en, value, tone, icon }: HeroStatProps) {
  const shown = useCountUp(value);
  return (
    <div className="bizro-card bizro-card-hover flex flex-col gap-2 px-4 py-4 sm:px-5 sm:py-5">
      <p className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-semibold uppercase tracking-[0.04em] ${ICON_TONE_CLASS[tone]}`}>
        <span className="inline-flex">{icon}</span>
        {en}
      </p>
      {/* D4-1 hero numerals: clamp() scales 390px→40px floor / wide desktop→72px
          ceiling, never below the 2.5rem floor. The amount line wraps (prefix
          drops a line) rather than truncating — amounts are never cut.
          Coefficient is 5.6vw, NOT 9.8vw: 9.8vw hit the 4.5rem=72px ceiling at
          ~735px while the KPI grid only goes 3-column at md=768px, so across
          768–1050px the digits overflowed the card and were sliced mid-glyph
          (measured 831px: "Rs 1,441.08" → "Rs 1,441.0", rect right=862).
          5.6vw keeps the whole string inside the card content box from 768px up
          (43.0px @768 … 58.8px @1050, all ≤ track−46px) and still reaches the
          72px ceiling on wide desktops (≥1286px, where max-w-6xl gives the card
          a 354.67px track that fits 72px). */}
      <p
        className={`flex flex-wrap items-baseline gap-x-1 font-numerals font-bold leading-none tabular-nums text-[clamp(2.5rem,5.6vw,4.5rem)] ${TONE_CLASS[tone]}`}
      >
        <span className="text-[0.5em] font-semibold opacity-70">Rs</span>
        <bdi>{shown.toLocaleString('en-PK')}</bdi>
      </p>
    </div>
  );
}
