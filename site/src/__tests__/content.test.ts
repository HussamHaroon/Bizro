/* content.test.ts — invariants of the 3-language copy tree in ../content.

   The owner's law (content.ts header, 2026-08-30): one language per mode, no
   duplicated sentences. These tests pin the structural guarantees that law
   depends on:
     1. en / mixed / ur are structurally identical (deep key-set equality), so
        switching language can never strand a screen on a missing field.
     2. the "en" tree is PURE English copy: zero Arabic-script characters and
        zero roman-Urdu loan words. Only string VALUES are scanned — field
        NAMES like `udharChip` are identifiers, not copy.
     3. "mixed" genuinely differs from "en" (the Urdu brand accents exist).
     4. every mithu.tips array has exactly 4 entries (the rotating bubble). */

import { describe, it, expect } from "vitest";
import { CONTENT, type Copy, type Lang } from "../content";

const LANG_IDS: Lang[] = ["en", "mixed", "ur"];

/* Arabic script block (covers Urdu/Nastaliq glyphs used in the copy). */
const ARABIC = /[\u0600-\u06FF]/;
/* Roman-Urdu loan words the "en" tree must never contain. Proper nouns
   (Bizro/Alkhidmat/Mawakhat/Qwen/PKR/Ahmad) are allowed and simply aren't in
   this list. */
const ROMAN_URDU = /(udhar|karyana)/i;

/* ---- structural walkers (values only, keys used purely as paths) ---- */

function collectPaths(value: unknown, prefix: string, out: string[]): void {
  if (prefix) out.push(prefix);
  if (Array.isArray(value)) {
    value.forEach((v, i) => collectPaths(v, `${prefix}[${i}]`, out));
  } else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      collectPaths(v, prefix ? `${prefix}.${k}` : k, out);
    }
  }
}

function keyPaths(tree: Copy): string[] {
  const out: string[] = [];
  collectPaths(tree, "", out);
  return out.sort();
}

function collectStrings(value: unknown, out: string[]): void {
  if (typeof value === "string") {
    out.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((v) => collectStrings(v, out));
  } else if (value && typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach((v) =>
      collectStrings(v, out),
    );
  }
}

function allStrings(tree: Copy): string[] {
  const out: string[] = [];
  collectStrings(tree, out);
  return out;
}

describe("content — deep key-set equality (en is the reference)", () => {
  const reference = keyPaths(CONTENT.en);

  for (const lang of LANG_IDS) {
    it(`"${lang}" has the identical key structure to "en"`, () => {
      expect(keyPaths(CONTENT[lang])).toEqual(reference);
    });
  }
});

describe('content — the "en" tree is pure English', () => {
  it("contains ZERO Arabic-script characters in any value", () => {
    const offenders = allStrings(CONTENT.en).filter((s) => ARABIC.test(s));
    expect(
      offenders,
      `en copy must have no Arabic script; found in: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });

  it("contains ZERO roman-Urdu loan words (udhar, karyana) in any value", () => {
    const offenders = allStrings(CONTENT.en).filter((s) => ROMAN_URDU.test(s));
    expect(
      offenders,
      `en copy must have no roman-Urdu loan words; found in: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });
});

describe('content — "mixed" carries the Urdu accents', () => {
  it('differs from "en" (the accent strings are actually present)', () => {
    const enBlob = allStrings(CONTENT.en).join("\n");
    const mixedBlob = allStrings(CONTENT.mixed).join("\n");
    expect(mixedBlob).not.toBe(enBlob);
  });

  it("contains at least one Arabic-script accent", () => {
    const hasAccent = allStrings(CONTENT.mixed).some((s) => ARABIC.test(s));
    expect(hasAccent).toBe(true);
  });
});

describe("content — mithu.tips has exactly 4 entries in every language", () => {
  for (const lang of LANG_IDS) {
    it(`"${lang}" mithu.tips length is 4`, () => {
      expect(CONTENT[lang].mithu.tips).toHaveLength(4);
    });
  }
});
