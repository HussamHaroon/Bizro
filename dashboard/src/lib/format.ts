/* Formatting helpers — Western digits by default per schema.md §1 (NUMERAL_STYLE env
   decides outbound text; dashboard renders Western until the real-user test lands). */

/** "Rs 4,500" — slab-numeral ledger format. Never signed: direction is kind's job. */
export function formatPkr(amount: number): string {
  return `Rs ${amount.toLocaleString('en-PK')}`;
}

/** "Rs 4,500 · چار ہزار پانچ سو روپے" is composed at call sites; this returns the
    spoken word form of the integer in Urdu (design.md §4.7: numbers in digit AND
    spoken/word form where relevant — used on amount drill-downs). */
const UR_ONES = [
  'صفر', 'ایک', 'دو', 'تین', 'چار', 'پانچ', 'چھ', 'سات', 'آٹھ', 'نو', 'دس',
  'گیارہ', 'بارہ', 'تیرہ', 'چودہ', 'پندرہ', 'سولہ', 'سترہ', 'اٹھارہ', 'انیس',
];
const UR_TENS: Record<number, string> = {
  2: 'بیس', 3: 'تیس', 4: 'چالیس', 5: 'پچاس', 6: 'ساٹھ', 7: 'ستر', 8: 'اسی', 9: 'نوے',
};

function urduUnder100(n: number): string {
  if (n < 20) return UR_ONES[n];
  const t = Math.floor(n / 10);
  const r = n % 10;
  return r === 0 ? UR_TENS[t] : `${UR_TENS[t]} ${UR_ONES[r]}`;
}

function urduUnder1000(n: number): string {
  const h = Math.floor(n / 100);
  const rest = n % 100;
  if (h === 0) return urduUnder100(rest);
  return rest === 0 ? `${UR_ONES[h]} سو` : `${UR_ONES[h]} سو ${urduUnder100(rest)}`;
}

/** Word form for whole PKR amounts up to crores — "چار ہزار پانچ سو". */
export function urduAmountWords(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '';
  if (n === 0) return UR_ONES[0];
  const parts: string[] = [];
  const crore = Math.floor(n / 10_000_000);
  const lakh = Math.floor((n % 10_000_000) / 100_000);
  const thousand = Math.floor((n % 100_000) / 1000);
  const rest = n % 1000;
  if (crore) parts.push(`${urduUnder100(crore)} کروڑ`);
  if (lakh) parts.push(`${urduUnder100(lakh)} لاکھ`);
  if (thousand) parts.push(`${urduUnder100(thousand)} ہزار`);
  if (rest) parts.push(urduUnder1000(rest));
  return parts.join(' ');
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
