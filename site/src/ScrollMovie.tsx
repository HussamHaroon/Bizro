/* ScrollMovie — "video on scroll" title sequence for the homepage.
   A tall (≈420vh) section with a sticky stage; scroll progress drives a
   4-scene timeline built from hand-drawn SVG assets in the stamped-ledger
   palette (D4-1):

     SCENE 1 SCATTER  — the pieces of a khata drift onto the stage
     SCENE 2 ASSEMBLE — they fly together into a بزرو coin
     SCENE 3 STAMP    — the coin slams down like a rubber trust seal
     SCENE 4 REVEAL   — it settles onto a ledger card; the three pillars rise

   Architecture: the six coin-forming pieces are CHILDREN of the coin group,
   so they scatter from its center and the group's stamp scale / hard
   drop-shadow carries them for free. The three satellites (voice bubble,
   receipt, ledger book) live in the world layer — they orbit the assembled
   coin, then fade as their spirit inheritors (the three pillar chips) rise.

   Engineering law:
   - scroll is NEVER hijacked — we only read scrollY and map it to progress;
     transforms/opacity only, written straight to DOM in one rAF loop
     (no per-frame React renders; state changes only on scene boundaries).
   - prefers-reduced-motion: the timeline ALWAYS runs (it is scroll-scrubbed —
     the user is the playback control), but the vestibular-risky garnish is
     stripped: no slam shake, no REC blink, no caption slide. Owner ruling
     2026-08-30: a frozen film on animation-disabled Windows machines reads
     as broken; scrubbed motion reads as scrolling.
   - every asset is inline SVG (no network, crisp at any DPI) so the owner
     can swap any piece for their own image later without touching the
     timeline.
*/

import { useEffect, useRef, useState } from "react";

/* ---------- tiny easings ---------- */
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeInCubic = (t: number) => t * t * t;
/* back-out overshoot for the stamp slam (slight squash past 1) */
const easeOutBack = (t: number) => {
  const c = 1.70158;
  return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
};

/* scene boundaries in progress p */
const P = { scatterEnd: 0.2, assembleEnd: 0.58, stampEnd: 0.72 };

/* ---------- the 8 assets (hand-drawn, token palette, 3px ink law) ---------- */

const CoinLeftHalf = () => (
  <svg viewBox="0 0 100 200" aria-hidden="true">
    <path
      d="M100 10 A 90 90 0 0 0 100 190 Z"
      fill="var(--gold)"
      stroke="var(--ink)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <path d="M92 30 V 170" stroke="var(--ink)" strokeWidth="3" strokeDasharray="2 10" fill="none" />
  </svg>
);

const CoinRightHalf = () => (
  <svg viewBox="0 0 100 200" aria-hidden="true">
    <path
      d="M0 10 A 90 90 0 0 1 0 190 Z"
      fill="var(--gold)"
      stroke="var(--ink)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <path d="M8 30 V 170" stroke="var(--ink)" strokeWidth="3" strokeDasharray="2 10" fill="none" />
  </svg>
);

const CoinRing = () => (
  <svg viewBox="0 0 200 200" aria-hidden="true">
    <circle
      cx="100"
      cy="100"
      r="94"
      fill="none"
      stroke="var(--ink)"
      strokeWidth="3"
      strokeDasharray="10 8"
    />
  </svg>
);

const StarSeal = () => (
  <svg viewBox="0 0 80 80" aria-hidden="true">
    <path
      d="M40 6 49.6 29.4 74.6 30.8 55.5 46.9 61.5 71.2 40 58 18.5 71.2 24.5 46.9 5.4 30.8 30.4 29.4 Z"
      fill="var(--gold)"
      stroke="var(--ink)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
  </svg>
);

