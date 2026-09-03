/* sfx.test.ts — the Web Audio SFX layer in ../sfx.

   The law being pinned here (sfx.ts header):
     - mute state round-trips through localStorage["bizro.sfx"]; absent => ON.
     - everything fails SILENTLY: an unavailable or throwing AudioContext must
       never make play{Click,Chirp,Pop} throw.
     - when muted, NOTHING plays — the AudioContext is never even constructed.

   The module caches its AudioContext in a module-level `let ctx`, so each test
   runs against a FRESH module instance via vi.resetModules() + dynamic import.
   That keeps the "never constructed while muted" assertion honest (ctx starts
   null every time, so a construction would be observable). */

import { describe, it, expect, beforeEach, vi } from "vitest";

type SfxModule = typeof import("../sfx");

/* window shape we mutate: both ctor aliases the source probes for. Optional so
   `delete` is legal under strict mode. */
type AudioWindow = { AudioContext?: unknown; webkitAudioContext?: unknown };
const w = window as unknown as AudioWindow;

/* A minimal but fully-wired AudioContext stand-in: everything getContext() and
   tone() touch is present and inert. */
function ctxShape() {
  const param = { setValueAtTime: () => {}, exponentialRampToValueAtTime: () => {} };
  return {
    state: "running",
    currentTime: 0,
    destination: {},
    resume: () => Promise.resolve(),
    createOscillator: () => ({
      type: "sine",
      frequency: param,
      connect: () => {},
      start: () => {},
      stop: () => {},
    }),
    createGain: () => ({ gain: param, connect: () => {} }),
  };
}

/* Install a constructor spy that yields a working mock context; returns the spy
   so tests can assert on construction count. */
function installMockAudioContext() {
  const ctor = vi.fn(function (this: Record<string, unknown>) {
    Object.assign(this, ctxShape());
  });
  w.AudioContext = ctor;
  return ctor;
}

/* Install a fresh, empty in-memory Storage double on window.localStorage. The
   product code reads/writes window.localStorage, so this is exactly the surface
   under test. If the host property can't be redefined, fall back to jsdom's own
   (now same-origin, working) storage and just clear it. */
function installMockStorage(): void {
  const store = new Map<string, string>();
  const mock = {
    get length() {
      return store.size;
    },
    clear: () => {
      store.clear();
    },
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (k: string) => {
      store.delete(k);
    },
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
  };
  try {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      writable: true,
      value: mock,
    });
  } catch {
    window.localStorage.clear();
  }
}

beforeEach(() => {
  vi.resetModules();
  installMockStorage();
  delete w.AudioContext;
  delete w.webkitAudioContext;
});

describe("sfx — preference round-trip", () => {
  it("reads ON when nothing is stored", async () => {
    const sfx: SfxModule = await import("../sfx");
    expect(window.localStorage.getItem(sfx.SFX_STORAGE_KEY)).toBeNull();
    expect(sfx.readSfxPref()).toBe(true);
  });

  it("writeSfxPref persists and readSfxPref round-trips both states", async () => {
    const sfx: SfxModule = await import("../sfx");

    sfx.writeSfxPref(false);
    expect(window.localStorage.getItem(sfx.SFX_STORAGE_KEY)).toBe("off");
    expect(sfx.readSfxPref()).toBe(false);

    sfx.writeSfxPref(true);
    expect(window.localStorage.getItem(sfx.SFX_STORAGE_KEY)).toBe("on");
    expect(sfx.readSfxPref()).toBe(true);
  });
});

describe("sfx — silent-failure law", () => {
  it("play{Click,Chirp,Pop} do not throw when AudioContext is unavailable", async () => {
    const sfx: SfxModule = await import("../sfx");
    // jsdom ships no Web Audio; be explicit that neither alias exists.
    expect(w.AudioContext).toBeUndefined();
    expect(w.webkitAudioContext).toBeUndefined();
    sfx.writeSfxPref(true); // unmuted, so each play actually attempts audio

    expect(() => sfx.playClick()).not.toThrow();
    expect(() => sfx.playChirp()).not.toThrow();
    expect(() => sfx.playPop()).not.toThrow();
  });

  it("play{Click,Chirp,Pop} swallow errors from a throwing AudioContext", async () => {
    const sfx: SfxModule = await import("../sfx");
    // Context constructs fine, but the first node factory throws (blocked audio).
    w.AudioContext = vi.fn(function (this: Record<string, unknown>) {
      Object.assign(this, ctxShape(), {
        createOscillator(): never {
          throw new Error("audio blocked by policy");
        },
      });
    });
    sfx.writeSfxPref(true);

    expect(() => sfx.playClick()).not.toThrow();
    expect(() => sfx.playChirp()).not.toThrow();
    expect(() => sfx.playPop()).not.toThrow();
  });
});

describe("sfx — mute means no audio is even constructed", () => {
  it("positive control: while ON, a play constructs the AudioContext once", async () => {
    const sfx: SfxModule = await import("../sfx");
    const ctor = installMockAudioContext();
    sfx.writeSfxPref(true);

    sfx.playChirp();
    expect(ctor).toHaveBeenCalledTimes(1);
  });

  it('while OFF (bizro.sfx="off"), no play constructs the AudioContext', async () => {
    const sfx: SfxModule = await import("../sfx");
    const ctor = installMockAudioContext();
    sfx.writeSfxPref(false); // muted

    sfx.playClick();
    sfx.playChirp();
    sfx.playPop();

    expect(ctor).not.toHaveBeenCalled();
  });
});
