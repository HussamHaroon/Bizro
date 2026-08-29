/* TrendSparkline (D3-3) — readiness over time, from GET /api/merchants/{id}/
   report/history (schema.md §7.2: {history: [{generated_at, score, band}, …]}
   oldest→newest). A single polyline next to the credit screen's seal gauge:
   the shape is a glance, the exact scores travel in the aria-label and the
   title tooltip. D4-1: FLAT gold-fill stroke over a thin ink underlay (keeps
   the line ≥3:1 against paper for WCAG 1.4.11 — gold alone misses it), with a
   square endpoint marker. Renders ONLY with ≥2 points (client filters) — a
   missing endpoint degrades to nothing, never an error, never a fabricated
   trend. */

import type { ReadinessHistoryPoint } from '../types/schema';
import { useT } from '../i18n';

export interface TrendSparklineProps {
  points: ReadinessHistoryPoint[];
  className?: string;
}

const W = 96;
const H = 40;
const PAD = 4;

export function TrendSparkline({ points, className = '' }: TrendSparklineProps) {
  const { pick } = useT();
  if (points.length < 2) return null;
  const step = (W - PAD * 2) / (points.length - 1);
  const y = (score: number): number =>
    H - PAD - (Math.max(0, Math.min(100, score)) / 100) * (H - PAD * 2);
  const coords = points.map((p, i) => `${(PAD + step * i).toFixed(1)},${y(p.score).toFixed(1)}`);
  const last = points[points.length - 1];
  const first = points[0];
  const trendWord =
    last.score > first.score
      ? pick('rising', 'بڑھ رہا ہے')
      : last.score < first.score
        ? pick('falling', 'گر رہا ہے')
        : pick('steady', 'برابر ہے');

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`h-10 w-24 shrink-0 ${className}`.trim()}
      role="img"
      focusable="false"
      aria-label={pick('readiness over time', 'وقت کے ساتھ تیاری')}
    >
      {/* baseline rule — 1px ink at 20% (D4-1 gridline token) */}
      <line
        x1={PAD}
        x2={W - PAD}
        y1={H - PAD}
        y2={H - PAD}
        stroke="var(--bizro-gridline)"
        strokeWidth="1"
      />
      {/* ink underlay: guarantees ≥3:1 non-text contrast under the flat gold */}
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke="var(--bizro-ink-line)"
        strokeWidth="5"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke="var(--bizro-gold-fill)"
        strokeWidth="2.5"
        strokeLinecap="square"
        strokeLinejoin="miter"
      >
        <title>
          {pick('readiness over time', 'وقت کے ساتھ تیاری')} · {first.score} → {last.score} ({trendWord})
        </title>
      </polyline>
      {/* latest point marker — where the seal gauge's score came from (D4-1:
          square dot, ink-bordered, on the flat gold) */}
      <rect
        x={W - PAD - 4.5}
        y={y(last.score) - 4.5}
        width="9"
        height="9"
        fill="var(--bizro-gold-fill)"
        stroke="var(--bizro-ink-line)"
        strokeWidth="2"
      />
    </svg>
  );
}
