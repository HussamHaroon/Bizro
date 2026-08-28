// WCAG 2.1 contrast audit for every text/background pair used by the site.
// Run: npm run contrast   (node >= 18, zero deps)
// Law: design.md §4.7 / D4-1 — every text pair >= 4.5:1 (AA body text).

function srgbToLinear(c) {
  const cs = c / 255;
  return cs <= 0.04045 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
}

function luminance(hex) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (
    0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
  );
}

function contrast(fg, bg) {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

const INK = "#1F1B16"; // border-ink — text baseline on light fills
const WHITE = "#FFFFFF";
const CANVAS = "#F5F1E6";
const CARD = "#FCF9F0";
const GREEN = "#0B5D3B";
const RED = "#A6332B";
const GOLD = "#E9A93D";
const TEAL = "#1F7A6C";

// [label, fg, bg, where it appears]
const pairs = [
  ["ink on canvas (body text)", INK, CANVAS],
  ["ink on card (card body text)", INK, CARD],
  ["ink on gold (stickers, hl, gold chips)", INK, GOLD],
  ["canvas on ink (demo-frame tag, footer)", CANVAS, INK],
  ["white on green (primary buttons, band, green chips)", WHITE, GREEN],
  ["white on red (red chips)", WHITE, RED],
  ["white on teal (teal chips)", WHITE, TEAL],
  ["green on canvas (Urdu accents, links)", GREEN, CANVAS],
  ["green on card (mini-stat figures, meta icons)", GREEN, CARD],
  ["red on canvas (stat number 10.3%)", RED, CANVAS],
  ["red on card (stat number, amounts, stamp text)", RED, CARD],
  ["teal on card (stat number ~33%)", TEAL, CARD],
];

let fail = 0;
console.log("Bizro site — WCAG contrast audit (threshold 4.5:1 AA)\n");
for (const [label, fg, bg] of pairs) {
  const ratio = contrast(fg, bg);
  const ok = ratio >= 4.5;
  if (!ok) fail += 1;
  console.log(
    `${ok ? "PASS" : "FAIL"}  ${ratio.toFixed(2)}:1  ${label}  [${fg} on ${bg}]`,
  );
}
console.log(
  `\n${pairs.length - fail}/${pairs.length} pairs pass AA (>= 4.5:1).`,
);
process.exit(fail === 0 ? 0 : 1);
