/* WhatsApp Simulator (/simulator) — the zero-credential judge demo: a phone-
   style chat that speaks to the REAL pipeline. A recorded Urdu voice note (or
   a receipt photo) is base64'd into the standard webhook payload + the
   `bizro_sim` media envelope (exactly what server/scripts/simulate_inbound.py
   sends) and POSTed to /webhook/whatsapp, which runs Groq STT → parse → DB
   synchronously. Bizro's stored reply is then read back via
   GET /api/merchants/{id}/outbound (2–3 polls ~1.5s apart) and rendered as an
   incoming bubble with the §7.1 quick-reply chips; tapping a chip POSTs the
   button-reply envelope — the same confirm/correct flow a real WhatsApp
   merchant gets.

   Chat mechanics (WhatsApp idioms, Bizro-stamped): outgoing voice bubbles play
   the recorded blob in-place (play/pause + static waveform + duration) and
   carry delivery ticks — one grey tick when sent, two once Bizro's reply is
   heard on the outbound poll. Incoming bubbles sit left of a small square
   Bizro avatar; a parsed transaction renders as a mini invoice card (kind icon
   + counterparty + amount + StatusPill). While a send is in flight (tens of
   seconds on the free tier) a "Bizro is typing…" bubble with three dots shows
   — word always present, motion inside prefers-reduced-motion: no-preference
   only. The mic is press-and-hold (pointerdown/up) with a click-toggle
   fallback for keyboard/AT (click.detail === 0); releases under 0.6s are
   discarded silently with a small inline hint.

   VISUAL LAW (D4-1 stamped-ledger): this is Bizro's stamped version of a
   WhatsApp chat, NOT a clone — dark-green header bar, cream/teal-tint bubbles
   with 3px ink borders, hard offset shadows (zero blur), radius ≤ 2px, square
   chips, every color from tokens. UI chrome is English-only (owner directive
   2026-09-04); Urdu in the chat BODIES is the pipeline's real output and stays.
   Messages file under the merchant the top-bar picker has selected (their wa_id
   is what the webhook envelope carries), so the Ledger screen reflects the same
   rows. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, PointerEvent as ReactPointerEvent, ReactNode } from 'react';
import { API_BASE_URL, api, mediaUrl } from '../api/client';
import {
  buildButtonEnvelope,
  buildMediaEnvelope,
  buildTextEnvelope,
  bytesToBase64,
  fetchOutbound,
  fileToSimMedia,
  pickRecorderMime,
  postWebhookEnvelope,
} from '../api/simulator';
import type { WaReplyButton } from '../api/simulator';
import { ScreenHeader } from '../components/ScreenHeader';
import { StatusPill } from '../components/StatusPill';
import {
  IconExpense,
  IconMic,
  IconPaperclip,
  IconSale,
  IconSend,
  IconUdharGiven,
  IconUdharSettled,
  IconWhatsApp,
} from '../components/icons';
import { formatPkr } from '../lib/format';
import { useMerchant } from '../merchant';
import type { TransactionKind, TransactionStatus } from '../types/schema';

/* ---- chat model ------------------------------------------------------------ */

type ChatSide = 'in' | 'out' | 'system';