const VoiceBubble = () => (
  <svg viewBox="0 0 120 110" aria-hidden="true">
    <rect x="6" y="6" width="108" height="76" rx="6" fill="var(--teal)" stroke="var(--ink)" strokeWidth="3" />
    <path d="M34 82 L46 100 L54 82 Z" fill="var(--teal)" stroke="var(--ink)" strokeWidth="3" strokeLinejoin="round" />
    <g stroke="#FCF9F0" strokeWidth="5" strokeLinecap="round" fill="none">
      <path d="M38 44 q6 -10 12 0 t12 0 t12 0 t12 0" />
    </g>
  </svg>
);

const Receipt = () => (
  <svg viewBox="0 0 110 130" aria-hidden="true">
    <path
      d="M10 6 H100 V112 L88 122 L76 112 L64 122 L52 112 L40 122 L28 112 L16 122 L10 112 Z"
      fill="var(--card)"
      stroke="var(--ink)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <g stroke="var(--red)" strokeWidth="4" strokeLinecap="round">
      <path d="M24 30 H86" />
      <path d="M24 48 H70" />
      <path d="M24 66 H86" />
    </g>
    <g stroke="var(--ink)" strokeWidth="3" strokeLinecap="round">
      <path d="M24 88 H60" />
    </g>
  </svg>
);

const LedgerBook = () => (
  <svg viewBox="0 0 120 100" aria-hidden="true">
    <rect x="6" y="8" width="108" height="84" rx="3" fill="var(--green)" stroke="var(--ink)" strokeWidth="3" />
    <rect x="18" y="20" width="84" height="12" fill="#FCF9F0" stroke="var(--ink)" strokeWidth="2.5" />
    <g stroke="#FCF9F0" strokeWidth="3.5" strokeLinecap="round">
      <path d="M24 48 H96" />
      <path d="M24 62 H80" />
      <path d="M24 76 H88" />
    </g>
  </svg>
);

const RupeeChip = () => (
  <svg viewBox="0 0 70 70" aria-hidden="true">
    <rect x="5" y="5" width="60" height="60" rx="2" fill="var(--red)" stroke="var(--ink)" strokeWidth="3" />
    <text
      x="35"
      y="49"
      textAnchor="middle"
      fontFamily="var(--font-slab)"
      fontWeight="700"
      fontSize="38"
      fill="#FCF9F0"
    >
      ₹
    </text>
  </svg>
);

/* ---------- piece choreography table ----------
   from = scatter pose (fractions of stage size, relative to coin center)
   to   = assembled pose (fractions of coin diameter C, relative to center)
   core pieces render INSIDE the coin group; satellites in the world layer */

interface PieceDef {
  id: string;
  cls: string;
  from: { x: number; y: number; r: number; s: number };
  to: { x: number; y: number; r: number };
  order: number; // assembly stagger
  satellite?: boolean; // world layer; fades out in the reveal
}

const PIECES: PieceDef[] = [
  { id: "ring", cls: "movie__piece--ring", from: { x: 0.12, y: 0.2, r: -28, s: 0.7 }, to: { x: 0, y: 0, r: 0 }, order: 0 },
  { id: "half-l", cls: "movie__piece--half-l", from: { x: -0.38, y: 0.06, r: -120, s: 0.8 }, to: { x: -0.243, y: 0, r: 0 }, order: 1 },
  { id: "half-r", cls: "movie__piece--half-r", from: { x: 0.36, y: -0.12, r: 140, s: 0.8 }, to: { x: 0.243, y: 0, r: 0 }, order: 2 },
  { id: "word", cls: "movie__piece--word", from: { x: -0.3, y: 0.22, r: 24, s: 0.5 }, to: { x: 0, y: 0, r: 0 }, order: 4 },
  { id: "star", cls: "movie__piece--star", from: { x: 0.34, y: 0.3, r: -40, s: 0.6 }, to: { x: 0.335, y: -0.335, r: 12 }, order: 5 },
  { id: "rupee", cls: "movie__piece--rupee", from: { x: -0.3, y: -0.32, r: 90, s: 0.55 }, to: { x: -0.44, y: 0.38, r: -10 }, order: 3 },
  { id: "voice", cls: "movie__piece--voice", from: { x: 0.42, y: 0.2, r: 18, s: 0.7 }, to: { x: -0.78, y: 0.52, r: -6 }, order: 6, satellite: true },
  { id: "receipt", cls: "movie__piece--receipt", from: { x: -0.42, y: -0.18, r: -14, s: 0.7 }, to: { x: 0.82, y: 0.2, r: 8 }, order: 7, satellite: true },
  { id: "book", cls: "movie__piece--book", from: { x: 0.02, y: -0.4, r: 10, s: 0.7 }, to: { x: 0.08, y: -0.82, r: -4 }, order: 8, satellite: true },
];

