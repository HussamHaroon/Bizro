/* Hero demo — the real pipeline behind the homepage demo-frame.
   Pure helpers only (no React): a MediaRecorder wrapper + the webhook
   envelope/post used by the hero's "try it" mic. The envelope mirrors
   server/scripts/simulate_inbound.py EXACTLY (build_payload): same Meta
   Cloud-API shape, same SIM ids, same namespaced bizro_sim media envelope
   that server/app/webhook.py honors while WhatsApp is in mock mode. The
   audio mime is pinned to "audio/ogg; codecs=opus" for the same reason it
   is there: build_payload classifies audio vs image by that exact string.

   Honesty law (STATUS.md D0-3): this module never invents data. If the
   server's answer is missing a field, the field stays unknown and the UI
   renders what it actually got — including the mock marker on sends. */

/* ---------- narrow, defensive views of the server's wire shapes ---------- */

export interface QuickReplyButton {
  id: string;
  title: string;
}

export interface HeroResult {
  /** "pending" until the one-tap confirm lands, then "confirmed". */
  status: string | null;
  /** The confirmation text Bizro actually sent back (Urdu). */
  confirmation: string | null;
  /** Real parsed fields — null when the read-back couldn't supply them. */
  kind: string | null;
  amountPkr: number | null;
  counterparty: string | null;
  confidence: number | null;
  /** True when the send carried the server's mock marker (no live keys). */
  mock: boolean;
  /** §7.1 quick replies when the response carried them (else empty). */
  buttons: QuickReplyButton[];
}

export interface WebhookOutcome {
  rejected: boolean;
  /** The server's real reply text on the rejection path (reply_ur). */
  reply: string | null;
  result: HeroResult | null;
}

/* --- tiny safe accessors: the server is Python; shapes can drift. --- */

type Row = Record<string, unknown>;

