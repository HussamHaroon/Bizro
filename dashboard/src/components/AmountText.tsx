/* AmountText — every money figure in the app. Slab numerals (Zilla Slab) per
   design.md §4.2, digits only (owner directive: amounts show regular numbers,
   no word-form line). Tone maps to money direction:
     in (sale / repaid)  → settled-teal  + ↓/← arrow at the row level
     out (expense/udhar) → ledger-red    + ↑/→ arrow at the row level
     neutral             → ink-black
   Color is never the only signal: rows pair the tone with a direction icon,
   a kind word, and right-alignment. */

import { formatPkr } from '../lib/format';

export type AmountTone = 'in' | 'out' | 'neutral';

export interface AmountTextProps {
  value: number;
  tone?: AmountTone;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const TONE_CLASS: Record<AmountTone, string> = {
  in: 'text-settled-teal',
  out: 'text-ledger-red',
  neutral: 'text-ink-line',
};

const SIZE_CLASS: Record<NonNullable<AmountTextProps['size']>, string> = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-2xl',
  xl: 'text-4xl',
};

export function AmountText({
  value,
  tone = 'neutral',
  size = 'md',
  className = '',
}: AmountTextProps) {
  return (
    <span className={`inline-flex flex-col ${className}`}>
      <span className={`font-numerals font-semibold tabular-nums ${TONE_CLASS[tone]} ${SIZE_CLASS[size]}`}>
        {formatPkr(value)}
      </span>
    </span>
  );
}

/** Kind → tone mapping used by LedgerRow and the report (schema.md §1 kinds). */
export function toneForKind(kind: 'sale' | 'expense' | 'udhar_given' | 'udhar_settlement'): AmountTone {
  return kind === 'sale' || kind === 'udhar_settlement' ? 'in' : 'out';
}
