/* English-only text helpers (owner directive 2026-09-04: "make it in english,
   remove the other modes for urdu and mixed, keep everything in english").

   The old three-mode i18n (ur / en / mixed) is gone. <T> and pick() keep their
   historical prop shapes (en required, ur accepted) only so remaining call
   sites still typecheck — the Urdu string is never rendered anywhere. Plain
   strings are preferred at new call sites: <T en="Save"> === "Save". */

import type { ReactNode } from 'react';

export interface TApi {
  /** Always 'en' — kept so existing destructuring call sites compile. */
  mode: 'en';
  /** Returns the English string; the second argument is accepted and ignored. */
  pick: (en: string, ur?: string) => string;
}

export function useT(): TApi {
  return {
    mode: 'en',
    pick: (en) => en,
  };
}

export interface TProps {
  en: ReactNode;
  /** Accepted for call-site compatibility — never rendered. */
  ur?: ReactNode;
  className?: string;
}

/** English-only label: renders {en} inside a plain span. */
export function T({ en, className = '' }: TProps) {
  return <span className={className}>{en}</span>;
}
