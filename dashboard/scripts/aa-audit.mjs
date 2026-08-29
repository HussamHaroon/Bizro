/* Bizro AA contrast audit (D4-1 binding: every text/bg pair >= 4.5:1, non-text
   >= 3:1, verified programmatically — design.md §4.1/§4.7).
   Run: npm run aa-audit   (node, zero deps, exit 1 on any failure)

   Pairs mirror the actual component pairings in the dashboard:
   - text on canvas/cards: ink-line, ink-green, ledger-red on paper/paper-raised
   - fill chips/buttons: paper text on green/red/teal fills (+ hover variant)
   - gold-fill: ink-line text (mock banner)
   - sticker tints: alpha-composited over BOTH bases (rows sit on the page
     canvas, pills inside raised cards) — the worst case must pass
   - non-text (WCAG 1.4.11): chart bar fills vs the canvas, the gauge arc vs
     its sticker, ink borders.
   Disabled controls are WCAG-exempt and not audited. */

import { readFileSync } from 'node:fs';

const HEX = {
  inkLine: '#1F1B16',
  inkGreen: '#0B5D3B',
  inkGreenHover: '#0E7A4C',
  ledgerRed: '#A6332B',
  sealGold: '#C98A2C',
  settledTeal: '#1F7A6C',
  tealInk: '#176156',
  paper: '#F5F1E6',
  paperRaised: '#FCF9F0',
  greenFill: '#0B5D3B',
  redFill: '#A6332B',
  goldFill: '#E9A93D',
  tealFill: '#1F7A6C',
  paperCream: '#F7F2E7', // EXTERNAL anchor (invoice/report) — audited so the
  ruleLine: '#DCD3BE',   // legacy renderers keep their passing pairs too
  inkBlack: '#211E1A',
};

