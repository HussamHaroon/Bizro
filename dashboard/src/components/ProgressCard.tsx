/* ProgressCard (growth) — the merchant's shareable "this week" card, drawn on a
   1200×675 <canvas> with the Canvas 2D API (zero new dependencies) so ONE pure
   draw function serves the on-screen preview AND the downloaded PNG.
   Art direction: D4-1 stamped-ledger. The canvas is a non-web surface, so it
   reads the locked token values directly (same rule as tokens.json consumers —
   the invoice renderer): paper #F5F1E6 · ink-line #1F1B16 · fill-gold #E9A93D.
   8px ink frame + hard zero-blur offset shadow, square gold accent squares,
   numerals in Zilla Slab (font-numerals), headings in bold IBM Plex Sans.
   drawProgressCard is a PURE function of its stats: fixed coordinates, no DOM
   measurement, no layout reads — the image renders identically anywhere. */

import { useEffect, useRef } from 'react';
import { useNumerals, useT } from '../i18n';
import { formatAmount } from '../lib/format';
import type { NumeralStyle } from '../types/schema';

/** Full-size backing store of the share image (16:9 social card). */
export const CARD_WIDTH = 1200;
export const CARD_HEIGHT = 675;

/** The four shareable numbers — all derivable from data the ledger already has. */
export interface WeekCardStats {
  salesCount: number;
  moneyIn: number;
  collected: number;
  streakWeeks: number;
}

/* Locked token values (design-tokens/tokens.json — canvas = non-web surface). */
const INK = '#1F1B16'; // ink-line
const PAPER = '#F5F1E6'; // paper
const GOLD = '#E9A93D'; // fill-gold

/* Token font stacks (tokens.css): font-body / font-numerals. Webfonts are
   npm-packaged (@fontsource) and loaded by main.tsx — the fallbacks only cover
   the first paint. */
const SANS = '"IBM Plex Sans", "Noto Sans Urdu", system-ui, sans-serif';
const NUMERAL_FONT = '"Zilla Slab", "IBM Plex Sans", serif';

/** Canvas letter-spacing where the engine supports it; older engines simply
    draw untracked — the card stays correct either way. */
function setTracking(ctx: CanvasRenderingContext2D, px: string): void {
  if ('letterSpacing' in ctx) ctx.letterSpacing = px;
}

/** Pure draw: stats (+ numeral style) in, painted 1200×675 card out. Same
    inputs always produce the same image — no reads beyond the canvas itself. */
export function drawProgressCard(
  ctx: CanvasRenderingContext2D,
  stats: WeekCardStats,
  numerals: NumeralStyle = 'western',
): void {
  ctx.save();
  ctx.textBaseline = 'alphabetic';
  ctx.textAlign = 'left';

  // Paper canvas + the stamped frame: hard zero-blur ink shadow (D4-1), 8px ink border.
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  const fx = 32;
  const fy = 32;
  const fw = CARD_WIDTH - 64;
  const fh = CARD_HEIGHT - 64;
  ctx.fillStyle = INK;
  ctx.fillRect(fx + 18, fy + 18, fw, fh); // hard offset shadow, zero blur
  ctx.fillStyle = PAPER;
  ctx.fillRect(fx, fy, fw, fh);
  ctx.lineWidth = 8;
  ctx.strokeStyle = INK;
  ctx.strokeRect(fx + 4, fy + 4, fw - 8, fh - 8);

  // BIZRO wordmark + gold underline bar (fixed width — no text measurement).
  const LEFT = 88;
  ctx.fillStyle = INK;
  ctx.font = `700 88px ${SANS}`;
  setTracking(ctx, '10px');
  ctx.fillText('BIZRO', LEFT, 150);
  setTracking(ctx, '0px');
  ctx.fillStyle = GOLD;
  ctx.fillRect(LEFT, 172, 236, 12);

  // Heading.
  ctx.fillStyle = INK;
  ctx.font = `700 52px ${SANS}`;
  ctx.fillText('This week', LEFT, 262);

  // Four stat blocks, 2×2 — gold accent square + word label + big slab numerals.
  const blocks: { x: number; y: number; label: string; value: string }[] = [
    { x: LEFT, y: 316, label: 'SALES', value: stats.salesCount.toLocaleString('en-PK') },
    { x: 640, y: 316, label: 'MONEY IN', value: formatAmount(stats.moneyIn, numerals) },
    { x: LEFT, y: 464, label: 'COLLECTED', value: formatAmount(stats.collected, numerals) },
    { x: 640, y: 464, label: 'STREAK WEEKS', value: String(stats.streakWeeks) },
  ];
  for (const b of blocks) {
    ctx.fillStyle = GOLD;
    ctx.fillRect(b.x, b.y + 2, 26, 26);
    ctx.fillStyle = INK;
    ctx.font = `600 24px ${SANS}`;
    setTracking(ctx, '3px');
    ctx.fillText(b.label, b.x + 40, b.y + 22);
    setTracking(ctx, '0px');
    ctx.font = `700 72px ${NUMERAL_FONT}`;
    ctx.fillText(b.value, b.x, b.y + 104);
  }

  // Footer.
  ctx.fillStyle = INK;
  ctx.font = `600 26px ${SANS}`;
  ctx.fillText('Made with Bizro · bizro-pk.vercel.app', LEFT, 622);

  ctx.restore();
}

/** The card at display size: fixed 1200×675 backing store, CSS-scaled to its
    container. Redraws on stats/numeral changes and once webfonts settle. */
export function ProgressCard({
  stats,
  className = '',
}: {
  stats: WeekCardStats;
  className?: string;
}) {
  const { pick } = useT();
  const { numerals } = useNumerals();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    drawProgressCard(ctx, stats, numerals);
    // Webfonts settle after first paint — redraw once so the preview carries
    // the real IBM Plex Sans / Zilla Slab instead of the fallback stack.
    let alive = true;
    void document.fonts.ready.then(() => {
      if (alive) drawProgressCard(ctx, stats, numerals);
    });
    return () => {
      alive = false;
    };
  }, [stats, numerals]);

  return (
    <canvas
      ref={canvasRef}
      width={CARD_WIDTH}
      height={CARD_HEIGHT}
      role="img"
      aria-label={pick(
        'Weekly progress card: sales, money in, collected, streak weeks',
        'ہفتہ کارڈ: فروخت، آمدنی، وصولی، ہفتوں کا سلسلہ',
      )}
      className={className}
    />
  );
}
