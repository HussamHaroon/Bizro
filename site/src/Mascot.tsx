/* Mithu — Bizro's parrot mascot, pure inline SVG.
   Stamped-ledger neobrutalism law (design.md D4-1):
     - token palette only, referenced through CSS vars
     - 3px ink outlines · radius <= 2px · flat fills, no gradients
     - hard offset shadow: the silhouette duplicated in ink, translated,
       zero blur
   Ledger motif: one tiny gold stamp pinned to the wing.
   Moods read through posture and props (head tilt, wings, eyes, badges) —
   never through colour alone. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  attachSfxUnlock,
  playChirp,
  playPop,
  readSfxPref,
  writeSfxPref,
} from "./sfx";

export type MithuMood =
  | "wave"
  | "listening"
  | "thinking"
  | "success"
  | "clarify"
  | "sleep";

interface MithuProps {
  mood?: MithuMood;
  size?: number;
  /** When set, the SVG is exposed as role="img" with this accessible name;
      otherwise it stays decorative (aria-hidden). */
  label?: string;
}

const INK = "var(--ink)";
const FONT_SLAB = '"Zilla Slab", Georgia, serif';

function Eyes({ mood }: { mood: MithuMood }) {
  if (mood === "success") {
    return (
      <g fill="none" stroke={INK} strokeWidth={3.5} strokeLinecap="round">
        <path d="M58 49 q5.5 -8 11 0" />
        <path d="M74 49 q5.5 -8 11 0" />
      </g>
    );
  }
  if (mood === "sleep") {
    return (
      <g fill="none" stroke={INK} strokeWidth={3.5} strokeLinecap="round">
        <path d="M58 47 h11" />
        <path d="M74 47 h11" />
      </g>
    );
  }
  const y = mood === "thinking" ? 37 : 43; // pupils climb when thinking
  return (
    <g fill={INK}>
      <rect x={59} y={y} width={9} height={9} />
      <rect x={75} y={y} width={9} height={9} />
    </g>
  );
}

