/* "In the field" gallery copy — the stock-photo band under Trust & audit
   (section 05). Kept OUTSIDE the COPY tree in content.ts on purpose:
   content.test.ts pins COPY to exactly ten homepage sections, so this band
   carries its copy beside its component, the way MITHU_COPY does.

   Same law as the rest of the site (owner directive 2026-09-04): one
   language, plain English, short sentences, everyday words. And the
   honesty law: the photos are stock, so the band says so — it never
   passes them off as Bizro merchants. */

export interface FieldTileCopy {
  /** Describes the photo/video for screen readers — what is IN the frame. */
  alt: string;
  /** One short line under the tile, in the section-head voice. */
  caption: string;
}

export const FIELD_COPY = {
  chip: "05 · In the field",
  h2: "The counter, the notebook, the phone.",
  lede:
    "Bizro was drawn around shops like these. No new machine — the work happens on the phone already in the owner's pocket.",
  honesty:
    "Illustration only: stock photos and video (Unsplash, Pexels) — not Bizro merchants.",
  tiles: {
    bazaar: {
      alt: "Video loop: shoppers walking past stalls on a busy street market",
      caption: "A market street on a normal day.",
    },
    phone: {
      alt: "A hand holding a phone, screen towards the viewer",
      caption: "The phone the shop already runs on.",
    },
    ledger: {
      alt: "An old open ledger book with handwritten entries",
      caption: "The ledger most shops still keep.",
    },
    shelf: {
      alt: "A small grocery shelf packed full of snack packets",
      caption: "A corner-shop shelf, stocked by hand.",
    },
    spice: {
      alt: "A shopkeeper at a spice and grain shop, goods in sacks",
      caption: "Weighed, packed, and sold by hand.",
    },
    cart: {
      alt: "A fruit seller sitting beside a cart of watermelons",
      caption: "The cart that counts as a business.",
    },
    rupee: {
      alt: "A hand holding a Pakistani banknote",
      caption: "Cash in, cash out — all day.",
    },
    writing: {
      alt: "Video loop: hands writing lines in a notebook by hand",
      caption: "Every evening, the notebook gets written.",
    },
  } satisfies Record<string, FieldTileCopy>,
} as const;

export type FieldCopy = typeof FIELD_COPY;