function asRow(v: unknown): Row | null {
  return v !== null && typeof v === "object" ? (v as Row) : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function firstResult(body: Row): Row | null {
  const results = Array.isArray(body.results) ? body.results : [];
  return asRow(results[0]);
}

/* ---------- SIM ids — same namespaces as simulate_inbound.py ---------- */

function hexId(len: number): string {
  const bytes = new Uint8Array(len);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < len; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/* Same defaults as the simulator script (DEFAULT_WA_ID / DEFAULT_NAME):
   the demo speaks for one clearly-labeled simulated merchant. */
export const SIM_WA_ID = "923001234567";
export const SIM_CONTACT_NAME = "Karyana Store (sim)";

const VOICE_MIME = "audio/ogg; codecs=opus";
const DISPLAY_PHONE = "15550001111";
const PHONE_NUMBER_ID = "SIM_PHONE_ID";
const WABA_ID = "SIM_WABA";

function metaMessages(): Row {
  return {
    messaging_product: "whatsapp",
    metadata: {
      display_phone_number: DISPLAY_PHONE,
      phone_number_id: PHONE_NUMBER_ID,
    },
  };
}

function simMessage(extra: Row): Row {
  return {
    from: SIM_WA_ID,
    id: `wamid.SIM${hexId(12)}`,
    timestamp: String(Math.floor(Date.now() / 1000)),
    ...extra,
  };
}

/* ---------- envelopes (mirror build_payload in simulate_inbound.py) ---------- */

/** Voice-note envelope: Meta shape + the namespaced bizro_sim media
    envelope (honored only while WhatsApp is in mock mode). */
export function buildVoiceEnvelope(mediaB64: string): Row {
  return {
    object: "whatsapp_business_account",
    entry: [
      {
        id: WABA_ID,
        changes: [
          {
            field: "messages",
            value: {
              ...metaMessages(),
              contacts: [{ profile: { name: SIM_CONTACT_NAME }, wa_id: SIM_WA_ID }],
              messages: [
                simMessage({
                  type: "audio",
                  audio: { id: `SIM_MEDIA_${hexId(10)}`, mime_type: VOICE_MIME },
                }),
              ],
            },
          },
        ],
      },
    ],
    bizro_sim: { media_b64: mediaB64, mime_type: VOICE_MIME },
  };
}

/** One-tap button-reply envelope (§7.1): msg.type "button" with
    button.payload "confirm" | "correct" — no media envelope. */
export function buildButtonEnvelope(buttonPayload: string, title: string): Row {
  return {
    object: "whatsapp_business_account",
    entry: [
      {
        id: WABA_ID,
        changes: [
          {
            field: "messages",
            value: {
              ...metaMessages(),
              contacts: [{ profile: { name: SIM_CONTACT_NAME }, wa_id: SIM_WA_ID }],
              messages: [
                simMessage({
                  type: "button",
                  button: { payload: buttonPayload, text: title },
                }),
              ],
            },
          },
        ],
      },
    ],
  };
}

/* ---------- webhook post ---------- */

export class WebhookBusyError extends Error {
  constructor(status: number) {
    super(`webhook busy: HTTP ${status}`);
  }
}

export async function postWebhook(payload: Row): Promise<Row> {
  let res: Response;
  try {
    res = await fetch("/webhook/whatsapp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // network down / offline — the caller shows the free-tier-busy line
    throw new WebhookBusyError(0);
  }
  if (res.status === 429 || res.status >= 500) throw new WebhookBusyError(res.status);
  if (!res.ok) throw new WebhookBusyError(res.status);
  const body = asRow(await res.json());
  if (!body) throw new WebhookBusyError(res.status);
  return body;
}

/* ---------- outcome parsing (never invents; nulls stay null) ---------- */

function buttonsFrom(sent: Row | null): QuickReplyButton[] {
  const raw = sent && Array.isArray(sent.buttons) ? sent.buttons : [];
  const out: QuickReplyButton[] = [];
  for (const b of raw) {
    const row = asRow(b);
    const reply = row ? asRow(row.reply) : null;
    const id = reply ? str(reply.id) : null;
    const title = reply ? str(reply.title) : null;
    if (id && title) out.push({ id, title });
  }
  return out;
}

/** The parsed wire row, read back through the same REST endpoint the
    simulator script uses (GET /api/merchants/{id}/transactions). Returns
    null on any failure — the UI then renders without the parsed fields
    rather than guessing. */
async function fetchParsedRow(
  merchantId: string,
  transactionId: string,
): Promise<Partial<HeroResult> | null> {
  try {
    const res = await fetch(
      `/api/merchants/${encodeURIComponent(merchantId)}/transactions`,
    );
    if (!res.ok) return null;
    const body = asRow(await res.json());
    const rows = body && Array.isArray(body.transactions) ? body.transactions : [];
    for (const r of rows) {
      const row = asRow(r);
      if (!row || row.id !== transactionId) continue;
      const counterparty = asRow(row.counterparty);
      const source = asRow(row.source);
      return {
        kind: str(row.kind),
        amountPkr: num(row.amount_pkr),
        counterparty: counterparty ? str(counterparty.name) : null,
        confidence: source ? num(source.confidence) : null,
      };
    }
    return null;
  } catch {
    return null;
  }
}

/** Interpret one voice-note POST response. Throws WebhookBusyError only for
    transport problems; a handled rejection is a real outcome, not an error. */
export async function interpretVoiceResponse(body: Row): Promise<WebhookOutcome> {
  const r = firstResult(body);
  if (!r) throw new WebhookBusyError(200);

  // §6.9 rejection: the pipeline handled the note but persisted nothing —
  // the server's reply text is the honest thing to show.
  if (r.rejected === true) {
    return { rejected: true, reply: str(r.reply_ur), result: null };
  }
  if (r.ok === false) throw new WebhookBusyError(200);

  const transactionId = str(r.transaction_id);
  const merchantId = str(r.merchant_id);
  const sent = asRow(r.sent);

  const parsed =
    transactionId && merchantId
      ? await fetchParsedRow(merchantId, transactionId)
      : null;

  return {
    rejected: false,
    reply: null,
    result: {
      status: str(r.status),
      confirmation: str(r.confirmation_ur),
      kind: parsed?.kind ?? null,
      amountPkr: parsed?.amountPkr ?? null,
      counterparty: parsed?.counterparty ?? null,
      confidence: parsed?.confidence ?? null,
      mock: sent?.mock === true,
      buttons: buttonsFrom(sent),
    },
  };
}

/** Interpret a one-tap button-reply POST response (§7.1). */
export function interpretButtonResponse(body: Row): {
  action: string | null;
  status: string | null;
  reply: string | null;
} {
  const r = firstResult(body);
  if (!r) return { action: null, status: null, reply: null };
  const tx = asRow(r.transaction);
  return {
    action: str(r.action),
    status: tx ? str(tx.status) : null,
    reply: str(r.reply),
  };
}

/* ---------- recorder wrapper (browser MediaRecorder) ---------- */

export function recorderSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function"
  );
}

/** Pick the first mime type this browser can actually record. */
function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return undefined;
  }
  const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t));
}

export class VoiceRecorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickMime();
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data && e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.start();
  }

  /** Stop and hand back the recording. Resolves null when never started. */
  stop(): Promise<Blob | null> {
    const recorder = this.recorder;
    if (!recorder || recorder.state === "inactive") return Promise.resolve(null);
    return new Promise((resolve) => {
      recorder.onstop = () => {
        for (const t of this.stream ? this.stream.getTracks() : []) t.stop();
        const type = recorder.mimeType || "audio/webm";
        resolve(new Blob(this.chunks, { type }));
      };
      recorder.stop();
    });
  }

  /** Best-effort teardown (permission lost, component unmounted mid-take). */
  dispose(): void {
    try {
      if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
    } catch {
      /* already inert */
    }
    for (const t of this.stream ? this.stream.getTracks() : []) t.stop();
    this.recorder = null;
    this.stream = null;
  }
}

/* ---------- bytes -> base64 (FileReader; no diacritic-safe btoa needed) ---------- */

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const s = String(reader.result);
      const comma = s.indexOf(",");
      resolve(comma >= 0 ? s.slice(comma + 1) : "");
    };
    reader.onerror = () => reject(new Error("could not read recording"));
    reader.readAsDataURL(blob);
  });
}

/* ---------- presentation helpers ---------- */

/** PKR amount for the invoice line. The site has no numerals helper, so
    this is the one place amounts get formatted — grouping only, no
    invented decimals. */
export function formatAmountPkr(amountPkr: number): string {
  return `PKR ${amountPkr.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

/** mm:ss for the recording timer. */
export function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
