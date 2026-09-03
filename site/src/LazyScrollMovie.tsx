/* Lazy gate for ScrollMovie — the heaviest component on the page (nine inline
   SVG assets + the scroll timeline). It must never delay the hero's first
   paint, so its chunk is dynamic-imported only once the section comes within
   two viewports of the current one; until then (and while the chunk streams)
   an empty runway of identical height holds the layout. */
import { lazy, Suspense, useEffect, useRef, useState } from "react";

const ScrollMovie = lazy(() => import("./ScrollMovie"));

export default function LazyScrollMovie() {
  const [near, setNear] = useState(false);
  const runwayRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (near) return;
    const el = runwayRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setNear(true);
          io.disconnect();
        }
      },
      { rootMargin: "200% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [near]);

  if (!near) {
    return <div className="movie" aria-hidden="true" ref={runwayRef} />;
  }
  return (
    <Suspense fallback={<div className="movie" aria-hidden="true" />}>
      <ScrollMovie />
    </Suspense>
  );
}
