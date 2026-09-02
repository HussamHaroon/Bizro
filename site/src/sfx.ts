/* Mithu SFX — Web Audio API only. No audio files, no libraries.

   Law:
     - The AudioContext is created LAZILY, at the first user `pointerdown`
       anywhere (attachSfxUnlock) or at the first play that happens inside a
       gesture — NEVER at module load / import time (autoplay policy).
     - One shared context, reused for the lifetime of the page.
     - Everything is wrapped in try/catch and fails SILENTLY: blocked,
       unsupported or throwing audio never logs, never crashes, never
       produces an unhandled rejection.
     - Mute state persists in localStorage["bizro.sfx"]; absent/invalid
       reads as ON. When muted, nothing plays.
     - Deliberately NOT gated behind prefers-reduced-motion — sound is not
       vestibular motion. Any *visual* motion is gated in styles.css.

   Sound design: sine oscillators only.
     open  -> soft two-note chirp, total 190ms (<= 200ms), peak gain 0.12
     close -> low short pop, 90ms, peak gain 0.10  */

export const SFX_STORAGE_KEY = "bizro.sfx";

/** Read the persisted mute state. Absent / invalid / unreadable => ON. */
export function readSfxPref(): boolean {
  try {
    return window.localStorage.getItem(SFX_STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

/** Persist the mute state ("on" | "off"). Storage failures are ignored. */
export function writeSfxPref(on: boolean): void {
  try {
    window.localStorage.setItem(SFX_STORAGE_KEY, on ? "on" : "off");
  } catch {
    /* private mode / quota — not fatal */
  }
}

let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  try {
    let c = ctx;
    if (!c) {
      const w = window as unknown as {
        AudioContext?: typeof AudioContext;
        webkitAudioContext?: typeof AudioContext;
      };
      const Ctor = w.AudioContext ?? w.webkitAudioContext;
      if (!Ctor) return null;
      c = new Ctor();
      ctx = c;
    }
    if (c.state === "suspended") {
      c.resume().catch(() => {});
    }
    return c;
  } catch {
    ctx = null;
    return null;
  }
}

/**
 * Attach the one-time autoplay unlock: lazily creates/resumes the shared
 * AudioContext on the first `pointerdown` anywhere. Call from a component
 * effect (never at import time). Returns a detach function.
 */
export function attachSfxUnlock(): () => void {
  let detach = () => {};
  try {
    const onFirstGesture = () => {
      getContext();
    };
    window.addEventListener("pointerdown", onFirstGesture, {
      once: true,
      passive: true,
    });
    detach = () => window.removeEventListener("pointerdown", onFirstGesture);
  } catch {
    /* no usable window — stay silent */
  }
  return detach;
}

function tone(
  c: AudioContext,
  freqFrom: number,
  freqTo: number,
  startIn: number,
  dur: number,
  peak: number,
): void {
  const t0 = c.currentTime + startIn;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(freqFrom, t0);
  if (freqTo !== freqFrom) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(1, freqTo), t0 + dur);
  }
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(peak, t0 + 0.012); // fast attack
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur); // full decay by end
  osc.connect(gain);
  gain.connect(c.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

/** Bubble OPEN — soft two-note chirp (A5 -> D6). Total 190ms, peak 0.12. */
export function playChirp(): void {
  if (!readSfxPref()) return;
  try {
    const c = getContext();
    if (!c) return;
    tone(c, 880, 880, 0, 0.085, 0.12);
    tone(c, 1174.7, 1174.7, 0.09, 0.1, 0.12);
  } catch {
    /* blocked or unsupported — fail silently */
  }
}

/** Bubble CLOSE — low, short pop (190Hz down to 85Hz, 90ms, peak 0.10). */
export function playPop(): void {
  if (!readSfxPref()) return;
  try {
    const c = getContext();
    if (!c) return;
    tone(c, 190, 85, 0, 0.09, 0.1);
  } catch {
    /* fail silently */
  }
}
