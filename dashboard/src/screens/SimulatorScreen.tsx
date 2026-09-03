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

   VISUAL LAW (D4-1 stamped-ledger): this is Bizro's stamped version of a
   WhatsApp chat, NOT a clone — dark-green header bar, cream/teal-tint bubbles
   with 3px ink borders, hard offset shadows (zero blur), radius ≤ 2px, square
   chips, every color from tokens. i18n via <T>/pick (en/ur/mixed). Messages
   file under the merchant the top-bar picker has selected (their wa_id is what
   the webhook envelope carries), so the Ledger screen reflects the same rows. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { api } from '../api/client';
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
  IconVoice,
  IconWhatsApp,
} from '../components/icons';
import { T, useNumerals, useT } from '../i18n';
import { formatAmount } from '../lib/format';
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
  /** Object URL preview for outgoing receipt photos. */
  imageUrl?: string;
  /** Webhook/outbound transaction id — resolved into a stamped mini-card. */
  txId?: string;
  /** Transient "Bizro is writing" bubble. */
  typing?: boolean;
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

/* ---- mini ledger card (polled transactions, rendered under confirmations) -- */

const KIND_SPEC: Record<TransactionKind, { icon: typeof IconSale; en: string; ur: string }> = {
  sale: { icon: IconSale, en: 'Sale', ur: 'فروخت' },
  expense: { icon: IconExpense, en: 'Expense', ur: 'خرچ' },
  udhar_given: { icon: IconUdharGiven, en: 'Udhar given', ur: 'ادھار دیا' },
  udhar_settlement: { icon: IconUdharSettled, en: 'Repaid', ur: 'وصولی' },
};

interface TxMini {
  id: string;
  kind: TransactionKind;
  amount_pkd: number;
  status: TransactionStatus;
}

function LedgerChip({ tx }: { tx: TxMini }) {
  const { numerals } = useNumerals();
  const spec = KIND_SPEC[tx.kind] ?? KIND_SPEC.sale;
  const Icon = spec.icon;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 border-t-2 border-ink-line pt-2">
      <Icon className="h-6 w-6 shrink-0 text-ink-green" />
      <span className="font-numerals text-sm font-bold">{formatAmount(tx.amount_pkd, numerals)}</span>
      <span className="text-xs font-semibold">
        <T en={spec.en} ur={spec.ur} />
      </span>
      <StatusPill status={tx.status} className="ml-auto" />
    </div>
  );
}

/* ---- screen ------------------------------------------------------------------ */

