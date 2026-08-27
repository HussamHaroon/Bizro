/* TrendSparkline (D3-3) — readiness over time, from GET /api/merchants/{id}/
   report/history (schema.md §7.2: {history: [{generated_at, score, band}, …]}
   oldest→newest). A single seal-gold polyline next to the credit screen's seal
   gauge: the shape is a glance, the exact scores travel in the aria-label and
   the title tooltip. Renders ONLY with ≥2 points (client filters) — a missing
   endpoint degrades to nothing, never an error, never a fabricated trend. */

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
      {/* baseline rule (the register line the trend is read against) */}
      <line
        x1={PAD}
        x2={W - PAD}
        y1={H - PAD}
        y2={H - PAD}
        stroke="var(--bizro-rule-line)"
        strokeWidth="1"
      />
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke="var(--bizro-seal-gold)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <title>
          {pick('readiness over time', 'وقت کے ساتھ تیاری')} · {first.score} → {last.score} ({trendWord})
        </title>
      </polyline>
      {/* latest point dot — where the seal gauge's score came from */}
      <circle
        cx={W - PAD}
        cy={y(last.score)}
        r="3.5"
        fill="var(--bizro-seal-gold)"
        stroke="var(--bizro-paper-cream-raised)"
        strokeWidth="1.5"
      />
    </svg>
  );
}