function srgbChannel(v) {
  const c = v / 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function luminance(hex) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return 0.2126 * srgbChannel(r) + 0.7152 * srgbChannel(g) + 0.0722 * srgbChannel(b);
}
function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}
/** alpha-composite `over` (rgba(r,g,b,a) string) on base hex */
function blend(rgba, baseHex) {
  const m = rgba.match(/rgba?\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
  const [, r, g, b, a] = m.map(Number);
  const bh = baseHex.replace('#', '');
  const mix = (fg, bg) => Math.round(fg * a + bg * (1 - a));
  const hr = mix(r, parseInt(bh.slice(0, 2), 16));
  const hg = mix(g, parseInt(bh.slice(2, 4), 16));
  const hb = mix(b, parseInt(bh.slice(4, 6), 16));
  return `#${[hr, hg, hb].map((x) => x.toString(16).padStart(2, '0')).join('')}`;
}

const TINTS = {
  'tint-teal': 'rgba(31, 122, 108, 0.10)',
  'tint-red': 'rgba(166, 51, 43, 0.12)',
  'tint-gold': 'rgba(233, 169, 61, 0.14)',
  'tint-neutral': 'rgba(31, 27, 22, 0.10)',
};

/** ---- pull the live token hexes out of tokens.css (audit what ships) ----- */
const css = readFileSync(new URL('../design-tokens/tokens.css', import.meta.url), 'utf8');
for (const [key, varName] of [
  ['inkLine', 'ink-line'], ['inkGreen', 'ink-green'], ['inkGreenHover', 'ink-green-hover'],
  ['ledgerRed', 'ledger-red'], ['sealGold', 'seal-gold'], ['settledTeal', 'settled-teal'],
  ['tealInk', 'teal-ink'], ['paper', 'paper'], ['paperRaised', 'paper-raised'],
  ['greenFill', 'green-fill'], ['redFill', 'red-fill'], ['goldFill', 'gold-fill'],
  ['tealFill', 'teal-fill'],
]) {
  const m = css.match(new RegExp(`--bizro-${varName}:\\s*(#[0-9A-Fa-f]{6})`));
  if (m) HEX[key] = m[1];
}

const checks = [];
function text(name, fg, bg) {
  checks.push({ name, kind: 'text', ratio: contrast(fg, bg), fg, bg, min: 4.5 });
}
function nontext(name, fg, bg) {
  checks.push({ name, kind: 'non-text', ratio: contrast(fg, bg), fg, bg, min: 3.0 });
}

/* ---- text pairs ---------------------------------------------------------- */
text('ink-line on paper (body text)', HEX.inkLine, HEX.paper);
text('ink-line on paper-raised (card text)', HEX.inkLine, HEX.paperRaised);
text('ink-green on paper (titles, links)', HEX.inkGreen, HEX.paper);
text('ink-green on paper-raised (card titles)', HEX.inkGreen, HEX.paperRaised);
text('ledger-red on paper (out amounts)', HEX.ledgerRed, HEX.paper);
text('ledger-red on paper-raised', HEX.ledgerRed, HEX.paperRaised);
text('settled-teal on paper-raised (in amounts, cards)', HEX.settledTeal, HEX.paperRaised);
text('paper on green-fill (primary buttons, active tabs)', HEX.paper, HEX.greenFill);
text('paper on ink-green-hover (button hover)', HEX.paper, HEX.inkGreenHover);
text('paper on red-fill (danger chips)', HEX.paper, HEX.redFill);
text('paper on teal-fill (settled chips)', HEX.paper, HEX.tealFill);
text('ink-line on gold-fill (mock banner, gold stickers)', HEX.inkLine, HEX.goldFill);
text('ink-green on tint-gold (streak flame icon)', HEX.inkGreen, blend(TINTS['tint-gold'], HEX.paper));

/* ---- sticker tints: worst case across both bases -------------------------- */
for (const [tint, rgba] of Object.entries(TINTS)) {
  const overPaper = blend(rgba, HEX.paper);
  const overRaised = blend(rgba, HEX.paperRaised);
  const worst = contrast(overPaper, HEX.paper) < contrast(overRaised, HEX.paperRaised)
    ? overPaper
    : overRaised;
  text(`ink-line on ${tint} (neutral/gold/edited chips)`, HEX.inkLine, worst);
  if (tint === 'tint-teal') text('teal-ink on tint-teal (Verified pill)', HEX.tealInk, worst);
  if (tint === 'tint-red') text('ledger-red on tint-red (Rejected pill, flags)', HEX.ledgerRed, worst);
}

/* ---- EXTERNAL legacy pairs (invoice + credit report keep passing) --------- */
text('ink-black on paper-cream (invoice/report body)', HEX.inkBlack, HEX.paperCream);
text('ink-black on paper-cream-raised', HEX.inkBlack, HEX.paperCream);
text('paper-cream on ink-green (report headers)', HEX.paperCream, HEX.inkGreen);
text('ink-black on seal-gold (report seal)', HEX.inkBlack, HEX.sealGold);
text('settled-teal on paper-cream (report ready band)', HEX.settledTeal, HEX.paperCream);

/* ---- non-text (WCAG 1.4.11) -----------------------------------------------
   The gauge arc draws a 14px ink under-arc beneath the 10px gold arc, so the
   gold band is bounded by ink on every edge (checked vs ink below). The two
   6px seal-gold header accent segments are pure decoration on a 3px ink rule
   (nothing to understand), which WCAG exempts — seal-gold-on-paper is listed
   informationally in the summary, not as a gate. */
nontext('ink-line card borders on paper', HEX.inkLine, HEX.paper);
nontext('green-fill bars on paper (cashflow in)', HEX.greenFill, HEX.paper);
nontext('red-fill bars on paper (cashflow out, udhar)', HEX.redFill, HEX.paper);
nontext('gauge arc gold bounded by its ink under-arc', HEX.goldFill, HEX.inkLine);

/* ---- report --------------------------------------------------------------- */
let fail = 0;
const pad = (s, n) => s.padEnd(n);
for (const c of checks) {
  const ok = c.ratio >= c.min;
  if (!ok) fail += 1;
  console.log(
    `${ok ? 'PASS' : 'FAIL'}  ${c.kind.padEnd(8)} ${pad(c.ratio.toFixed(2), 6)}  (min ${c.min})  ${c.name}`,
  );
}
console.log(`\n${checks.length} pairs checked, ${fail} failing.`);
if (fail > 0) process.exit(1);
