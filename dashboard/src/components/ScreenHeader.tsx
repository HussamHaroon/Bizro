/* ScreenHeader — one per screen (design.md §4.7: purpose graspable in ≤5 words).
   Ink-green band, paper-cream text (AA pair per tokens.css), slab-serif title
   (tokens: section headers use Zilla Slab), Urdu label alongside English. */

import type { ReactNode } from 'react';

export interface ScreenHeaderProps {
  title: string;
  /** Urdu rendering of the title (Noto Sans Urdu — dense-UI safe, NOT Nastaliq). */
  titleUr: string;
  /** ≤5 words, plain language. E.g. "This month's money". */
  purpose: string;
  icon?: ReactNode;
  /** Right-aligned controls (month nav, etc.) — each must keep its own 48px target. */
  actions?: ReactNode;
}

export function ScreenHeader({ title, titleUr, purpose, icon, actions }: ScreenHeaderProps) {
  return (
    <header className="bg-ink-green text-paper-cream">
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-5">
        <div className="flex min-w-touch min-h-touch items-center justify-center">
          {icon ?? null}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-baseline gap-x-3 gap-y-0">
            <span className="font-numerals text-2xl font-semibold tracking-wide">{title}</span>
            <span className="bizro-urdu text-lg font-semibold" lang="ur">
              {titleUr}
            </span>
          </h1>
          <p className="mt-0.5 text-sm opacity-90">{purpose}</p>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
