/* AmountText — every money figure in the app. Slab numerals (Zilla Slab) per
   design.md §4.2. Tone maps to money direction:
     in (sale / repaid)  → settled-teal  + ↓/← arrow at the row level
     out (expense/udhar) → ledger-red    + ↑/→ arrow at the row level
     neutral             → ink-black
   Color is never the only signal: rows pair the tone with a direction icon,
   a kind word, and right-alignment. `showWords` adds the Urdu word form
   (design.md §4.7) — visible in mixed + ur modes, hidden in en mode (D1-1a:
   English-only means digits-only amounts). */

import { formatPkr, urduAmountWords } from '../lib/format';
import { useT } from '../i18n';

export type AmountTone = 'in' | 'out' | 'neutral';

export interface AmountTextProps {
  value: number;
  tone?: AmountTone;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showWords?: boolean;
  className?: string;
}

const TONE_CLASS: Record<AmountTone, string> = {
  in: 'text-settled-teal',
  out: 'text-ledger-red',
  neutral: 'text-ink-black',
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
  showWords = false,
  className = '',
}: AmountTextProps) {
  const { showUrduWords } = useT();
  const wordsVisible = showWords && showUrduWords;
  return (
    <span className={`inline-flex flex-col ${className}`}>
      <span className={`font-numerals font-semibold tabular-nums ${TONE_CLASS[tone]} ${SIZE_CLASS[size]}`}>
        {formatPkr(value)}
      </span>
      {wordsVisible && value > 0 && (
        <span className="bizro-urdu text-xs text-ink-black opacity-80" lang="ur">
          {urduAmountWords(Math.round(value))} روپے
        </span>
      )}
    </span>
  );
}

/** Kind → tone mapping used by LedgerRow and the report (schema.md §1 kinds). */
export function toneForKind(kind: 'sale' | 'expense' | 'udhar_given' | 'udhar_settlement'): AmountTone {
  return kind === 'sale' || kind === 'udhar_settlement' ? 'in' : 'out';
}