/* ---------- captions per scene (bilingual, site voice) ---------- */
const SCENES = [
  {
    ur: "آواز بھیجیں، رسید بھیجیں — بس",
    en: "He sends the voice note. He snaps the receipt. That's the whole job.",
  },
  {
    ur: "بزرو خود جُڑتا ہے",
    en: "No typing. The pieces assemble themselves into a ledger entry.",
  },
  {
    ur: "مہر لگ گئی",
    en: "Every entry is stamped — parsed, priced, and double-checked.",
  },
  {
    ur: "کھاتے سے کریڈٹ ہسٹری تک",
    en: "Months of this become a credit history a lender can actually read.",
  },
];

export default function ScrollMovie() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const worldRef = useRef<HTMLDivElement | null>(null);
  const coinRef = useRef<HTMLDivElement | null>(null);
  const pieceRefs = useRef<(HTMLDivElement | null)[]>([]);
  const impactRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const chipRefs = useRef<(HTMLDivElement | null)[]>([]);
  const barRef = useRef<HTMLDivElement | null>(null);
  const [scene, setScene] = useState(0);

  useEffect(() => {
    const soft = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let raf = 0;
    let active = true;
    let lastScene = -1;

    /* Smooth playback: scrolling sets a TARGET progress; a rAF loop eases the
       rendered progress toward it, so wheel/touch steps glide instead of
       snapping scene to scene. The loop idles once converged and restarts on
       the next scroll — no permanent CPU burn. */
    let targetP = 0;
    let renderP = 0;
    let first = true;
    let loopRunning = false;

    const io = new IntersectionObserver(
      (entries) => {
        active = entries[0]?.isIntersecting ?? true;
        if (active) onScroll();
      },
      { rootMargin: "10% 0px" },
    );

    const apply = (p: number, W: number, H: number) => {
      const C = Math.min(W * 0.56, 300); // coin diameter (mirrors CSS --c)
      const cx = W / 2;
      const cy = H / 2;

      /* --- scene 3: stamp dynamics on the coin group --- */
      const s3 = clamp((p - P.assembleEnd) / (P.stampEnd - P.assembleEnd));
      let coinScale = 1;
      let shadow = 4;
      if (s3 > 0) {
        const wind = clamp(s3 / 0.45); // wind-up 0.58–0.645
        const slam = clamp((s3 - 0.45) / 0.4); // slam 0.645–0.72
        coinScale = 1 + 0.14 * easeInCubic(wind) * (1 - easeOutBack(slam));
        shadow = 4 + 10 * easeInCubic(wind) - 6 * easeOutCubic(slam);
      }

      /* --- scene 4: reveal --- */
      const s4 = clamp((p - P.stampEnd) / (1 - P.stampEnd));
      const lift = easeInOutCubic(clamp(s4 / 0.55));
      const coinY = cy - lift * H * 0.14;
      const coinScaleFinal = coinScale * (1 - lift * 0.34);

      /* whole-world shake at the slam — suppressed for reduced-motion users
         (the one vestibular-risky effect in the film) */
      let shakeX = 0;
      let shakeY = 0;
      if (!soft && s3 > 0.45 && s3 < 0.85) {
        const k = Math.sin((s3 - 0.45) * 26) * (1 - (s3 - 0.45) / 0.4);
        shakeX = 3 * k;
        shakeY = 2 * k;
      }
      if (worldRef.current) {
        worldRef.current.style.transform = `translate(${shakeX}px, ${shakeY}px)`;
      }
      if (coinRef.current) {
        coinRef.current.style.left = `${cx}px`;
        coinRef.current.style.top = `${coinY}px`;
        coinRef.current.style.width = `${C}px`;
        coinRef.current.style.height = `${C}px`;
        coinRef.current.style.transform = `translate(-50%, -50%) scale(${coinScaleFinal}) rotate(${lift * -4}deg)`;
        coinRef.current.style.filter = `drop-shadow(${shadow}px ${shadow}px 0 var(--ink))`;
      }

      /* impact ring */
      if (impactRef.current) {
        const ri = clamp((p - 0.58) / 0.14);
        impactRef.current.style.opacity = ri > 0 ? String(0.9 * (1 - ri)) : "0";
        impactRef.current.style.transform = `translate(-50%, -50%) scale(${0.9 + ri * 0.9})`;
      }

      /* ledger card + pillar chips */
      if (cardRef.current) {
        const c = easeOutCubic(clamp((s4 - 0.1) / 0.5));
        cardRef.current.style.opacity = String(c);
        cardRef.current.style.transform = `translate(-50%, 0) translateY(${(1 - c) * 40}px)`;
      }
      chipRefs.current.forEach((chip, i) => {
        if (!chip) return;
        const c = easeOutCubic(clamp((s4 - 0.3 - i * 0.12) / 0.32));
        chip.style.opacity = String(c);
        chip.style.transform = `translateY(${(1 - c) * 26}px)`;
      });
      if (barRef.current) barRef.current.style.transform = `scaleX(${p})`;

      /* --- pieces: scatter drift → assembly flight --- */
      pieceRefs.current.forEach((el, i) => {
        if (!el) return;
        const d = PIECES[i];
        const a = easeInOutCubic(
          clamp((p - P.scatterEnd - d.order * 0.03) / (P.assembleEnd - P.scatterEnd - 0.08)),
        );
        const drift = 1 - easeOutCubic(clamp(p / P.scatterEnd)); // settle wobble in scene 1
        const ox = d.from.x * W + (d.to.x * C - d.from.x * W) * a;
        const oy = d.from.y * H + (d.to.y * C - d.from.y * H) * a + drift * 8 * Math.sin(i * 2.1);
        const r = d.from.r + (d.to.r - d.from.r) * a + drift * 3 * Math.cos(i * 1.7);
        let s = d.from.s + (1 - d.from.s) * a;
        let op = clamp(p / (P.scatterEnd * 0.7 - (d.order % 3) * 0.03));

        if (d.satellite) {
          /* world layer: base at stage center; parallax drift down as the
             coin lifts; shrink+fade in the reveal */
          const fade = easeInOutCubic(clamp((s4 - 0.15) / 0.45));
          op *= 1 - fade;
          s *= 1 - 0.25 * fade;
          el.style.transform = `translate(${cx + ox}px, ${cy + oy + lift * 40}px) translate(-50%, -50%) rotate(${r}deg) scale(${s})`;
        } else {
          /* core piece: child of the coin group — offsets relative to the
             coin center; the group's scale/shadow carry it */
          el.style.transform = `translate(${ox}px, ${oy}px) translate(-50%, -50%) rotate(${r}deg) scale(${s})`;
        }
        el.style.opacity = String(clamp(op));
      });
    };

    const frame = () => {
      loopRunning = false;
      const sec = sectionRef.current;
      if (!sec || !active) return;
      const diff = targetP - renderP;
      renderP = Math.abs(diff) < 0.0004 ? targetP : renderP + diff * 0.16;
      apply(renderP, sec.clientWidth, window.innerHeight);
      const idx = renderP < P.scatterEnd ? 0 : renderP < P.assembleEnd ? 1 : renderP < P.stampEnd ? 2 : 3;
      if (idx !== lastScene) {
        lastScene = idx;
        setScene(idx);
      }
      if (renderP !== targetP) {
        loopRunning = true;
        raf = requestAnimationFrame(frame);
      }
    };

    const readScroll = () => {
      const sec = sectionRef.current;
      if (!sec) return;
      const rect = sec.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      targetP = clamp(-rect.top / Math.max(total, 1));
      if (first) {
        renderP = targetP; // no swoosh when the page loads mid-section
        first = false;
      }
    };

    const onScroll = () => {
      readScroll();
      if (active && !loopRunning) {
        loopRunning = true;
        raf = requestAnimationFrame(frame);
      }
    };

    io.observe(sectionRef.current!);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    onScroll();
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <section
      className="movie"
      id="movie"
      ref={sectionRef}
      aria-label="Bizro in four scenes — an animated title sequence"
    >
      <div className="movie__stage">
        <div className="movie__world" ref={worldRef}>
          {/* rising ledger backing card (scene 4) */}
          <div className="movie__card" ref={cardRef} aria-hidden="true" />

          {/* satellites — world layer, orbit the assembled coin, fade in scene 4 */}
          {PIECES.map((d, i) =>
            d.satellite ? (
              <div
                key={d.id}
                className={`movie__piece ${d.cls}`}
                ref={(el) => {
                  pieceRefs.current[i] = el;
                }}
                aria-hidden="true"
              >
                {d.id === "voice" && <VoiceBubble />}
                {d.id === "receipt" && <Receipt />}
                {d.id === "book" && <LedgerBook />}
              </div>
            ) : null,
          )}

          {/* coin group — core pieces are its children so the stamp
              scale + hard shadow carry them */}
          <div className="movie__coin" ref={coinRef} aria-hidden="true">
            {PIECES.map((d, i) =>
              d.satellite ? null : (
                <div
                  key={d.id}
                  className={`movie__piece ${d.cls}`}
                  ref={(el) => {
                    pieceRefs.current[i] = el;
                  }}
                >
                  {d.id === "ring" && <CoinRing />}
                  {d.id === "half-l" && <CoinLeftHalf />}
                  {d.id === "half-r" && <CoinRightHalf />}
                  {d.id === "word" && (
                    <span className="movie__word" lang="ur">
                      بزرو
                    </span>
                  )}
                  {d.id === "star" && <StarSeal />}
                  {d.id === "rupee" && <RupeeChip />}
                </div>
              ),
            )}
            <div className="movie__impact" ref={impactRef} />
          </div>
        </div>

        {/* the three pillars, revealed in scene 4 */}
        <div className="movie__chips" aria-hidden="true">
          <div className="movie__chip movie__chip--teal" ref={(el) => { chipRefs.current[0] = el; }}>
            <VoiceBubble /> Voice Khata
          </div>
          <div className="movie__chip movie__chip--red" ref={(el) => { chipRefs.current[1] = el; }}>
            <Receipt /> Vision Audit
          </div>
          <div className="movie__chip movie__chip--green" ref={(el) => { chipRefs.current[2] = el; }}>
            <LedgerBook /> Credit Report
          </div>
        </div>

        {/* scene captions */}
        <div className="movie__caption" aria-live="off">
          <span className="movie__caption-ur" key={`ur${scene}`} lang="ur">
            {SCENES[scene].ur}
          </span>
          <span className="movie__caption-en" key={`en${scene}`}>
            {SCENES[scene].en}
          </span>
        </div>

        {/* film-strip progress */}
        <div className="movie__progress" aria-hidden="true">
          <div className="movie__progress-fill" ref={barRef} />
        </div>

        {/* summary for screen readers (the visuals are decorative) */}
        <p className="sr-only">
          Animated sequence: scattered pieces of a paper ledger — a voice note,
          a receipt, a notebook — fly together and assemble into a golden Bizro
          coin that stamps down like a trust seal, revealing Bizro's three
          tools: Voice Khata, Vision Audit, and the Credit Readiness Report.
        </p>
      </div>
    </section>
  );
}
