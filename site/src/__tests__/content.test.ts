/* content.test.ts — invariants of the single-language COPY tree in ../content.

   The site is English-only (owner directive 2026-09-04: one language, simple
   words — the ur/mixed modes and the language switcher are gone). These tests
   pin what that law depends on:
     1. the tree exposes ALL ten top-level sections, so no screen loses its copy
     2. the copy is PURE English: zero Arabic-script characters and zero
        roman-Urdu loan words. Only string VALUES are scanned — field names
        like `creditChip` and the server's kind keys (`udhar_given`) are
        identifiers, not copy
     3. the movie has exactly 4 scene captions and Mithu exactly 4 tips
     4. the brand facts survive the plain-wording pass unchanged:
        10.3% / ~33% / 99.9%, PKR figures, Mawakhat, and the Qwen models */

import { describe, it, expect } from "vitest";
import { COPY } from "../content";

/* Arabic script block (covers Urdu/Nastaliq glyphs). */
const ARABIC = /[\u0600-\u06FF]/;
/* Roman-Urdu loan words the copy must never lean on. Proper nouns
   (Bizro/Alkhidmat/Mawakhat/Qwen/PKR/Ahmad) are allowed and simply aren't
   in this list. */
const ROMAN_URDU = /(udhar|karyana)/i;

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

function allStrings(tree: unknown): string[] {
  const out: string[] = [];
  collectStrings(tree, out);
  return out;
}

describe("content — one language, all sections present", () => {
  it("exposes exactly the ten homepage sections", () => {
    expect(Object.keys(COPY).sort()).toEqual(
      [
        "a11y",
        "footer",
        "hero",
        "how",
        "movie",
        "mithu",
        "nav",
        "problem",
        "trust",
        "why",
      ].sort(),
    );
  });

  it("no longer carries any language-mode fields (LANGS / CONTENT are gone)", () => {
    const blob = allStrings(COPY).join("\n");
    expect(blob).not.toMatch(/زبان|اردو/);
    expect(Object.keys(COPY.a11y)).not.toContain("langLabel");
  });
});

describe("content — the copy is pure English", () => {
  it("contains ZERO Arabic-script characters in any value", () => {
    const offenders = allStrings(COPY).filter((s) => ARABIC.test(s));
    expect(
      offenders,
      `copy must have no Arabic script; found in: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });

  it("contains ZERO roman-Urdu loan words (udhar, karyana) in any value", () => {
    const offenders = allStrings(COPY).filter((s) => ROMAN_URDU.test(s));
    expect(
      offenders,
      `copy must have no roman-Urdu loan words; found in: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });
});

describe("content — fixed-size story arrays", () => {
  it("movie.captions has exactly 4 non-empty scenes", () => {
    expect(COPY.movie.captions).toHaveLength(4);
    for (const caption of COPY.movie.captions) {
      expect(caption.trim().length).toBeGreaterThan(0);
    }
  });

  it("mithu.tips has exactly 4 non-empty entries", () => {
    expect(COPY.mithu.tips).toHaveLength(4);
    for (const tip of COPY.mithu.tips) {
      expect(tip.trim().length).toBeGreaterThan(0);
    }
  });
});

describe("content — brand facts survive the plain-wording pass", () => {
  const blob = allStrings(COPY).join("\n");

  it("keeps the national account shares (10.3% / ~33%)", () => {
    expect(blob).toContain("10.3%");
    expect(blob).toContain("~33%");
  });

  it("keeps the Mawakhat figures (~800 branches, PKR 30–75k, 99.9% as claimed)", () => {
    expect(blob).toContain("Mawakhat");
    expect(blob).toContain("~800");
    expect(blob).toContain("PKR 30–75k");
    expect(blob).toContain("99.9%");
    expect(blob).toContain("as claimed by Mawakhat");
  });

  it("keeps the demo invoice facts (Ahmad, PKR 5,000, 96% confidence)", () => {
    expect(blob).toContain("Ahmad");
    expect(blob).toContain("PKR 5,000");
    expect(blob).toContain("96%");
  });

  it("keeps all three Qwen model names", () => {
    expect(blob).toContain("Qwen3.5-Omni-Plus");
    expect(blob).toContain("Qwen-VL-OCR");
    expect(blob).toContain("Qwen3.7-Plus");
  });

  it("still maps every server transaction kind to an English word", () => {
    const kinds = COPY.hero.kindWords;
    expect(kinds.sale).toBe("sale");
    expect(kinds.expense).toBe("expense");
    expect(kinds.udhar_given).toBe("credit given");
    expect(kinds.udhar_settlement).toBe("payment received");
  });
});
