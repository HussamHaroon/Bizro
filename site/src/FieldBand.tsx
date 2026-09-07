/* "In the field" — the gallery band after Trust & audit (section 05).
   A bento grid of six stock photos + two muted stock video loops, framed
   in the house stamped-ledger language (3px ink borders, hard offset
   shadows, canvas caption bars). Copy lives in field-content.ts, beside
   the component, so the pinned COPY tree in content.ts stays untouched.

   Performance/motion law, mirroring LazyScrollMovie:
     - video files are preload="none" with a poster frame — nothing
       streams until the tile is scrolled near
     - playback starts only while the tile is visible AND the visitor
       allows motion; a reduced-motion visitor gets the poster, static
     - photos are lazy + async-decoded */

import { useEffect, useRef } from "react";
import { FIELD_COPY } from "./field-content";

import bazaarLoop from "./assets/stock/field-bazaar-loop.mp4";
import bazaarPoster from "./assets/stock/field-bazaar-loop-poster.jpg";
import writingHands from "./assets/stock/field-writing-hands.mp4";
import writingPoster from "./assets/stock/field-writing-hands-poster.jpg";
import phoneInHand from "./assets/stock/field-phone-in-hand.jpg";
import ledgerNotebook from "./assets/stock/field-ledger-notebook.jpg";
import kiranaShelf from "./assets/stock/field-kirana-shelf.jpg";
import spiceShop from "./assets/stock/field-spice-shop.jpg";
import fruitCart from "./assets/stock/field-fruit-cart.jpg";
import rupeeNote from "./assets/stock/field-rupee-note.jpg";

interface FieldVideoProps {
  src: string;
  poster: string;
  alt: string;
}

/* One muted loop. The IntersectionObserver is the only driver: in view →
   play(), out of view → pause(). play() is user-gesture-free because the
   element is muted, and the catch keeps a paused-background-tab rejection
   from ever surfacing. */
function FieldVideo({ src, poster, alt }: FieldVideoProps) {
  const ref = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") return;
    // motion law: reduced-motion visitors get the poster, never autoplay
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) el.play().catch(() => {});
          else el.pause();
        }
      },
      { threshold: 0.25 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <video
      ref={ref}
      src={src}
      poster={poster}
      muted
      loop
      playsInline
      preload="none"
      aria-label={alt}
    />
  );
}

export default function FieldBand() {
  const c = FIELD_COPY.tiles;

  return (
    <section className="section" id="field" aria-labelledby="field-heading">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="chip chip--teal">{FIELD_COPY.chip}</span>
          <h2 id="field-heading">{FIELD_COPY.h2}</h2>
          <div className="rule" aria-hidden="true" />
          <p className="lede">{FIELD_COPY.lede}</p>
        </div>

        {/* DOM order is the layout: with auto-flow row the feature tile
            takes the 2x2 top-left, the phone tile the tall strip, and the
            six single tiles pack the rest — no dense packing needed. */}
        <div className="field-grid">
          <figure className="field-tile field-tile--feature reveal">
            <FieldVideo
              src={bazaarLoop}
              poster={bazaarPoster}
              alt={c.bazaar.alt}
            />
            <figcaption>{c.bazaar.caption}</figcaption>
          </figure>

          <figure className="field-tile field-tile--tall reveal">
            <img
              src={phoneInHand}
              alt={c.phone.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.phone.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <img
              src={ledgerNotebook}
              alt={c.ledger.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.ledger.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <img
              src={kiranaShelf}
              alt={c.shelf.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.shelf.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <img
              src={spiceShop}
              alt={c.spice.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.spice.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <img
              src={fruitCart}
              alt={c.cart.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.cart.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <img
              src={rupeeNote}
              alt={c.rupee.alt}
              loading="lazy"
              decoding="async"
            />
            <figcaption>{c.rupee.caption}</figcaption>
          </figure>

          <figure className="field-tile reveal">
            <FieldVideo
              src={writingHands}
              poster={writingPoster}
              alt={c.writing.alt}
            />
            <figcaption>{c.writing.caption}</figcaption>
          </figure>
        </div>

        <p className="fine field-note reveal">{FIELD_COPY.honesty}</p>
      </div>
    </section>
  );
}