export function Mithu({ mood = "wave", size = 160, label }: MithuProps) {
  const headTilt =
    mood === "listening"
      ? "rotate(-10 76 72)"
      : mood === "sleep"
        ? "rotate(6 76 72)"
        : undefined;
  const wingT = mood === "wave" ? "rotate(-120 112 86)" : undefined;

  return (
    <svg
      viewBox="0 0 160 160"
      width={size}
      height={size}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ display: "block" }}
    >
      {/* hard offset shadow — the silhouette duplicated in ink, zero blur */}
      <g fill={INK} transform="translate(6 6)">
        <rect x={94} y={128} width={18} height={22} rx={2} />
        <rect x={58} y={134} width={12} height={16} />
        <rect x={86} y={134} width={12} height={16} />
        <rect x={36} y={86} width={16} height={38} rx={2} />
        <rect x={48} y={64} width={64} height={76} rx={2} />
        <g transform={headTilt}>
          <rect x={64} y={6} width={11} height={12} rx={2} />
          <rect x={80} y={2} width={11} height={16} rx={2} />
          <rect x={44} y={16} width={64} height={56} rx={2} />
        </g>
        <g transform={wingT}>
          <rect x={112} y={84} width={20} height={42} rx={2} />
        </g>
      </g>

      {/* tail */}
      <rect
        x={94}
        y={128}
        width={18}
        height={22}
        rx={2}
        fill="var(--green)"
        stroke={INK}
        strokeWidth={3}
      />
      {/* feet */}
      <rect x={58} y={134} width={12} height={16} fill="var(--gold)" stroke={INK} strokeWidth={3} />
      <rect x={86} y={134} width={12} height={16} fill="var(--gold)" stroke={INK} strokeWidth={3} />
      {/* far wing, resting */}
      <rect
        x={36}
        y={86}
        width={16}
        height={38}
        rx={2}
        fill="var(--green)"
        stroke={INK}
        strokeWidth={3}
      />
      {/* body */}
      <rect
        x={48}
        y={64}
        width={64}
        height={76}
        rx={2}
        fill="var(--green)"
        stroke={INK}
        strokeWidth={3}
      />
      {/* gold belly */}
      <rect
        x={58}
        y={84}
        width={34}
        height={44}
        rx={2}
        fill="var(--gold)"
        stroke={INK}
        strokeWidth={3}
      />

      {/* success: the stamp pressed on the chest */}
      {mood === "success" && (
        <g>
          <rect
            x={60}
            y={94}
            width={30}
            height={22}
            rx={2}
            fill="var(--gold)"
            stroke={INK}
            strokeWidth={3}
          />
          <rect
            x={64.5}
            y={98.5}
            width={21}
            height={13}
            fill="none"
            stroke="var(--red)"
            strokeWidth={2}
            strokeDasharray="4 3"
          />
        </g>
      )}

      {/* near wing — carries the ledger motif: a tiny gold stamp */}
      <g transform={wingT}>
        <rect
          x={112}
          y={84}
          width={20}
          height={42}
          rx={2}
          fill="var(--green)"
          stroke={INK}
          strokeWidth={3}
        />
        <rect
          x={115.5}
          y={92}
          width={13}
          height={15}
          fill="var(--gold)"
          stroke={INK}
          strokeWidth={2.5}
        />
        <path
          d="M118.5 99.5 l2.4 2.6 4.6 -5.4"
          fill="none"
          stroke={INK}
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>

      {/* head — tilts as one piece for listening / sleep */}
      <g transform={headTilt}>
        <rect x={64} y={6} width={11} height={12} rx={2} fill="var(--green)" stroke={INK} strokeWidth={3} />
        <rect x={80} y={2} width={11} height={16} rx={2} fill="var(--green)" stroke={INK} strokeWidth={3} />
        <rect
          x={44}
          y={16}
          width={64}
          height={56}
          rx={2}
          fill="var(--green)"
          stroke={INK}
          strokeWidth={3}
        />
        {/* cream face patch */}
        <rect
          x={52}
          y={30}
          width={38}
          height={34}
          rx={2}
          fill="var(--card)"
          stroke={INK}
          strokeWidth={3}
        />
        <Eyes mood={mood} />
        {mood === "clarify" && (
          <rect x={56} y={35} width={15} height={4} fill={INK} transform="rotate(-14 63.5 37)" />
        )}
        {/* red beak */}
        <path
          d="M90 42 H104 L108 51 L104 60 H90 Z"
          fill="var(--red)"
          stroke={INK}
          strokeWidth={3}
          strokeLinejoin="round"
        />
      </g>

      {/* listening: sound waves at the ear */}
      {mood === "listening" && (
        <g fill="none" stroke={INK} strokeWidth={3} strokeLinecap="round">
          <path d="M30 34 q-8 10 0 20" />
          <path d="M21 29 q-12 15 0 30" />
          <path d="M12 24 q-16 20 0 40" />
        </g>
      )}

      {/* thinking: dotted trail up to a bubble holding a question mark */}
      {mood === "thinking" && (
        <g>
          <circle cx={112} cy={40} r={3.5} fill={INK} />
          <circle cx={121} cy={29} r={5} fill={INK} />
          <rect
            x={124}
            y={4}
            width={32}
            height={28}
            rx={2}
            fill="var(--card)"
            stroke={INK}
            strokeWidth={3}
          />
          <text
            x={140}
            y={27}
            textAnchor="middle"
            fontSize={22}
            fontWeight={700}
            fill={INK}
            fontFamily={FONT_SLAB}
          >
            ?
          </text>
        </g>
      )}

      {/* clarify: a blunt question hanging in the air */}
      {mood === "clarify" && (
        <text x={22} y={40} fontSize={30} fontWeight={700} fill={INK} fontFamily={FONT_SLAB}>
          ?
        </text>
      )}

      {/* sleep: the Easter egg — two little z's */}
      {mood === "sleep" && (
        <g fill={INK} fontFamily={FONT_SLAB} fontWeight={700}>
          <text x={122} y={26} fontSize={22}>
            z
          </text>
          <text x={139} y={12} fontSize={15}>
            z
          </text>
        </g>
      )}

      {/* success: confetti squares in the token colours */}
      {mood === "success" && (
        <g stroke={INK} strokeWidth={2}>
          <rect x={26} y={22} width={9} height={9} fill="var(--red)" />
          <rect x={40} y={4} width={9} height={9} fill="var(--teal)" />
          <rect x={112} y={10} width={9} height={9} fill="var(--gold)" />
          <rect x={130} y={26} width={9} height={9} fill="var(--green)" />
        </g>
      )}
    </svg>
  );
}

/* ============================================================
   Interactive guide layer — appended, existing exports above
   are untouched.

   GuideMithu: Mithu + a chat-style speech bubble.
     - opens on hover (mouse) or tap (touch / keyboard), closes on
       mouse-leave, tap outside, or Escape
     - each open shows the NEXT tip, cycling through the list
     - while open, Mithu's mood is always "wave"
     - open chirps, close pops (see ./sfx — Web Audio only, lazy
       context, fails silently, honors the persisted mute state)
     - fully props-driven: no content.ts import. All copy arrives
       via props (see ./mithu-content.ts for the typed strings).     - styling lives in the appended "Mithu guide bubble" block at
       the END of styles.css; every bit of motion there is gated
       behind prefers-reduced-motion: no-preference.

   SfxToggle: chip-style mute toggle (inline-SVG speaker icon +
   word label), aria-pressed, persists to localStorage["bizro.sfx"],
   default ON. Also fully props-driven.
   ============================================================ */

export interface GuideMithuProps {
  /** Rotating guide tips (the four per MITHU_COPY). Each open shows
      the next one, cycling. */
  tips: readonly string[];
  /** Mithu size in px, forwarded to Mithu. Default 150 (hero size). */
  size?: number;
  /** Accessible name for the interactive mascot. It becomes the wrapper's
      aria-label; the inner SVG stays decorative (aria-hidden). */
  label?: string;
  /** aria-label for the bubble itself (MithuGuideCopy.bubbleLabel). */
  bubbleLabel?: string;
  /** Mithu's mood while the bubble is CLOSED. While open he always waves.
      Default "wave". */
  idleMood?: MithuMood;
}