interface ChatMessage {
  id: string;
  side: ChatSide;
  kind: 'text' | 'voice' | 'photo' | 'reply' | 'note' | 'error';
  body: string;
  /** HH:MM stamp rendered at the bubble's foot. */
  timeLabel: string;
  /** §7.1 quick-reply chips riding an incoming confirmation. */
  buttons?: WaReplyButton[];
  /** Set once a chip on this bubble is tapped — locks the pair. */
  answeredPayload?: string;
  /** Voice-note duration label for outgoing voice bubbles ("0:07"). */
  voiceLabel?: string;
  /** Object URL of the outgoing voice blob — powers in-bubble playback. */
  audioUrl?: string;
  /** Outgoing delivery marks: one grey tick = sent, two = Bizro replied. */
  ticks?: 'one' | 'two';
  /** Object URL preview for outgoing receipt photos. */
  imageUrl?: string;
  /** Webhook/outbound transaction id — resolved into a stamped mini-card. */
  txId?: string;
  /** Transient "Bizro is typing" bubble. */
  typing?: boolean;
  /** Stamped invoice image riding this reply (GET /api/media/{media_id}).
      Cleared to hidden when the image fails to load (404) — graceful. */
  mediaId?: string;
  mediaHidden?: boolean;
  /** Object URL of Bizro's spoken reply (POST /api/tts) — "Bizro talks back". */
  ttsUrl?: string;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

let msgSeq = 0;
function nextMsgId(): string {
  msgSeq += 1;
  return `m${Date.now().toString(36)}-${msgSeq}`;
}

function nowLabel(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** mm:ss — the recording timer and the voice-bubble duration label. */
function mmss(totalSeconds: number): string {
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;
}

/** §7.1 quick-reply chips — English labels for the confirm/correct pair (the
    server's Urdu titles stay in the wire payload only). */
function chipLabel(replyId: string): string {
  return replyId === 'confirm' ? "It's correct" : 'Change';
}

/** Releases shorter than this are accidental taps, not voice notes — discarded
    silently (small inline hint only), never sent down the pipeline. */
const MIN_RECORD_MS = 600;

/** Static waveform bar heights (px) — deterministic, seven bars, stamped
    square. Decorative; the duration label carries the information. */
const WAVEFORM_HEIGHTS = [6, 11, 14, 8, 13, 7, 10];

/** Bidi: server replies are Urdu; judge text may be either. Script sniffing
    picks the rendering, per-message (bizro-ui-design: RTL runs must isolate). */
const RTL_RE = /[\u0600-\u06FF\u0750-\u077F\uFD3F-\uFEFF]/;

function MessageBody({ text }: { text: string }) {
  if (!RTL_RE.test(text)) return <span>{text}</span>;
  return (
    <span className="bizro-urdu" lang="ur">
      {text}
    </span>
  );
}

/* ---- chat glyphs -------------------------------------------------------------
   Delivery ticks + play/pause are chat idioms, not ledger icons — thin stroke
   glyphs (WhatsApp's grammar) instead of the filled badge set. Always paired
   with a word: aria-label on the control, sr-only text beside the ticks. */

function GlyphPlay({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false" className={`inline-block shrink-0 ${className}`}>
      <path d="M6.2 4.2v11.6L16 10z" fill="currentColor" />
    </svg>
  );
}

function GlyphPause({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false" className={`inline-block shrink-0 ${className}`}>
      <rect x="5" y="4.2" width="3.4" height="11.6" fill="currentColor" />
      <rect x="11.6" y="4.2" width="3.4" height="11.6" fill="currentColor" />
    </svg>
  );
}

function GlyphTick({ double = false, className = '' }: { double?: boolean; className?: string }) {
  return (
    <svg
      viewBox="0 0 20 12"
      aria-hidden="true"
      focusable="false"
      className={`inline-block ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M1 6.4 4.4 9.8 12.4 1.8" />
      {double && <path d="M7.6 7.4 10.6 10.4 18.6 2.4" />}
    </svg>
  );
}

function GlyphSpeaker({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden="true"
      focusable="false"
      className={`inline-block shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 7.8v4.4h3l4.2 3.5V4.3L6.5 7.8h-3z" fill="currentColor" stroke="none" />
      <path d="M13.4 7.3a3.8 3.8 0 0 1 0 5.4" />
      <path d="M15.6 5.3a6.8 6.8 0 0 1 0 9.4" />
    </svg>
  );
}

function GlyphSpeakerOff({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden="true"
      focusable="false"
      className={`inline-block shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 7.8v4.4h3l4.2 3.5V4.3L6.5 7.8h-3z" fill="currentColor" stroke="none" />
      <path d="M13.2 8.2l4 4" />
      <path d="M17.2 8.2l-4 4" />
    </svg>
  );
}

/* ---- mini invoice card (polled transactions, rendered inside confirmations) - */

const KIND_SPEC: Record<TransactionKind, { icon: typeof IconSale; label: string }> = {
  sale: { icon: IconSale, label: 'Sale' },
  expense: { icon: IconExpense, label: 'Expense' },
  udhar_given: { icon: IconUdharGiven, label: 'Udhar given' },
  udhar_settlement: { icon: IconUdharSettled, label: 'Repaid' },
};

interface TxMini {
  id: string;
  kind: TransactionKind;
  amount_pkr: number;
  status: TransactionStatus;
  /** Counterparty display name from the ledger row (null-safe). */
  counterparty: string | null;
}

function MiniInvoice({ tx }: { tx: TxMini }) {
  const spec = KIND_SPEC[tx.kind] ?? KIND_SPEC.sale;
  const Icon = spec.icon;
  return (
    <div className="mt-2 border-2 border-ink-line bg-paper px-2.5 py-2">
      <p className="flex items-center gap-2">
        <Icon className="h-6 w-6 shrink-0 text-ink-green" />
        <span className="min-w-0 flex-1 truncate text-xs font-bold">
          {tx.counterparty ? <MessageBody text={tx.counterparty} /> : 'Unknown'}
        </span>
      </p>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 border-t-2 border-ink-line pt-1.5">
        <span className="font-numerals text-sm font-bold">{formatPkr(tx.amount_pkr)}</span>
        <span className="text-xs font-semibold">{spec.label}</span>
        <StatusPill status={tx.status} className="ml-auto" />
      </div>
    </div>
  );
}

/* ---- screen ------------------------------------------------------------------ */

export function SimulatorScreen() {
  const { merchants, merchantId } = useMerchant();

  const merchant = merchants.find((m) => m.id === merchantId);
  // The webhook envelope carries THIS wa_id, so entries file under the merchant
  // the top-bar picker selected — the Ledger screen shows the same rows.
  const waId = merchant?.wa_id || '923001234567';
  // _upsert_merchant renames the merchant from contact.profile.name — echo the
  // stored name back so the simulator never overwrites it.
  const contactProfileName = merchant?.display_name || 'Bizro Simulator';

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [recentTxs, setRecentTxs] = useState<TxMini[]>([]);
  /** Which voice bubble is currently playing (play/pause glyph state). */
  const [playingId, setPlayingId] = useState<string | null>(null);
  /** Inline "released too soon" hint under the input bar — no chat noise. */
  const [micHint, setMicHint] = useState(false);
  /** "Bizro talks back" — TTS autoplay toggle, persisted (bizro.tts, ON default). */
  const [ttsOn, setTtsOn] = useState<boolean>(() => {
    try {
      return localStorage.getItem('bizro.tts') !== '0';
    } catch {
      return true;
    }
  });
  /** Which bubble's spoken reply is currently playing. */
  const [ttsPlayingId, setTtsPlayingId] = useState<string | null>(null);

  const seenOutbound = useRef<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordSecondsRef = useRef(0);
  const objectUrlsRef = useRef<string[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  /** performance.now() at record start — sub-second press detection. */
  const recordStartMsRef = useRef(0);
  /** Pointer press in progress (pointerdown seen, pointerup not yet). */
  const pointerDownRef = useRef(false);
  /** A pointer gesture started on the mic — its trailing click is suppressed
      (pointerup already stopped the recording; click-toggle stays keyboard's). */
  const suppressClickRef = useRef(false);
  /** pointerup landed before getUserMedia resolved — stop the instant it does. */
  const pendingStopRef = useRef(false);
  const micHintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timeLabel'> & { timeLabel?: string }) => {
    const full: ChatMessage = { ...msg, id: nextMsgId(), timeLabel: msg.timeLabel ?? nowLabel() };
    setMessages((ms) => [...ms, full]);
    return full.id;
  }, []);

  const removeMessage = useCallback((id: string) => {
    setMessages((ms) => ms.filter((m) => m.id !== id));
  }, []);

  // Keep the chat pinned to the newest bubble.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // One-time teardown: object URLs + recorder/playback timers + live audio.
  // (Revoke-on-send would blank the judge's own preview bubble, so URLs are
  // released on unmount only.)
  useEffect(() => {
    const urls = objectUrlsRef.current;
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
      if (tickRef.current) clearInterval(tickRef.current);
      if (micHintTimerRef.current) clearTimeout(micHintTimerRef.current);
      if (audioRef.current) audioRef.current.pause();
      if (ttsAudioRef.current) ttsAudioRef.current.pause();
    };
  }, []);

  // Absorb everything ALREADY in outbound_messages so old demo runs never
  // flood this session's chat — only rows that arrive from now on render.
  useEffect(() => {
    let alive = true;
    fetchOutbound(merchantId, 20)
      .then((rows) => {
        if (!alive) return;
        for (const row of rows) seenOutbound.current.add(row.id);
      })
      .catch(() => {
        /* server not up yet — the first send's polls will populate the set */
      });
    return () => {
      alive = false;
    };
  }, [merchantId]);

  /* ---- Bizro talks back (TTS) ------------------------------------------------ */

  const stopTts = useCallback(() => {
    ttsAudioRef.current?.pause();
    setTtsPlayingId(null);
  }, []);

  /** Play (or replace) Bizro's spoken reply at volume 0.9. If the browser's
      autoplay policy refuses, the bubble's bar stays for a manual tap. */
  const playTts = useCallback((msgId: string, url: string) => {
    ttsAudioRef.current?.pause();
    const audio = new Audio(url);
    audio.volume = 0.9;
    ttsAudioRef.current = audio;
    audio.addEventListener('ended', () => {
      setTtsPlayingId((cur) => (cur === msgId ? null : cur));
    });
    audio
      .play()
      .then(() => setTtsPlayingId(msgId))
      .catch(() => setTtsPlayingId(null));
  }, []);

  /** Fetch Bizro's spoken reply as soon as the confirmation bubble lands.
      Toggle OFF → nothing is fetched or played at all; any server failure
      (400/502/offline) is silent — audio is skipped, NEVER faked. Under
      prefers-reduced-motion the AUTOplay is skipped; the bubble still gets
      its bar so playback itself remains one tap away. */
  const speakReply = useCallback(
    (msgId: string, text: string) => {
      if (!ttsOn) return;
      void (async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
          });
          if (!res.ok) return;
          const blob = await res.blob();
          if (!blob.size) return;
          const url = URL.createObjectURL(blob);
          objectUrlsRef.current.push(url);
          setMessages((ms) => ms.map((m) => (m.id === msgId ? { ...m, ttsUrl: url } : m)));
          const reduced =
            typeof window.matchMedia === 'function' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          if (!reduced) playTts(msgId, url);
        } catch {
          /* unreachable server / aborted fetch — the text reply stands alone */
        }
      })();
    },
    [playTts, ttsOn],
  );

  const toggleTtsPlayback = useCallback(
    (m: ChatMessage) => {
      if (!m.ttsUrl) return;
      if (ttsPlayingId === m.id) {
        stopTts();
        return;
      }
      playTts(m.id, m.ttsUrl);
    },
    [playTts, stopTts, ttsPlayingId],
  );

  /** Header toggle — persists to localStorage "bizro.tts" (default ON). */
  function toggleTts() {
    const next = !ttsOn;
    setTtsOn(next);
    try {
      localStorage.setItem('bizro.tts', next ? '1' : '0');
    } catch {
      /* storage unavailable — the toggle still holds for this session */
    }
    if (!next) stopTts();
  }

  /* ---- voice playback ------------------------------------------------------- */

  const toggleVoicePlayback = useCallback(
    (msg: ChatMessage) => {
      if (!msg.audioUrl) return;
      stopTts(); // one voice at a time — Bizro's spoken reply yields
      if (playingId === msg.id) {
        audioRef.current?.pause();
        setPlayingId(null);
        return;
      }
      audioRef.current?.pause();
      const audio = new Audio(msg.audioUrl);
      audioRef.current = audio;
      audio.addEventListener('ended', () => {
        setPlayingId((cur) => (cur === msg.id ? null : cur));
      });
      audio
        .play()
        .then(() => setPlayingId(msg.id))
        .catch(() => setPlayingId(null)); // playback refused — stay paused
    },
    [playingId, stopTts],
  );

  /* ---- reply polling --------------------------------------------------------- */

  const pollForReply = useCallback(
    async (attempts = 3): Promise<boolean> => {
      let heard = false;
      for (let i = 0; i < attempts; i += 1) {
        await sleep(1500);
        try {
          const rows = await fetchOutbound(merchantId, 20);
          // API returns newest-first; append oldest→newest so the chat reads chronologically.
          const fresh = rows.filter((r) => !seenOutbound.current.has(r.id)).reverse();
          for (const row of fresh) {
            seenOutbound.current.add(row.id);
            if (!row.body && !row.buttons?.length) continue;
            // The stamped invoice media reference (api.py adds media_id to the
            // outbound wire) — read locally; simulator.ts stays untouched.
            const mediaId = (row as { media_id?: string | null }).media_id ?? undefined;
            const replyMsgId = addMessage({
              side: 'in',
              kind: 'reply',
              body: row.body,
              buttons: row.buttons ?? undefined,
              txId: row.transaction_id ?? undefined,
              mediaId: mediaId ?? undefined,
            });
            // Bizro talks back: the confirmation (the chips state) is spoken.
            if (row.buttons?.length) speakReply(replyMsgId, row.body);
            heard = true;
          }
        } catch {
          /* a failed poll is "try again", not an error surface */
        }
        // Transactions poll: keeps the ledger client honest about what this
        // session wrote and feeds the mini invoice card inside confirmations.
        try {
          const { data } = await api.listTransactions();
          setRecentTxs(
            data.map((t) => ({
              id: t.id,
              kind: t.kind,
              amount_pkr: t.amount_pkr,
              status: t.status,
              counterparty: t.counterparty?.name ?? null,
            })),
          );
        } catch {
          /* ledger refresh is best-effort */
        }
        if (heard) return true;
      }
      if (!heard) {
        addMessage({
          side: 'system',
          kind: 'note',
          body: 'No reply yet — the free AI tier can be slow. Check the Ledger in a moment.',
        });
      }
      return false;
    },
    [addMessage, merchantId, speakReply],
  );

  /* ---- the one send path ------------------------------------------------------- */

  const runEnvelope = useCallback(
    async (envelope: unknown, opts?: { upgradeMsgId?: string }) => {
      setSending(true);
      const typingId = addMessage({ side: 'in', kind: 'note', body: '', typing: true });
      try {
        await postWebhookEnvelope(envelope);
      } catch {
        removeMessage(typingId);
        addMessage({
          side: 'system',
          kind: 'error',
          body: 'Could not reach the Bizro server — is it running on :8000?',
        });
        setSending(false);
        return;
      }
      removeMessage(typingId);
      try {
        const heard = await pollForReply();
        // Bizro's reply arrived → the sender's voice bubble earns its double tick.
        if (heard && opts?.upgradeMsgId) {
          setMessages((ms) =>
            ms.map((m) => (m.id === opts.upgradeMsgId ? { ...m, ticks: 'two' as const } : m)),
          );
        }
      } finally {
        setSending(false);
      }
    },
    [addMessage, pollForReply, removeMessage],
  );

  /* ---- input handlers --------------------------------------------------------- */

  function sendText() {
    const text = input.trim();
    if (!text || sending || recording) return;
    setInput('');
    addMessage({ side: 'out', kind: 'text', body: text });
    void runEnvelope(buildTextEnvelope(waId, contactProfileName, text));
  }

  async function handlePhotoPicked(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-picking the same file
    if (!file || sending) return;
    if (file.size > 5 * 1024 * 1024) {
      addMessage({
        side: 'system',
        kind: 'error',
        body: 'Photo is over 5MB — send a smaller one.',
      });
      return;
    }
    try {
      const { b64, mime } = await fileToSimMedia(file);
      const url = URL.createObjectURL(file);
      objectUrlsRef.current.push(url);
      addMessage({ side: 'out', kind: 'photo', body: file.name, imageUrl: url });
      await runEnvelope(buildMediaEnvelope(waId, contactProfileName, b64, mime));
    } catch {
      addMessage({
        side: 'system',
        kind: 'error',
        body: 'Could not read that file — try another photo.',
      });
    }
  }

  /* ---- voice recording: press-and-hold + click-toggle fallback ----------------- */

  function stopRecordingUi() {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
    setRecording(false);
  }

  /** Inline hint for too-short presses — shows under the input bar for a few
      seconds; the recording itself is discarded without any chat noise. */
  function showMicHint() {
    setMicHint(true);
    if (micHintTimerRef.current) clearTimeout(micHintTimerRef.current);
    micHintTimerRef.current = setTimeout(() => setMicHint(false), 4000);
  }

  /** Finish the current recording — now if the recorder exists, or the moment
      it does (a fast pointerup can beat getUserMedia's permission round-trip).
      The state check makes double-stop (keyboard + pointer race) a no-op. */
  function requestStop() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop(); // onstop finishes the UI + send
    } else if (!recorder) {
      pendingStopRef.current = true;
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      addMessage({
        side: 'system',
        kind: 'error',
        body: 'This browser cannot record audio — use the photo or text options.',
      });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickRecorderMime();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        stopRecordingUi();
        const elapsedMs = performance.now() - recordStartMsRef.current;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        if (blob.size === 0) {
          addMessage({
            side: 'system',
            kind: 'error',
            body: 'Nothing was recorded — hold the mic and speak.',
          });
          return;
        }
        if (elapsedMs < MIN_RECORD_MS) {
          showMicHint(); // accidental tap — discard silently, no chat noise
          return;
        }
        void sendVoiceBlob(blob);
      };
      recordSecondsRef.current = 0;
      setRecordSeconds(0);
      recordStartMsRef.current = performance.now();
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      tickRef.current = setInterval(() => {
        recordSecondsRef.current += 1;
        setRecordSeconds(recordSecondsRef.current);
      }, 1000);
      if (pendingStopRef.current) {
        pendingStopRef.current = false;
        requestStop();
      }
    } catch {
      pendingStopRef.current = false; // a queued stop must not survive a failed start
      addMessage({
        side: 'system',
        kind: 'error',
        body: 'Microphone unavailable — allow mic access in the browser.',
      });
    }
  }

  /** Accessibility fallback: Enter/Space toggles record ↔ stop. */
  async function toggleRecording() {
    if (recording) {
      requestStop();
      return;
    }
    if (sending) return;
    await startRecording();
  }

  function onMicPointerDown(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    if (sending || recording) return;
    suppressClickRef.current = true;
    pointerDownRef.current = true;
    // Capture the pointer so the release fires here even if it happens
    // after the finger/cursor left the button.
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      /* older browsers: pointerup on the button still works */
    }
    void startRecording();
  }

  function onMicPointerEnd() {
    if (!pointerDownRef.current) return;
    pointerDownRef.current = false;
    requestStop(); // release sends automatically
  }

  function onMicClick(event: { detail: number }) {
    // Keyboard activation (detail === 0) → click-toggle. A pointer-generated
    // click was already handled by pointerup — swallow it; a stray pointer
    // click while keyboard-recording still stops.
    if (event.detail === 0) {
      void toggleRecording();
      return;
    }
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    if (recording) requestStop();
  }

  async function sendVoiceBlob(blob: Blob) {
    const seconds = recordSecondsRef.current;
    try {
      const b64 = bytesToBase64(new Uint8Array(await blob.arrayBuffer()));
      const url = URL.createObjectURL(blob);
      objectUrlsRef.current.push(url);
      const voiceMsgId = addMessage({
        side: 'out',
        kind: 'voice',
        body: '',
        voiceLabel: mmss(seconds),
        audioUrl: url,
        ticks: 'one',
      });
      await runEnvelope(buildMediaEnvelope(waId, contactProfileName, b64, blob.type || 'audio/webm'), {
        upgradeMsgId: voiceMsgId,
      });
    } catch {
      addMessage({
        side: 'system',
        kind: 'error',
        body: 'The recording could not be sent — try once more.',
      });
    }
  }

  function pressQuickReply(messageId: string, button: WaReplyButton) {
    if (sending) return;
    const payload = button.reply.id === 'confirm' ? 'confirm' : 'correct';
    const label = chipLabel(button.reply.id);
    // Lock the pair, echo the press as the merchant's own outgoing bubble…
    setMessages((ms) =>
      ms.map((m) => (m.id === messageId ? { ...m, answeredPayload: button.reply.id } : m)),
    );
    addMessage({ side: 'out', kind: 'text', body: label, timeLabel: nowLabel() });
    // …and run the REAL §7.1 button-reply flow through the webhook.
    void runEnvelope(buildButtonEnvelope(waId, contactProfileName, payload));
  }

  /* ---- derived render data ------------------------------------------------ */

  const txById = useMemo(() => new Map(recentTxs.map((t) => [t.id, t])), [recentTxs]);

  /** Shared bubble chrome: left-aligned with the square Bizro avatar, or the
      merchant's own bubbles right-aligned. */
  function bubbleRow(m: ChatMessage, children: ReactNode) {
    const out = m.side === 'out';
    return (
      <div key={m.id} className={`bizro-msg-in flex w-full items-end gap-2 ${out ? 'flex-row-reverse' : ''}`}>
        {!out && (
          <span
            aria-hidden="true"
            className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-ink-line bg-fill-green font-numerals text-sm font-bold text-paper"
          >
            B
          </span>
        )}
        <div
          className={`max-w-[85%] rounded-button border-[3px] border-ink-line px-3.5 py-2.5 text-sm shadow-hard-sm ${
            out ? 'bizro-tint-teal text-teal-ink' : 'bg-paper-raised text-ink-line'
          }`}
        >
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconWhatsApp className="h-9 w-9 text-ink-green" />}
        title="WhatsApp Simulator"
        purpose="Try the real pipeline — no WhatsApp needed"
      />

      <div className="bizro-card bizro-card-hero mx-auto flex w-full max-w-md flex-col overflow-hidden">
        {/* -- WhatsApp-evoking header (Bizro's stamped version) ------------------ */}
        <div className="flex items-center gap-3 border-b-[3px] border-ink-line bg-fill-green px-3 py-2.5 text-paper">
          {/* Avatar: initial-letter square (Mithu SVG lives in site/, out of scope) */}
          <span
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-ink-line bg-paper-raised font-numerals text-xl font-bold text-ink-green"
          >
            B
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-numerals text-base font-bold leading-tight">Bizro</p>
            <p className="flex items-center gap-1.5 text-xs leading-tight opacity-90">
              {recording ? (
                <>
                  <span
                    aria-hidden="true"
                    className="bizro-rec-pulse inline-block h-2 w-2 rounded-full bg-fill-red"
                  />
                  Listening… record your entry
                </>
              ) : (
                'Business account · replies in seconds'
              )}
            </p>
          </div>
          {/* Bizro talks back — speaker toggle (icon+word, §4.7), persists */}
          <button
            type="button"
            onClick={toggleTts}
            aria-pressed={ttsOn}
            aria-label={
              ttsOn
                ? 'Bizro voice replies are on — tap to mute'
                : 'Bizro voice replies are off — tap to unmute'
            }
            title="Bizro speaks confirmations aloud"
            className={`bizro-btn-quiet inline-flex shrink-0 items-center gap-1 rounded-chip border-2 border-ink-line px-2 py-1.5 text-[11px] font-bold ${
              ttsOn ? 'bg-fill-gold text-ink-line' : 'bg-paper-raised text-ink-line opacity-70'
            }`}
          >
            {ttsOn ? <GlyphSpeaker className="h-4 w-4" /> : <GlyphSpeakerOff className="h-4 w-4" />}
            Voice
          </button>
          <span aria-hidden="true" className="bizro-stamp bg-fill-gold text-[10px] text-ink-line">
            SIM
          </span>
        </div>

        {/* -- chat log ----------------------------------------------------------- */}
        <div
          ref={scrollRef}
          role="log"
          aria-live="polite"
          aria-label="Chat with Bizro"
          className="flex h-[min(60dvh,460px)] min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-paper px-3 py-4"
        >
          {/* Date chip — WhatsApp's "Today" divider, stamped */}
          <p className="mx-auto border-2 border-ink-line bg-paper-raised px-3 py-1 text-center text-xs font-semibold">
            Today
          </p>

          <p className="mx-auto max-w-[95%] border-2 border-dashed border-ink-line bg-paper px-3 py-1.5 text-center text-xs text-ink-line opacity-80">
            Press the mic and speak your entry — e.g. “Ahmad ko panch hazar ka udhar diya” — or attach a receipt photo.
          </p>

          {messages.map((m) => {
            if (m.typing) {
              return (
                <div key={m.id} className="bizro-msg-in flex w-full items-end gap-2">
                  <span
                    aria-hidden="true"
                    className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-ink-line bg-fill-green font-numerals text-sm font-bold text-paper"
                  >
                    B
                  </span>
                  <div className="max-w-[85%] rounded-button border-[3px] border-ink-line bg-paper-raised px-3.5 py-2.5 text-sm shadow-hard-sm">
                    <span className="flex items-center gap-2.5">
                      <span aria-hidden="true" className="flex items-center gap-1">
                        <span className="bizro-typing-dot inline-block h-2 w-2 bg-ink-line" />
                        <span className="bizro-typing-dot inline-block h-2 w-2 bg-ink-line" />
                        <span className="bizro-typing-dot inline-block h-2 w-2 bg-ink-line" />
                      </span>
                      Bizro is typing…
                    </span>
                  </div>
                </div>
              );
            }
            if (m.side === 'system') {
              const error = m.kind === 'error';
              return (
                <p
                  key={m.id}
                  role={error ? 'alert' : 'status'}
                  className={`bizro-msg-in mx-auto max-w-[95%] px-3 py-1.5 text-center text-xs ${
                    error
                      ? 'border-[3px] border-ink-line bg-paper font-semibold text-ledger-red'
                      : 'border-2 border-dashed border-ink-line bg-paper text-ink-line opacity-80'
                  }`}
                >
                  <MessageBody text={m.body} />{' '}
                  <span className="whitespace-nowrap font-numerals opacity-60">· {m.timeLabel}</span>
                </p>
              );
            }

            const out = m.side === 'out';
            const ticksLabel =
              m.ticks === 'two' ? 'Sent · Bizro replied' : 'Sent';
            return bubbleRow(m, (
              <>
                {!out && (
                  <p className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-ink-line">Bizro</p>
                )}

                {m.kind === 'voice' && (
                  <div className="mb-1 flex min-w-[190px] items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => toggleVoicePlayback(m)}
                      disabled={!m.audioUrl}
                      aria-label={
                        playingId === m.id ? 'Pause voice note' : 'Play voice note'
                      }
                      aria-pressed={playingId === m.id}
                      className="bizro-btn-quiet inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-chip border-2 border-ink-line bg-paper-raised text-ink-line disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {playingId === m.id ? <GlyphPause className="h-5 w-5" /> : <GlyphPlay className="h-5 w-5" />}
                    </button>
                    <span aria-hidden="true" className="flex items-center gap-[3px]">
                      {WAVEFORM_HEIGHTS.map((h, i) => (
                        <span key={i} className="inline-block w-[3px] bg-current" style={{ height: `${h}px` }} />
                      ))}
                    </span>
                    <span className="ml-auto font-numerals text-xs font-semibold">{m.voiceLabel}</span>
                  </div>
                )}
                {m.kind === 'photo' && (
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold">
                    <IconPaperclip className="h-4 w-4" />
                    <span className="truncate">{m.body}</span>
                  </p>
                )}
                {m.imageUrl ? (
                  <img
                    src={m.imageUrl}
                    alt="Receipt photo you sent"
                    className="mb-1.5 max-h-36 w-full border-2 border-ink-line object-cover"
                  />
                ) : null}
                {m.body && m.kind !== 'voice' ? (
                  <div className="leading-snug">
                    <MessageBody text={m.body} />
                  </div>
                ) : null}

                {/* The real stamped invoice (voice-and-invoice): Bizro sends the
                    picture of the entry below its own text. Hidden gracefully
                    when the media is gone (404 → onError clears it). */}
                {m.mediaId && !m.mediaHidden && (
                  <img
                    src={mediaUrl(m.mediaId)}
                    alt="Bizro’s stamped invoice for this entry"
                    onError={() =>
                      setMessages((ms) =>
                        ms.map((x) => (x.id === m.id ? { ...x, mediaHidden: true } : x)),
                      )
                    }
                    className="mt-2 max-h-72 w-full max-w-[280px] rounded-button border-[3px] border-ink-line bg-paper object-contain shadow-hard-sm"
                  />
                )}

                {/* Tiny audio bar while Bizro's spoken reply exists/plays —
                    doubles as the manual play control (reduced motion skips
                    autoplay; playback itself is fine). */}
                {!out && m.ttsUrl && (
                  <div className="mt-2 flex items-center gap-2 border-t-2 border-ink-line pt-2">
                    <button
                      type="button"
                      onClick={() => toggleTtsPlayback(m)}
                      aria-pressed={ttsPlayingId === m.id}
                      aria-label={
                        ttsPlayingId === m.id
                          ? 'Pause Bizro’s voice reply'
                          : 'Play Bizro’s voice reply'
                      }
                      className="bizro-btn-quiet inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-chip border-2 border-ink-line bg-paper-raised text-ink-line"
                    >
                      {ttsPlayingId === m.id ? (
                        <GlyphPause className="h-4 w-4" />
                      ) : (
                        <GlyphPlay className="h-4 w-4" />
                      )}
                    </button>
                    <span className="text-xs font-semibold">Bizro’s voice reply</span>
                  </div>
                )}

                {/* §7.1 quick-reply chips — the confirm/correct flow */}
                {m.buttons?.length ? (
                  <div className="mt-2 flex flex-wrap gap-2 border-t-2 border-ink-line pt-2">
                    {m.buttons.map((b) => {
                      const answered = m.answeredPayload != null;
                      const active = m.answeredPayload === b.reply.id;
                      return (
                        <button
                          key={b.reply.id}
                          type="button"
                          disabled={answered || sending}
                          onClick={() => pressQuickReply(m.id, b)}
                          aria-pressed={active}
                          className={`bizro-btn-quiet inline-flex min-h-touch items-center justify-center rounded-chip border-2 border-ink-line px-3 text-sm font-semibold ${
                            active
                              ? 'bg-fill-green text-paper'
                              : 'bg-paper text-ink-line hover:bg-paper-raised disabled:opacity-50'
                          }`}
                        >
                          {chipLabel(b.reply.id)}
                        </button>
                      );
                    })}
                  </div>
                ) : null}

                {m.txId && txById.get(m.txId) && <MiniInvoice tx={txById.get(m.txId)!} />}

                <div className="mt-1 flex items-center justify-end gap-1">
                  <span
                    className={`text-[11px] font-numerals ${
                      out ? 'text-teal-ink opacity-75' : 'text-ink-line opacity-60'
                    }`}
                  >
                    {m.timeLabel}
                  </span>
                  {out && m.ticks && (
                    // Grey tick (WhatsApp's delivery-mark color) — single = sent,
                    // double = Bizro's reply heard on the outbound poll.
                    <span className="inline-flex items-center text-ink-line opacity-60" title={ticksLabel}>
                      <GlyphTick double={m.ticks === 'two'} className="h-3 w-4" />
                      <span className="sr-only">{ticksLabel}</span>
                    </span>
                  )}
                </div>
              </>
            ));
          })}
        </div>

        {/* -- input bar ------------------------------------------------------------ */}
        <div className="border-t-[3px] border-ink-line bg-paper-raised px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') sendText();
              }}
              placeholder="Type a message…"
              aria-label="Message Bizro"
              className="min-h-touch min-w-0 flex-1 rounded-button border-[3px] border-ink-line bg-paper px-3 text-sm text-ink-line placeholder:text-ink-line placeholder:opacity-50"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={sending || recording}
              aria-label="Attach a receipt photo"
              className="bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line bg-paper px-2.5 text-xs font-semibold text-ink-line disabled:cursor-not-allowed disabled:opacity-60"
            >
              <IconPaperclip className="h-5 w-5" />
              Photo
            </button>
            <button
              type="button"
              onPointerDown={onMicPointerDown}
              onPointerUp={onMicPointerEnd}
              onPointerCancel={onMicPointerEnd}
              onClick={onMicClick}
              disabled={sending}
              aria-pressed={recording}
              aria-label={
                recording
                  ? 'Stop recording'
                  : 'Record a voice note — hold to record'
              }
              className={`bizro-btn-press inline-flex min-h-touch touch-manipulation select-none items-center gap-1.5 rounded-chip border-[3px] border-ink-line px-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${
                recording ? 'bg-fill-red text-paper' : 'bg-paper text-ink-line'
              }`}
            >
              {recording && (
                <span
                  aria-hidden="true"
                  className="bizro-rec-pulse inline-block h-2 w-2 rounded-full bg-paper"
                />
              )}
              <IconMic className="h-5 w-5" />
              {recording ? (
                <>
                  Stop
                  <span className="font-numerals">{mmss(recordSeconds)}</span>
                </>
              ) : (
                'Mic'
              )}
            </button>
            <button
              type="button"
              onClick={sendText}
              disabled={!input.trim() || sending || recording}
              aria-label="Send message"
              className="bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line bg-fill-green px-3 text-sm font-semibold text-paper disabled:cursor-not-allowed disabled:bg-ink-green-disabled"
            >
              <IconSend className="h-5 w-5" />
              Send
            </button>
          </div>
          {recording ? (
            <p role="status" className="mt-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-ink-line">
              <span aria-hidden="true" className="bizro-rec-pulse inline-block h-2 w-2 rounded-full bg-fill-red" />
              Recording
              <span className="font-numerals">{mmss(recordSeconds)}</span>
              <span aria-hidden="true">·</span>
              release to send
            </p>
          ) : micHint ? (
            <p role="status" className="mt-2 border-2 border-dashed border-ink-line px-2 py-1 text-xs font-semibold text-ink-line">
              Too short — hold the mic while you speak.
            </p>
          ) : (
            <p className="mt-2 text-xs text-ink-line opacity-75">
              Free AI tier — each message uses 1-2 AI requests
            </p>
          )}
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => void handlePhotoPicked(e)}
      />

      <p className="text-center text-xs text-ink-line opacity-75">
        Entries file under the merchant selected in the top bar:{' '}
        <span className="font-semibold">{merchant?.display_name ?? 'first merchant'}</span>
      </p>
    </div>
  );
}
