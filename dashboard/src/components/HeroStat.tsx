/* HeroStat — D1-1 art direction §2: the month summary becomes large-format
   stats. Zilla Slab 48–64px numerals on a raised cream card (paperCreamRaised +
   shadow-card via .bizro-card), label in small-caps letter-spaced 12px with the
   Urdu pair. The number counts up on mount (300ms ease-out, one easing curve —
   NOT a second animation loop; skipped entirely under prefers-reduced-motion). */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { T } from '../i18n';

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

const TONE_CLASS: Record<HeroTone, string> = {
  in: 'text-settled-teal',
  out: 'text-ledger-red',
  neutral: 'text-ink-green',
};

export function HeroStat({ en, ur, value, tone, icon }: HeroStatProps) {
  const shown = useCountUp(value);
  return (
    <div className="bizro-card bizro-card-hover flex flex-col gap-2 px-4 py-4 sm:px-5 sm:py-5">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-semibold uppercase tracking-[0.08em] text-ink-black opacity-80">
        <span className="inline-flex">{icon}</span>
        <T en={en} ur={ur} />
      </p>
      {/* Mobile-first numerals (D3): clamp() scales 390px→~35px / desktop→60px,
          never below the 32px legibility floor. The amount line wraps (prefix
          drops a line) rather than truncating — amounts are never cut. */}
      <p
        className={`flex flex-wrap items-baseline gap-x-1 font-numerals font-bold leading-none tabular-nums text-[clamp(2rem,8.9vw,3.75rem)] ${TONE_CLASS[tone]}`}
      >
        <span className="text-[0.5em] font-semibold opacity-60">Rs</span>
        <bdi>{shown.toLocaleString('en-PK')}</bdi>
      </p>
    </div>
  );
}
