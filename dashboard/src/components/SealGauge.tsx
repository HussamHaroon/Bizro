/* SealGauge — D1-1 §5, the credit-verdict centerpiece (the screenshot the
   judges will see): a 140px seal-gold ring with notary tick marks around the
   edge (the stamp metaphor), the readiness score climbing as a gold arc, the
   number in Zilla Slab at the center. Score counts up on mount (300ms
   ease-out, skipped under prefers-reduced-motion — the same budget the hero
   stats use; the seal stamp-in remains the ONE decorative animation). */

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
const R_TICKS = 66;
const CIRC = 2 * Math.PI * R_ARC;

export function SealGauge({ score, label, className = '' }: SealGaugeProps) {
  const shown = useCountUp(score);
  const clamped = Math.max(0, Math.min(100, score));
  const ticks = Array.from({ length: 48 }, (_, i) => {
    const a = (i / 48) * Math.PI * 2 - Math.PI / 2;
    return {
      x1: SIZE / 2 + R_TICKS * Math.cos(a),
      y1: SIZE / 2 + R_TICKS * Math.sin(a),
      x2: SIZE / 2 + (R_TICKS - (i % 4 === 0 ? 7 : 4)) * Math.cos(a),
      y2: SIZE / 2 + (R_TICKS - (i % 4 === 0 ? 7 : 4)) * Math.sin(a),
    };
  });

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={label}
      focusable="false"
      className={`shrink-0 print-color-exact ${className}`.trim()}
      style={{ printColorAdjust: 'exact', WebkitPrintColorAdjust: 'exact' }}
    >
      {/* stamp tick marks — notary edge, quarter ticks longer */}
      <g stroke="var(--bizro-seal-gold)" strokeWidth="2" strokeLinecap="round">
        {ticks.map((t, i) => (
          <line key={i} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} />
        ))}
      </g>
      {/* track + progress arc (rotated to start at 12 o'clock) */}
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R_ARC}
        fill="var(--bizro-paper-cream-raised)"
        stroke="var(--bizro-rule-line)"
        strokeWidth="10"
      />
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R_ARC}
        fill="none"
        stroke="var(--bizro-seal-gold)"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={CIRC}
        strokeDashoffset={CIRC * (1 - clamped / 100)}
        transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
      />
      <text
        x={SIZE / 2}
        y={SIZE / 2 + 2}
        textAnchor="middle"
        className="font-numerals"
        fontFamily="var(--bizro-font-numerals)"
        fontSize="40"
        fontWeight="700"
        fill="var(--bizro-ink-black)"
      >
        {shown}
      </text>
      <text
        x={SIZE / 2}
        y={SIZE / 2 + 26}
        textAnchor="middle"
        fontFamily="var(--bizro-font-body)"
        fontSize="13"
        fill="var(--bizro-ink-black)"
        opacity="0.7"
      >
        / 100
      </text>
    </svg>
  );
}
