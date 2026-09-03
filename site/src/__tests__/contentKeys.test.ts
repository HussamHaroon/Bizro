/* contentKeys.test.ts — the lighter, complementary pass over ../content:
   the mithu tips are real non-empty strings, and all three languages expose
   the same top-level sections (a11y / nav / hero / movie / problem / how /
   why / trust / footer / mithu). */

import { describe, it, expect } from "vitest";
import { CONTENT, type Lang } from "../content";

const LANG_IDS: Lang[] = ["en", "mixed", "ur"];

describe("content keys — mithu.tips are non-empty strings", () => {
  for (const lang of LANG_IDS) {
    it(`"${lang}" tips are all non-empty strings`, () => {
      const tips = CONTENT[lang].mithu.tips;
      expect(Array.isArray(tips)).toBe(true);
      for (const tip of tips) {
        expect(typeof tip).toBe("string");
        expect(tip.trim().length).toBeGreaterThan(0);
      }
    });
  }
});

describe("content keys — same top-level sections in every language", () => {
  const reference = Object.keys(CONTENT.en).sort();

  for (const lang of LANG_IDS) {
    it(`"${lang}" exposes the same top-level sections as "en"`, () => {
      expect(Object.keys(CONTENT[lang]).sort()).toEqual(reference);
    });
  }
});
