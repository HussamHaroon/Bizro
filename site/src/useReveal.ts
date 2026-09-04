/* One shared entrance-reveal driver for the homepage.
   Attach the returned ref to a container (we use <main>); every descendant
   carrying `.reveal` fades + rises into place the first time it is seen.

   Motion law (item 2): the hidden start-state and the transition live ONLY
   inside `@media (prefers-reduced-motion: no-preference)` in styles.css — so
   with reduced motion the very same markup is simply always visible and
   static. This hook only ever ADDS the `is-in` class; it never hides anything
   itself, so a JS/IntersectionObserver failure can never strand content.

   Stagger: siblings sharing a parent step by `step` ms (<= 80), capped, so a
   grid of cards cascades instead of popping in unison. Blocks separated
   vertically are not penalised with long delays (index is per-parent).

   `dep` re-runs the observer when it changes — pass a key if the observed
   tree is ever remounted wholesale; nothing on the homepage needs it now
   that the language-switch re-key is gone. */

import { useEffect, useRef } from "react";

export function useReveal<T extends HTMLElement = HTMLElement>(
  dep?: unknown,
  step = 80,
) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;

    const items = Array.from(root.querySelectorAll<HTMLElement>(".reveal"));
    if (!items.length) return;

    const show = (el: HTMLElement) => el.classList.add("is-in");

    /* per-parent stagger index */
    const seen = new Map<Element, number>();
    for (const el of items) {
      const parent = el.parentElement ?? root;
      const i = seen.get(parent) ?? 0;
      seen.set(parent, i + 1);
      el.style.transitionDelay = `${Math.min(i, 5) * step}ms`;
    }

    /* Whatever is already on screen (first paint, or a mid-page reload) is
       shown right away — deterministic, no reliance on the observer firing —
       and only what is genuinely off-screen waits to scroll in. */
    const vh = window.innerHeight;
    const waiting: HTMLElement[] = [];
    for (const el of items) {
      const r = el.getBoundingClientRect();
      if (r.top < vh && r.bottom > 0) show(el);
      else waiting.push(el);
    }

    if (!waiting.length || typeof IntersectionObserver === "undefined") {
      waiting.forEach(show);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            show(entry.target as HTMLElement);
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.01, rootMargin: "0px 0px -8% 0px" },
    );
    waiting.forEach((el) => io.observe(el));

    return () => io.disconnect();
  }, [dep, step]);

  return ref;
}
