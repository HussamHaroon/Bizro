/* Language segmented control (D1-1a) — اردو / Mixed / English. Sits in the sticky
   top bar. 48px touch targets, icon + word on every segment (design.md §4.7:
   never icon-only — and here never word-only either), aria-pressed state, and
   aria-labels that follow the active mode via pick(). */

import { useLang, useT, type LangMode } from './index';
import { IconLangEn, IconLangMixed, IconLangUr } from '../components/icons';

const OPTIONS: { mode: LangMode; label: string; urdu: boolean; icon: typeof IconLangUr }[] = [
  { mode: 'ur', label: 'اردو', urdu: true, icon: IconLangUr },
  { mode: 'mixed', label: 'Mixed', urdu: false, icon: IconLangMixed },
  { mode: 'en', label: 'English', urdu: false, icon: IconLangEn },
];

export function LanguageControl() {
  const { mode, setMode } = useLang();
  const { pick } = useT();

  return (
    <div
      role="group"
      aria-label={pick('Language', 'زبان')}
      className="flex items-center gap-0.5 rounded-button border border-paper-cream/40 p-0.5"
    >
      {OPTIONS.map(({ mode: m, label, urdu, icon: Icon }) => {
        const active = mode === m;
        return (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            aria-pressed={active}
            className={`bizro-lang-segment inline-flex min-h-touch items-center gap-1.5 rounded-button px-2.5 text-sm font-semibold transition-colors duration-200 ease-out ${
              active
                ? 'bg-paper-cream text-ink-green'
                : 'text-paper-cream hover:bg-ink-green-hover'
            }`}
          >
            <Icon className="h-6 w-6" />
            <span className={urdu ? 'bizro-urdu leading-none' : ''}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}
