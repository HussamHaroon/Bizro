/* HeroStat — D1-1 art direction §2, D4-1 restyle: the month summary as
   large-format stats — slab-BLACK numerals, clamp(2.5rem → 4.5rem), on a
   stamped paper card (.bizro-card + hover lift). Label in small-caps
   letter-spaced 13px with the Urdu pair; the tone color rides on the label
   icon, never the numeral alone (§4.7). The number counts up on mount
   (300ms ease-out, one easing curve — NOT a second animation loop; skipped
   entirely under prefers-reduced-motion). */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { T, useT } from '../i18n';
import { urduAmountWords } from '../lib/format';

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
  en: string;
  ur: string;
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

export function HeroStat({ en, ur, value, tone, icon }: HeroStatProps) {
  const shown = useCountUp(value);
  const { mode } = useT();
  return (
    <div className="bizro-card bizro-card-hover flex flex-col gap-2 px-4 py-4 sm:px-5 sm:py-5">
      <p className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-semibold uppercase tracking-[0.04em] ${ICON_TONE_CLASS[tone]}`}>
        <span className="inline-flex">{icon}</span>
        <T en={en} ur={ur} />
      </p>
      {/* D4-1 hero numerals: clamp() scales 390px→~40px / desktop→72px, never
          below the 2.5rem floor. The amount line wraps (prefix drops a line)
          rather than truncating — amounts are never cut. */}
      <p
        className={`flex flex-wrap items-baseline gap-x-1 font-numerals font-bold leading-none tabular-nums text-[clamp(2.5rem,9.8vw,4.5rem)] ${TONE_CLASS[tone]}`}
      >
        <span className="text-[0.5em] font-semibold opacity-70">Rs</span>
        <bdi>{shown.toLocaleString('en-PK')}</bdi>
      </p>
      {/* §4.7: headline amounts appear in digits AND Urdu word form (mixed/ur
          modes; digits-only in en per the numeral ruling). */}
      {mode !== 'en' && (
        <p className="bizro-urdu text-xs leading-relaxed text-ink-line opacity-70" lang="ur">
          {urduAmountWords(value)} روپے
        </p>
      )}
    </div>
  );
}