export function GuideMithu({
  tips,
  size = 150,
  label,
  bubbleLabel,
  idleMood = "wave",
}: GuideMithuProps) {
  const count = Math.max(1, tips.length);
  const [open, setOpen] = useState(false);
  const [tip, setTip] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const openRef = useRef(open);
  openRef.current = open;
  const nextTip = useRef(0); // index of the tip the NEXT open will show

  /* Lazy AudioContext unlock — created on the first pointerdown anywhere
     (autoplay policy), never at import time. */
  useEffect(() => attachSfxUnlock(), []);

  const openBubble = useCallback(() => {
    if (!openRef.current) playChirp();
    setTip(nextTip.current);
    nextTip.current = (nextTip.current + 1) % count;
    setOpen(true);
  }, [count]);

  const closeBubble = useCallback(() => {
    if (openRef.current) playPop();
    setOpen(false);
  }, []);

  const toggleBubble = useCallback(() => {
    if (openRef.current) closeBubble();
    else openBubble();
  }, [openBubble, closeBubble]);

  /* tap/click outside closes (the mobile dismiss path) */
  useEffect(() => {
    if (!open) return;
    const onDocPointerDown = (e: PointerEvent) => {
      const root = rootRef.current;
      if (root && !root.contains(e.target as Node)) closeBubble();
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    return () => document.removeEventListener("pointerdown", onDocPointerDown);
  }, [open, closeBubble]);

  const shownTip = tips.length > 0 ? tips[tip % tips.length] : "";

  return (
    <div
      ref={rootRef}
      className={`guide-mithu${open ? " is-open" : ""}`}
      role="button"
      tabIndex={0}
      aria-expanded={open}
      aria-label={label ?? bubbleLabel}
      onPointerEnter={(e) => {
        if (e.pointerType === "mouse") openBubble();
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") closeBubble();
      }}
      onPointerDown={(e) => {
        if (e.pointerType !== "mouse") toggleBubble();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleBubble();
        } else if (e.key === "Escape") {
          closeBubble();
        }
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          closeBubble();
        }
      }}
    >
      <Mithu mood={open ? "wave" : idleMood} size={size} />

      <div className="mithu-bubble" role="group" aria-label={bubbleLabel}>
        <p className="mithu-bubble__tip">{shownTip}</p>
        <div className="mithu-bubble__dots" aria-hidden="true">
          {tips.map((_t, i) => (
            <span
              key={i}
              className={`mithu-bubble__dot${i === tip % count ? " is-active" : ""}`}
            />
          ))}
        </div>
        {/* square tail — an ink-bordered rotated square pointing at Mithu */}
        <span className="mithu-bubble__tail" aria-hidden="true" />
      </div>
    </div>
  );
}

export interface SfxToggleProps {
  /** Word label shown while sound is ON (MithuGuideCopy.sfxOn). */
  labelOn: string;
  /** Word label shown while sound is OFF (MithuGuideCopy.sfxOff). */
  labelOff: string;
  /** Optional extra class(es) for placement. */
  className?: string;
}

/* speaker / muted-speaker icon, drawn in the token style: ink outlines,
   flat card fill, red X when muted. Decorative — the word label carries
   the state, aria-pressed carries it for AT. */
function SpeakerIcon({ on }: { on: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={20}
      height={20}
      aria-hidden="true"
      focusable="false"
      className="sfx-toggle__icon"
    >
      <path
        d="M4 9h4l5-4v14l-5-4H4z"
        fill="var(--card)"
        stroke={INK}
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {on ? (
        <g fill="none" stroke={INK} strokeWidth={2} strokeLinecap="round">
          <path d="M16.5 9.5q2 2.5 0 5" />
          <path d="M19.5 7q3.4 5 0 10" />
        </g>
      ) : (
        <g
          fill="none"
          stroke="var(--red)"
          strokeWidth={2.4}
          strokeLinecap="round"
        >
          <path d="M17 9.5l5 5" />
          <path d="M22 9.5l-5 5" />
        </g>
      )}
    </svg>
  );
}

export function SfxToggle({ labelOn, labelOff, className }: SfxToggleProps) {
  const [on, setOn] = useState<boolean>(readSfxPref);

  const toggle = () => {
    const next = !on;
    writeSfxPref(next); // persist first so the chirp below honors the new state
    setOn(next);
    if (next) playChirp(); // audible confirmation when re-enabled; muting is silent
  };

  return (
    <button
      type="button"
      className={`sfx-toggle${on ? " is-on" : ""}${className ? ` ${className}` : ""}`}
      aria-pressed={on}
      onClick={toggle}
    >
      <SpeakerIcon on={on} />
      <span className="sfx-toggle__label">{on ? labelOn : labelOff}</span>
    </button>
  );
}
