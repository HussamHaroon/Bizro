/* Site language provider — the homepage's little sibling of the dashboard's
   per-merchant i18n (schema.md §8). Same triad: ur | en | mixed.
   - persists the choice in localStorage ("bizro.site.lang")
   - flips <html lang> and <html dir> so Urdu mode renders true RTL Nastaliq
   - hands out the copy tree for the active mode via useCopy()

   Owner law (2026-08-30): no duplicated sentences — every visitor reads ONE
   language per mode. "Mixed" is the house voice: English copy with Urdu brand
   accents, never a full translation stacked over the English. */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { CONTENT, LANGS, type Copy, type Lang } from "./content";

const STORAGE_KEY = "bizro.site.lang";

function initialLang(): Lang {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "ur" || saved === "en" || saved === "mixed") return saved;
  return "mixed"; // the showcase voice
}

interface SiteLangCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  copy: Copy;
}

const Ctx = createContext<SiteLangCtx | null>(null);

export function SiteLangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = lang === "ur" ? "ur" : "en";
    root.dir = lang === "ur" ? "rtl" : "ltr";
  }, [lang]);

  const setLang = (l: Lang) => {
    localStorage.setItem(STORAGE_KEY, l);
    setLangState(l);
  };

  return <Ctx.Provider value={{ lang, setLang, copy: CONTENT[lang] }}>{children}</Ctx.Provider>;
}

export function useSiteLang(): SiteLangCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSiteLang outside SiteLangProvider");
  return v;
}

export { LANGS };
export type { Lang };
