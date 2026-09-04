/* Bizro language modes — design.md D1-1(a), owner feedback 2026-08-22:
   "no option to change it to completely Urdu or English — keep mixed as an option too."
   Three modes: `ur` (Urdu-only, Urdu leads), `en` (English-only), `mixed` (the
   historical EN+UR pairs — DEFAULT). Persisted in localStorage; `<html lang>`
   follows the mode. Layout stays LTR in every mode (control-room audience includes
   loan officers); Urdu strings ALWAYS render in their own dir=rtl isolation
   (bizro-ui-design: bidi isolation is not optional), so Urdu text stays correct
   regardless of mode.

   D5-2 (schema.md §8): this provider also owns the numeral-style preference
   (`western` 1-2-3 / `urdu` ۱-۲-۳). localStorage is the FIRST-PAINT fallback;
   once the merchant's saved settings row loads (useSettingsHydration in
   App.tsx) / is saved (SettingsScreen), the server row wins. */

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { NumeralStyle } from '../types/schema';

export type LangMode = 'ur' | 'en' | 'mixed';

export const LANG_STORAGE_KEY = 'bizro.lang-mode';
export const NUMERALS_STORAGE_KEY = 'bizro.numerals';

interface LangState {
  mode: LangMode;
  setMode: (m: LangMode) => void;
  /** Amount-digit style (schema.md §8) — read by formatAmount call sites. */
  numerals: NumeralStyle;
  setNumerals: (n: NumeralStyle) => void;
}

const LangContext = createContext<LangState>({
  mode: 'mixed',
  setMode: () => {},
  numerals: 'western',
  setNumerals: () => {},
});

function readSavedMode(): LangMode {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (saved === 'ur' || saved === 'en' || saved === 'mixed') return saved;
  } catch {
    /* private mode / storage disabled — default below */
  }
  return 'mixed';
}

function readSavedNumerals(): NumeralStyle {
  try {
    const saved = localStorage.getItem(NUMERALS_STORAGE_KEY);
    if (saved === 'western' || saved === 'urdu') return saved;
  } catch {
    /* private mode / storage disabled — default below */
  }
  return 'western';
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<LangMode>(readSavedMode);
  const [numerals, setNumerals] = useState<NumeralStyle>(readSavedNumerals);

  useEffect(() => {
    // <html lang> follows the mode (D1-1). Mixed leads with English, so its
    // document language is en; screen readers switch to Urdu voices inside the
    // lang="ur" runs regardless. dir mirrors the mode: full RTL in Urdu, LTR
    // otherwise (D6-3 — the dashboard previously never mirrored).
    document.documentElement.lang = mode === 'ur' ? 'ur' : 'en';
    document.documentElement.dir = mode === 'ur' ? 'rtl' : 'ltr';
    try {
      localStorage.setItem(LANG_STORAGE_KEY, mode);
    } catch {
      /* persistence is best-effort, never fatal */
    }
  }, [mode]);

  useEffect(() => {
    try {
      localStorage.setItem(NUMERALS_STORAGE_KEY, numerals);
    } catch {
      /* persistence is best-effort, never fatal */
    }
  }, [numerals]);

  const value = useMemo(() => ({ mode, setMode, numerals, setNumerals }), [mode, numerals]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): LangState {
  return useContext(LangContext);
}

/** Numeral-style slice of the preference state (schema.md §8). */
export function useNumerals(): { numerals: NumeralStyle; setNumerals: (n: NumeralStyle) => void } {
  const { numerals, setNumerals } = useLang();
  return { numerals, setNumerals };
}

export interface TApi {
  mode: LangMode;
  /** Plain-string pick for attributes (aria-label, alt, title, error text).
      Mixed keeps both scripts, joined — labels stay honest per active mode. */
  pick: (en: string, ur: string) => string;
  /** §4.7 numerals rule (D1-1 wording): amounts keep the Urdu word form in
      mixed + ur modes; en mode is digits-only. */
  showUrduWords: boolean;
}

export function useT(): TApi {
  const { mode } = useLang();
  return useMemo(
    () => ({
      mode,
      pick: (en: string, ur: string) => (mode === 'ur' ? ur : mode === 'en' ? en : `${en} · ${ur}`),
      showUrduWords: mode !== 'en',
    }),
    [mode],
  );
}

export interface TProps {
  en: string;
  ur: string;
  /** Classes for the English (or mixed outer) span — Latin typography OK here. */
  className?: string;
  /** Classes for the Urdu span when it renders ALONE (ur mode). Latin font
      utilities (font-numerals) must NOT land here; pass size/weight only. */
  urClassName?: string;
}

/** Bilingual label: one script or both per mode.
    en    → English only
    ur    → Urdu only, leading (Urdu hides English, per D1-1)
    mixed → English + Urdu pair, exactly the pre-D1-1 rendering
    Urdu is always dir=rtl-isolated via .bizro-urdu (bizro-ui-design rules). */
export function T({ en, ur, className = '', urClassName = '' }: TProps) {
  const { mode } = useLang();
  if (mode === 'en') return <span className={className}>{en}</span>;
  if (mode === 'ur') return <span className={`bizro-urdu ${urClassName}`.trim()} lang="ur">{ur}</span>;
  return (
    <span className={className}>
      {en}{' '}
      <span className="bizro-urdu font-normal" lang="ur">
        {ur}
      </span>
    </span>
  );
}
