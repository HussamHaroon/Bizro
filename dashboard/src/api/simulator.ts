/* WhatsApp simulator API — the /simulator screen's direct line to the REAL
   pipeline with zero Meta credentials.

   POST /webhook/whatsapp: the same endpoint the Meta Cloud API calls, fed the
   standard inbound payload shape plus the clearly-namespaced `bizro_sim`
   envelope (media bytes base64) that server/app/webhook.py honors while
   WhatsApp is in mock mode. This is exactly what
   server/scripts/simulate_inbound.py sends — the browser is just another
   simulator client. The webhook runs the full pipeline synchronously (STT →
   parse → Neon/Postgres persist → outbound reply), so one POST can take tens
   of seconds on the free AI tier; the caller shows a typing state meanwhile.

   GET /api/merchants/{id}/outbound: the merchant's outbound_messages rows,
   newest-first — the read side that turns Bizro's stored replies into chat
   bubbles (body + §7.1 quick-reply buttons from payload.buttons). */

import { API_BASE_URL } from './client';

/* ---- wire types ---------------------------------------------------------- */

/** Graph API interactive reply-button wire shape (§7.1) as stored in
    outbound_messages.payload.buttons and echoed by the outbound endpoint. */
export interface WaReplyButton {
  type: 'reply';
  reply: { id: string; title: string };
}

/** One row of GET /api/merchants/{id}/outbound (newest-first). */
export interface OutboundRow {
  id: string;
  transaction_id: string | null;
  kind: string; // confirmation_text | clarification | …
  body: string;
  buttons: WaReplyButton[] | null;
  created_at: string;
}

/** The webhook's per-message result (server/app/webhook.py _handle_message). */
export interface WebhookResult {
  message_id?: string | null;
  ok?: boolean;
  deduped?: boolean;
  merchant_id?: string;
  type?: string;
  ignored?: boolean;
  rejected?: boolean;
  persisted?: boolean;
  reply_ur?: string;
  reply?: string;
  transaction_id?: string;
  status?: string;
  confirmation_ur?: string;
  action?: string;
  error?: string;
}

/* ---- envelope builders (mirror scripts/simulate_inbound.py) --------------- */

function simMessageBase(waId: string): { from: string; id: string; timestamp: string } {
  const wamid =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '')
      : `${Date.now()}${Math.floor(Math.random() * 1e9)}`;
  return { from: waId, id: `wamid.SIM${wamid}`, timestamp: String(Math.floor(Date.now() / 1000)) };
}

function simPayload(waId: string, name: string, message: Record<string, unknown>): Record<string, unknown> {
  return {
    object: 'whatsapp_business_account',
    entry: [
      {
        id: 'SIM_WABA',
        changes: [
          {
            field: 'messages',
            value: {
              messaging_product: 'whatsapp',
              metadata: { display_phone_number: '15550001111', phone_number_id: 'SIM_PHONE_ID' },
              contacts: [{ profile: { name }, wa_id: waId }],
              messages: [message],
            },
          },
        ],
      },
    ],
  };
}

/** Plain text message (confirm words like "1", or anything → help reply). */
export function buildTextEnvelope(waId: string, name: string, text: string): unknown {
  const msg = { ...simMessageBase(waId), type: 'text', text: { body: text } };
  return simPayload(waId, name, msg);
}

/** Voice note / receipt photo — media rides the bizro_sim envelope. */
export function buildMediaEnvelope(
  waId: string,
  name: string,
  mediaB64: string,
  mimeType: string,
): unknown {
  const isAudio = mimeType.startsWith('audio/');
  const mediaMeta = { id: `SIM_MEDIA_${Date.now().toString(36)}`, mime_type: mimeType };
  const base = simMessageBase(waId);
  const msg = isAudio
    ? { ...base, type: 'audio' as const, audio: mediaMeta }
    : { ...base, type: 'image' as const, image: mediaMeta };
  return {
    ...simPayload(waId, name, msg),
    // Namespaced simulator envelope — honored only while WhatsApp is mock mode.
    bizro_sim: { media_b64: mediaB64, mime_type: mimeType },
  };
}

/** One-tap reply to the §7.1 confirm/correct buttons (interactive message). */
export function buildButtonEnvelope(
  waId: string,
  name: string,
  payload: 'confirm' | 'correct',
): unknown {
  // Graph API carries button.payload; older versions only button.text (§7.1) —
  // send both, exactly like a real WhatsApp button press would.
  const msg = {
    ...simMessageBase(waId),
    type: 'button',
    button: { payload, text: payload === 'confirm' ? 'درست ہے' : 'بدلیں' },
  };
  return simPayload(waId, name, msg);
}

/* ---- calls ------------------------------------------------------------------ */

/** POST /webhook/whatsapp. Long timeout: the pipeline runs inline on free-tier
    AI (STT + parse), so this resolves only after the reply is already stored. */
export async function postWebhookEnvelope(payload: unknown): Promise<WebhookResult[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000);
  try {
    const res = await fetch(`${API_BASE_URL}/webhook/whatsapp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`webhook ${res.status} ${res.statusText}`);
    const body: unknown = await res.json();
    const results = (body as { results?: unknown })?.results;
    return Array.isArray(results) ? (results as WebhookResult[]) : [];
  } finally {
    clearTimeout(timer);
  }
}

/** GET /api/merchants/{id}/outbound?limit= — Bizro's sent messages,
    newest-first. Throws on non-OK so the caller can decide (polling treats a
    failed poll as "try again", not an error surface). */
export async function fetchOutbound(merchantId: string, limit = 20): Promise<OutboundRow[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/merchants/${encodeURIComponent(merchantId)}/outbound?limit=${limit}`,
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (!res.ok) throw new Error(`outbound ${res.status} ${res.statusText}`);
  const body: unknown = await res.json();
  const rows = (body as { outbound?: unknown })?.outbound;
  return Array.isArray(rows) ? (rows as OutboundRow[]) : [];
}

/* ---- media helpers ------------------------------------------------------- */

/** Bytes → base64 (no data: prefix) in 32k chunks — String.fromCharCode has an
    argument-count ceiling, voice notes don't. */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/** Read a picked File as {b64, mime} for the bizro_sim envelope. */
export async function fileToSimMedia(
  file: File,
): Promise<{ b64: string; mime: string }> {
  const buf = await file.arrayBuffer();
  return { b64: bytesToBase64(new Uint8Array(buf)), mime: file.type || 'image/jpeg' };
}

/** Pick the best MediaRecorder mimeType the current browser actually supports
    (Chrome/Edge/Firefox: webm+opus, Safari: mp4, else: browser default). */
export function pickRecorderMime(): string {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return '';
  const candidates = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? '';
}
