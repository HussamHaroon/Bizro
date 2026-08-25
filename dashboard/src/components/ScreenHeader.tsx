/* ScreenHeader — one per screen (design.md §4.7: purpose graspable in ≤5 words).
   D1-1 restyle: the sticky ink-green top bar now carries the brand band, so the
   page header is a raised cream card ("stamped paper") with a seal-gold left
   rule, ink-green slab title, Urdu pair alongside, purpose line, actions right.
   Sits on the shadow-card token per the D1-1 elevation ruling. */

import type { ReactNode } from 'react';
import { T } from '../i18n';

export interface ScreenHeaderProps {
  title: string;
  /** Urdu rendering of the title (Noto Sans Urdu — dense-UI safe, NOT Nastaliq). */
  titleUr: string;
  /** ≤5 words, plain language. E.g. "This month's money". */
  purpose: string;
  purposeUr?: string;
  icon?: ReactNode;
  /** Right-aligned controls (month nav, etc.) — each must keep its own 48px target. */
  actions?: ReactNode;
}

export function ScreenHeader({ title, titleUr, purpose, purposeUr, icon, actions }: ScreenHeaderProps) {
  return (
    <header className="bizro-card border-l-4 border-l-seal-gold">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4 sm:px-6">
        <div className="flex min-h-touch min-w-touch items-center justify-center text-ink-green">
          {icon ?? null}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-baseline gap-x-3 gap-y-0">
            <T
              en={title}
              ur={titleUr}
              className="font-numerals text-2xl font-semibold tracking-wide text-ink-green"
              urClassName="text-2xl font-semibold text-ink-green"
            />
          </h1>
          <p className="mt-0.5 text-sm text-ink-black opacity-80">
            {purposeUr ? <T en={purpose} ur={purposeUr} /> : purpose}
          </p>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
