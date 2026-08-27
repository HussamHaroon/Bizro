/* StreakChip (D3-3) — savings streak in the ledger hero, from GET /api/
   merchants/{id}/streak (schema.md §7.3: consecutive Mon–Sun PKT weeks with net
   cash-flow > 0). Flame icon + bilingual words (icon never alone, §4.7);
   rendered only when streak_weeks ≥ 1 — a 0-week streak is the absence of a
   streak, so the chip stays out of the hero entirely. */

import type { SavingsStreak } from '../types/schema';
import { IconStreak } from './icons';
import { T } from '../i18n';

export interface StreakChipProps {
  streak: SavingsStreak;
  className?: string;
}

export function StreakChip({ streak, className = '' }: StreakChipProps) {
  if (streak.streak_weeks < 1) return null;
  return (
    <span
      className={`bizro-card inline-flex min-h-touch flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2 ${className}`.trim()}
    >
      <IconStreak className="h-7 w-7 shrink-0 text-seal-gold" />
      <span className="font-numerals text-base font-semibold text-ink-black">
        <T
          en={pluralWeeks(streak.streak_weeks)}
          ur={`${streak.streak_weeks} ہفتوں کا سلسلہ`}
        />
      </span>
    </span>
  );
}

function pluralWeeks(n: number): string {
  return n === 1 ? '1 week streak' : `${n} week streak`;
}