export function SimulatorScreen() {
  const { merchants, merchantId } = useMerchant();
  const { pick } = useT();

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

  const seenOutbound = useRef<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordSecondsRef = useRef(0);
  const objectUrlsRef = useRef<string[]>([]);

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

  // Object URLs + recorder timer: release on unmount only (revoke-on-send would
  // blank the judge's own preview bubble).
  useEffect(() => {
    const urls = objectUrlsRef.current;
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
      if (tickRef.current) clearInterval(tickRef.current);
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

  /* ---- reply polling --------------------------------------------------------- */

  const pollForReply = useCallback(
    async (attempts = 3) => {
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
            addMessage({
              side: 'in',
              kind: 'reply',
              body: row.body,
              buttons: row.buttons ?? undefined,
              txId: row.transaction_id ?? undefined,
            });
            heard = true;
          }
        } catch {
          /* a failed poll is "try again", not an error surface */
        }
        // Transactions poll: keeps the ledger client honest about what this
        // session wrote and feeds the stamped mini-card under confirmations.
        try {
          const { data } = await api.listTransactions();
          setRecentTxs(
            data.map((t) => ({
              id: t.id,
              kind: t.kind,
              amount_pkd: t.amount_pkd,
              status: t.status,
            })),
          );
        } catch {
          /* ledger refresh is best-effort */
        }
        if (heard) return;
      }
      if (!heard) {
        addMessage({
          side: 'system',
          kind: 'note',
          body: pick(
            'No reply yet — the free AI tier can be slow. Check the Ledger in a moment.',
            'ابھی جواب نہیں آیا — مفت AI ٹائر آہستہ ہو سکتا ہے۔ کچھ دیر میں کھاتہ دیکھیں۔',
          ),
        });
      }
    },
    [addMessage, merchantId, pick],
  );

  /* ---- the one send path ------------------------------------------------------- */

  const runEnvelope = useCallback(
    async (envelope: unknown) => {
      setSending(true);
      const typingId = addMessage({ side: 'in', kind: 'note', body: '', typing: true });
      try {
        await postWebhookEnvelope(envelope);
      } catch {
        removeMessage(typingId);
        addMessage({
          side: 'system',
          kind: 'error',
          body: pick(
            'Could not reach the Bizro server — is it running on :8000?',
            'بزرو سرور تک رسائی نہیں ہو سکی — کیا یہ :8000 پر چل رہا ہے؟',
          ),
        });
        setSending(false);
        return;
      }
      removeMessage(typingId);
      try {
        await pollForReply();
      } finally {
        setSending(false);
      }
    },
    [addMessage, pick, pollForReply, removeMessage],
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
        body: pick('Photo is over 5MB — send a smaller one.', 'تصویر 5MB سے بڑی ہے — چھوٹی تصویر بھیجیں۔'),
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
        body: pick('Could not read that file — try another photo.', 'وہ فائل پڑھی نہیں جا سکی — دوسری تصویر آزمائیں۔'),
      });
    }
  }

  function stopRecordingUi() {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
    setRecording(false);
  }

  async function sendVoiceBlob(blob: Blob) {
    const seconds = recordSecondsRef.current;
    const label = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    try {
      const b64 = bytesToBase64(new Uint8Array(await blob.arrayBuffer()));
      addMessage({ side: 'out', kind: 'voice', body: '', voiceLabel: label });
      await runEnvelope(
        buildMediaEnvelope(waId, contactProfileName, b64, blob.type || 'audio/webm'),
      );
    } catch {
      addMessage({
        side: 'system',
        kind: 'error',
        body: pick('The recording could not be sent — try once more.', 'ریکارڈنگ بھیجی نہیں جا سکی — دوبارہ کوشش کریں۔'),
      });
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop(); // onstop finishes the UI + send
      return;
    }
    if (sending) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      addMessage({
        side: 'system',
        kind: 'error',
        body: pick(
          'This browser cannot record audio — use the photo or text options.',
          'یہ براؤزر آواز ریکارڈ نہیں کر سکتا — تصویر یا متن استعمال کریں۔',
        ),
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
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        if (blob.size === 0) {
          addMessage({
            side: 'system',
            kind: 'error',
            body: pick('Nothing was recorded — hold the mic and speak.', 'کچھ ریکارڈ نہیں ہوا — مائیک دبا کر بولیں۔'),
          });
          return;
        }
        void sendVoiceBlob(blob);
      };
      recordSecondsRef.current = 0;
      setRecordSeconds(0);
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      tickRef.current = setInterval(() => {
        recordSecondsRef.current += 1;
        setRecordSeconds(recordSecondsRef.current);
      }, 1000);
    } catch {
      addMessage({
        side: 'system',
        kind: 'error',
        body: pick(
          'Microphone unavailable — allow mic access in the browser.',
          'مائیک دستیاب نہیں — براؤزر میں مائیک کی اجازت دیں۔',
        ),
      });
    }
  }

  function pressQuickReply(messageId: string, button: WaReplyButton) {
    if (sending) return;
    const payload = button.reply.id === 'confirm' ? 'confirm' : 'correct';
    // Lock the pair, echo the press as the merchant's own outgoing bubble…
    setMessages((ms) =>
      ms.map((m) => (m.id === messageId ? { ...m, answeredPayload: button.reply.id } : m)),
    );
    addMessage({ side: 'out', kind: 'text', body: button.reply.title, timeLabel: nowLabel() });
    // …and run the REAL §7.1 button-reply flow through the webhook.
    void runEnvelope(buildButtonEnvelope(waId, contactProfileName, payload));
  }

  /* ---- derived render data ------------------------------------------------ */

  const txById = useMemo(() => new Map(recentTxs.map((t) => [t.id, t])), [recentTxs]);
  const voiceMeta = pick('Voice note', 'آواز');

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconWhatsApp className="h-9 w-9 text-ink-green" />}
        title="WhatsApp Simulator"
        titleUr="واٹس ایپ سمیولیٹر"
        purpose="Try the real pipeline — no WhatsApp needed"
        purposeUr="اصل پائپ لائن — واٹس ایپ کے بغیر"
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
                  <T en="Listening… record your entry" ur="سن رہا ہوں… اندراج بتائیں" />
                </>
              ) : (
                <T en="Business account · replies in seconds" ur="کاروبار اکاؤنٹ · جواب چند لمحوں میں" />
              )}
            </p>
          </div>
          <span aria-hidden="true" className="bizro-stamp bg-fill-gold text-[10px] text-ink-line">
            SIM
          </span>
        </div>

        {/* -- chat log ----------------------------------------------------------- */}
        <div
          ref={scrollRef}
          role="log"
          aria-live="polite"
          aria-label={pick('Chat with Bizro', 'بزرو سے گفتگو')}
          className="flex h-[min(60dvh,460px)] min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-paper px-3 py-4"
        >
          <p className="mx-auto max-w-[95%] border-2 border-dashed border-ink-line bg-paper px-3 py-1.5 text-center text-xs text-ink-line opacity-80">
            <T
              en="Press the mic and speak an Urdu entry — e.g. “Ahmad ko panch hazar ka udhar diya” — or attach a receipt photo."
              ur="مائیک دبا کر اردو میں اندراج بتائیں — مثلاً «احمد کو پانچ ہزار کا ادھار دیا» — یا رسید کی تصویر بھیجیں۔"
            />
          </p>

          {messages.map((m) => {
            if (m.typing) {
              return (
                <div
                  key={m.id}
                  className="flex max-w-[85%] items-center gap-2 self-start rounded-button border-[3px] border-ink-line bg-paper-raised px-3.5 py-2.5 text-sm shadow-hard-sm"
                >
                  <span
                    aria-hidden="true"
                    className="bizro-rec-pulse inline-block h-2 w-2 rounded-full bg-fill-red"
                  />
                  <T en="Bizro is writing…" ur="بزرو لکھ رہا ہے…" />
                </div>
              );
            }
            if (m.side === 'system') {
              const error = m.kind === 'error';
              return (
                <p
                  key={m.id}
                  role={error ? 'alert' : 'status'}
                  className={`mx-auto max-w-[95%] px-3 py-1.5 text-center text-xs ${
                    error
                      ? 'border-[3px] border-ink-line bg-paper font-semibold text-ledger-red'
                      : 'border-2 border-dashed border-ink-line bg-paper text-ink-line opacity-80'
                  }`}
                >
                  <MessageBody text={m.body} />
                </p>
              );
            }

            const out = m.side === 'out';
            return (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-button border-[3px] border-ink-line px-3.5 py-2.5 text-sm shadow-hard-sm ${
                  out ? 'bizro-tint-teal self-end text-teal-ink' : 'self-start bg-paper-raised text-ink-line'
                }`}
              >
                {m.kind === 'voice' && (
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold">
                    <IconVoice className="h-5 w-5" />
                    {m.voiceLabel ? `${voiceMeta} · ${m.voiceLabel}` : voiceMeta}
                  </p>
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
                    alt={pick('Receipt photo you sent', 'آپ کی بھیجی ہوئی رسید')}
                    className="mb-1.5 max-h-36 w-full border-2 border-ink-line object-cover"
                  />
                ) : null}
                {m.body ? (
                  <div className="leading-snug">
                    <MessageBody text={m.body} />
                  </div>
                ) : null}

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
                          <T
                            en={b.reply.id === 'confirm' ? "It's correct" : 'Change'}
                            ur={b.reply.title}
                          />
                        </button>
                      );
                    })}
                  </div>
                ) : null}

                {m.txId && txById.get(m.txId) && <LedgerChip tx={txById.get(m.txId)!} />}

                <p
                  className={`mt-1 text-right text-[11px] font-numerals ${
                    out ? 'text-teal-ink opacity-75' : 'text-ink-line opacity-60'
                  }`}
                >
                  {m.timeLabel}
                </p>
              </div>
            );
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
              placeholder={pick('Type a message…', 'پیغام لکھیں…')}
              aria-label={pick('Message Bizro', 'بزرو کو پیغام')}
              className="min-h-touch min-w-0 flex-1 rounded-button border-[3px] border-ink-line bg-paper px-3 text-sm text-ink-line placeholder:text-ink-line placeholder:opacity-50"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={sending || recording}
              aria-label={pick('Attach a receipt photo', 'رسید کی تصویر لگائیں')}
              className="bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line bg-paper px-2.5 text-xs font-semibold text-ink-line disabled:cursor-not-allowed disabled:opacity-60"
            >
              <IconPaperclip className="h-5 w-5" />
              <T en="Photo" ur="تصویر" />
            </button>
            <button
              type="button"
              onClick={() => void toggleRecording()}
              disabled={sending}
              aria-pressed={recording}
              aria-label={
                recording
                  ? pick('Stop recording', 'ریکارڈنگ روکیں')
                  : pick('Record a voice note', 'آواز ریکارڈ کریں')
              }
              className={`bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line px-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${
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
                <span className="font-numerals">
                  <T en={`Stop · 0:${String(recordSeconds).padStart(2, '0')}`} ur={`روکیں · 0:${String(recordSeconds).padStart(2, '0')}`} />
                </span>
              ) : (
                <T en="Mic" ur="مائیک" />
              )}
            </button>
            <button
              type="button"
              onClick={sendText}
              disabled={!input.trim() || sending || recording}
              aria-label={pick('Send message', 'پیغام بھیجیں')}
              className="bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line bg-fill-green px-3 text-sm font-semibold text-paper disabled:cursor-not-allowed disabled:bg-ink-green-disabled"
            >
              <IconSend className="h-5 w-5" />
              <T en="Send" ur="بھیجیں" />
            </button>
          </div>
          <p className="mt-2 text-xs text-ink-line opacity-75">
            <T
              en="Free AI tier — each message uses 1-2 AI requests"
              ur="مفت AI ٹائر — ہر پیغام پر 1-2 AI درخواستیں لگتی ہیں"
            />
          </p>
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
        <T
          en="Entries file under the merchant selected in the top bar:"
          ur="اندراجات اوپر منتخب شدہ تاجر کے کھاتے میں جائیں گے:"
        />{' '}
        <span className="font-semibold">{merchant?.display_name ?? pick('first merchant', 'پہلا تاجر')}</span>
      </p>
    </div>
  );
}
