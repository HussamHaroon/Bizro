/* contentKeys.test.ts — the lighter, complementary pass over ../content:
   every leaf string in the single-language COPY tree is a real non-empty
   sentence, and the card/stat arrays keep the sizes the homepage grid
   renders (3 stat cards, 3 steps, 3 differentiators, 3 Mawakhat minis).

   Exception: why.cards[].pPre / pStrong are sentence CONNECTORS around the
   optional <strong> (App renders pPre + strong + pPost); cards without a
   bolded phrase leave them empty on purpose — only pPost must be non-empty. */

import { describe, it, expect } from "vitest";
import { COPY } from "../content";

const CONNECTOR_FIELDS = new Set(["pPre", "pStrong"]);

describe("content keys — every leaf string is non-empty", () => {
  it("no empty or whitespace-only strings anywhere in the tree", () => {
    const offenders: string[] = [];

    function walk(value: unknown, path: string): void {
      if (typeof value === "string") {
        if (value.trim().length === 0) offenders.push(path);
      } else if (Array.isArray(value)) {
        value.forEach((v, i) => walk(v, `${path}[${i}]`));
      } else if (value && typeof value === "object") {
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
          walk(v, path ? `${path}.${k}` : k);
        }
      }
    }

    walk(COPY, "COPY");
    const real = offenders.filter(
      (p) => !CONNECTOR_FIELDS.has(p.split(".").pop() ?? ""),
    );
    expect(
      real,
      `empty copy at: ${JSON.stringify(real)}`,
    ).toEqual([]);
  });

  it("every why card says something (pPost is never empty)", () => {
    for (const card of COPY.why.cards) {
      expect(card.pPost.trim().length).toBeGreaterThan(0);
    }
  });
});

describe("content keys — grid array sizes match the rendered cards", () => {
  it("problem.stats has 3 stat cards", () => {
    expect(COPY.problem.stats).toHaveLength(3);
  });

  it("how.steps has 3 steps", () => {
    expect(COPY.how.steps).toHaveLength(3);
  });

  it("why.cards has 3 differentiator cards", () => {
    expect(COPY.why.cards).toHaveLength(3);
  });

  it("problem.mawakhat.minis has 3 mini stats", () => {
    expect(COPY.problem.mawakhat.minis).toHaveLength(3);
  });

  it("every step carries exactly 2 badges", () => {
    for (const step of COPY.how.steps) {
      expect(step.badges).toHaveLength(2);
    }
  });
});
