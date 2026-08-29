/* ScreenHeader — one per screen (design.md §4.7: purpose graspable in ≤5 words).
   D4-1 restyle: a stamped card — paper-raised surface, 3px ink-line border,
   hard-md shadow — with a 6px seal-gold left accent segment riding inside the
   border, ink-green slab title, Urdu pair alongside, purpose line, actions
   right. */

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
    <header className="bizro-card bizro-card-hover overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4 sm:px-6">
        <div className="flex min-h-touch min-w-touch items-center justify-center text-ink-green">
          {icon ?? null}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-baseline gap-x-3 gap-y-0">
            <T
              en={title}
              ur={titleUr}
              className="font-numerals text-2xl font-bold tracking-wide text-ink-green"
              urClassName="text-2xl font-bold text-ink-green"
            />
          </h1>
          <p className="mt-0.5 text-sm text-ink-line opacity-80">
            {purposeUr ? <T en={purpose} ur={purposeUr} /> : purpose}
          </p>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {/* 6px seal-gold accent segment along the bottom rule (D4-1 header spec) */}
      <span aria-hidden="true" className="block h-[6px] w-24 bg-seal-gold" />
    </header>
  );
}
