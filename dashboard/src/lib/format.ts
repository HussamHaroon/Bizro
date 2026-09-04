/* Formatting helpers — Western digits throughout (owner directive 2026-09-04:
   "keep everything in english"; the per-merchant numeral_style setting and the
   Urdu word-form amounts were removed with the language-mode system).
   urduMonth() stays: the month strip in MonthlyLedgerScreen (a screen owned by
   another workstream) still renders it. */

/** "Rs 4,500" — slab-numeral ledger format. Never signed: direction is kind's job. */
export function formatPkr(amount: number): string {
  return `Rs ${amount.toLocaleString('en-PK')}`;
}

/** "21 Aug" — compact day label for ledger group headers. */
export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
  });
}

/** "21 Aug, 7:03 pm" — drill-down timestamp. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/** "August 2026" — month picker / report period heading. */
export function formatMonth(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
  });
}

/** Urdu month name for a YYYY-MM string. */
const UR_MONTHS = [
  'جنوری', 'فروری', 'مارچ', 'اپریل', 'مئی', 'جون',
  'جولائی', 'اگست', 'ستمبر', 'اکتوبر', 'نومبر', 'دسمبر',
];
export function urduMonth(ym: string): string {
  const [, m] = ym.split('-').map(Number);
  return `${UR_MONTHS[m - 1]}`;
}

/** Confidence as a percentage string, "87%"; "—" when unknown (manual entries). */
export function formatConfidence(c: number | null): string {
  return c === null ? '—' : `${Math.round(c * 100)}%`;
}

/** YYYY-MM for grouping/filtering by month. */
export function monthOf(iso: string): string {
  return iso.slice(0, 7);
}

/** Previous / next YYYY-MM. */
export function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}
