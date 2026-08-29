/* SealGauge — D1-1 §5, the credit-verdict centerpiece (the screenshot the
   judges will see). D4-1 restyle: a FLAT chunky ring — 10px ink-line track,
   solid gold-fill arc (the D3-4 gradient + glow are retired) — with the slab
   score numeral at the center, the whole gauge mounted on a sticker score
   card (paper-raised, 3px ink border, hard shadow) tilted rotate(-2deg).
   Score counts up on mount (300ms ease-out, skipped under
   prefers-reduced-motion — the same budget the hero stats use; the seal
   stamp-in remains the ONE decorative animation). Print flattens the tilt. */

import { useCountUp } from './HeroStat';

export interface SealGaugeProps {
  /** 0–100 readiness score (schema.md report readiness.score). */
  score: number;
  /** Accessible description, built by the caller per active language mode. */
  label: string;
  /** Responsive sizing (D3 mobile-first): the viewBox stays 140 — pass e.g.
   *  "h-[104px] w-[104px] md:h-[140px] md:w-[140px]" to scale the whole gauge. */
  className?: string;
}

const SIZE = 140;
const R_ARC = 54;
const CIRC = 2 * Math.PI * R_ARC;

export function SealGauge({ score, label, className = '' }: SealGaugeProps) {
  const shown = useCountUp(score);
  const clamped = Math.max(0, Math.min(100, score));

  return (
    /* Sticker score card (D4-1): raised, ink-bordered, hard shadow, tilted.
       `rotate` (independent property) keeps the tilt out of transform's way;
       print flattens it with the shadows. */
    <span
      className="inline-block rotate-[-2deg] rounded-card border-[3px] border-ink-line bg-paper-raised p-2 shadow-hard-sm print:rotate-0"
      style={{ printColorAdjust: 'exact', WebkitPrintColorAdjust: 'exact' }}
    >
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={label}
        focusable="false"
        className={`shrink-0 ${className}`.trim()}
      >
        {/* chunky flat track: 10px ink-line */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R_ARC}
          fill="var(--bizro-paper-raised)"
          stroke="var(--bizro-ink-line)"
          strokeWidth="10"
        />
        {/* progress arc — solid gold-fill over a wider ink under-arc, so the
            gold band is bounded by ink on every edge (AA 1.4.11: gold vs ink
            8.3:1; gold vs paper alone would be 1.9:1) */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R_ARC}
          fill="none"
          stroke="var(--bizro-ink-line)"
          strokeWidth="14"
          strokeDasharray={CIRC}
          strokeDashoffset={CIRC * (1 - clamped / 100)}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R_ARC}
          fill="none"
          stroke="var(--bizro-gold-fill)"
          strokeWidth="10"
          strokeDasharray={CIRC}
          strokeDashoffset={CIRC * (1 - clamped / 100)}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        <text
          x={SIZE / 2}
          y={SIZE / 2 + 6}
          textAnchor="middle"
          className="font-numerals"
          fontFamily="var(--bizro-font-numerals)"
          fontSize="48"
          fontWeight="700"
          fill="var(--bizro-ink-line)"
        >
          {shown}
        </text>
        <text
          x={SIZE / 2}
          y={SIZE / 2 + 30}
          textAnchor="middle"
          fontFamily="var(--bizro-font-body)"
          fontSize="12.5"
          fontWeight="600"
          fill="var(--bizro-ink-line)"
          opacity="0.75"
        >
          / 100
        </text>
      </svg>
    </span>
  );
}
