/* Typed API client — hits the REST surface in server/schema.md §4:
     GET  /api/merchants/{id}/transactions?from=&to=&kind=
     GET  /api/merchants/{id}/udhar
     POST /api/transactions/{id}/confirm
     PATCH /api/transactions/{id}          (correction; server keeps original for audit)
     GET  /api/merchants/{id}/report/preview
     GET  /api/media/{id}                  (audit drill-down: original voice note / photo)
     GET  /api/merchants/{id}/settings     (schema.md §8 — getSettings/putSettings below)
     PUT  /api/merchants/{id}/settings

   LIVE BY DEFAULT (D1-1 wiring): with VITE_API_BASE_URL unset the client targets
   same-origin /api — the Vite dev proxy already forwards /api to :8000, and a
   deployed build sits next to the server. The mock fixtures are used ONLY as a
   fallback when a live call fails BEFORE any live call has ever succeeded (server
   not running, wrong merchant id…); the fallback flips a subscribed, honestly
   labeled banner (MockBanner). Once live has answered once, later failures are
   real errors and surface as errors — never silently swapped data.

   Set VITE_API_BASE_URL to target a server on another origin. */

import {
  MOCK_MERCHANT,
  MOCK_TRANSACTIONS,
  deriveReportPreview,
  deriveStreak,
  deriveUdhar,
} from './mockData';
import { adaptCanonicalReport, isCanonicalReport } from './reportAdapter';
import type {
  CreditReportPreview,
  LanguageSetting,
  MerchantSettings,
  MerchantSettingsPut,
  MerchantSummary,
  NumeralStyle,
  ReadinessHistoryPoint,
  SavingsStreak,
  Transaction,
  TransactionKind,
  UdharOutstanding,
} from '../types/schema';

/** Every payload is labeled with where it came from (design.md §7.2 spirit). */
export interface Labeled<T> {
  mock: boolean;
  data: T;
}

export interface TransactionQuery {
  from?: string; // YYYY-MM-DD
  to?: string; // YYYY-MM-DD
  kind?: TransactionKind;
}

/** PATCH /api/transactions/{id} — merchant correction (audit preserved server-side). */
export type TransactionPatch = Partial<
  Pick<Transaction, 'amount_pkd' | 'description' | 'kind' | 'counterparty' | 'status' | 'flag'>
>;

export interface ApiClient {
  readonly mock: boolean;
  readonly merchantId: string;
  listTransactions(query?: TransactionQuery): Promise<Labeled<Transaction[]>>;
  listUdhar(): Promise<Labeled<UdharOutstanding[]>>;
  confirmTransaction(id: string): Promise<Labeled<Transaction>>;
  patchTransaction(id: string, patch: TransactionPatch): Promise<Labeled<Transaction>>;
  reportPreview(): Promise<Labeled<CreditReportPreview>>;
}

const env = import.meta.env;

/** '' = same-origin (dev proxy → :8000); or an explicit origin. Shared with
    the webhook POST path (api/simulator.ts) so both surfaces target the same
    server — the dev proxy already forwards /webhook alongside /api. */
export const API_BASE_URL = env.VITE_API_BASE_URL ? String(env.VITE_API_BASE_URL).replace(/\/$/, '') : '';
const BASE_URL = API_BASE_URL;
const MERCHANT_ID = String(env.VITE_MERCHANT_ID ?? 'me');

// -- live client ----------------------------------------------------------------

function liveClient(baseUrl: string, merchantId: string): ApiClient {
  const base = baseUrl.replace(/\/$/, '');
  async function req<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      ...init,
    });
    if (!res.ok) throw new Error(`API ${res.status} ${res.statusText} — ${path}`);
    return (await res.json()) as T;
  }
  // Server wraps transaction lists as {count, transactions}; accept both shapes.
  const txList = (d: unknown): Transaction[] =>
    Array.isArray(d) ? d : ((d as { transactions?: Transaction[] })?.transactions ?? []);
  return {
    mock: false,
    merchantId,
    listTransactions(query = {}) {
      const qs = new URLSearchParams();
      if (query.from) qs.set('from', query.from);
      if (query.to) qs.set('to', query.to);
      if (query.kind) qs.set('kind', query.kind);
      const suffix = qs.size ? `?${qs}` : '';
      return req<unknown>(`/api/merchants/${merchantId}/transactions${suffix}`).then(
        (data): Labeled<Transaction[]> => ({ mock: false, data: txList(data) }),
      );
    },
    listUdhar() {
      return req<unknown>(`/api/merchants/${merchantId}/udhar`).then(
        (data): Labeled<UdharOutstanding[]> => ({
          mock: false,
          data: Array.isArray(data)
            ? data
            : ((data as { customers?: UdharOutstanding[] })?.customers ?? []),
        }),
      );
    },
    confirmTransaction(id) {
      return req<Transaction>(`/api/transactions/${id}/confirm`, { method: 'POST' }).then(
        (data): Labeled<Transaction> => ({ mock: false, data }),
      );
    },
    patchTransaction(id, patch) {
      return req<Transaction>(`/api/transactions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }).then((data): Labeled<Transaction> => ({ mock: false, data }));
    },
    async reportPreview() {
      const payload = await req<unknown>(`/api/merchants/${merchantId}/report/preview`);
      // Server wraps as {cached, report}; the report itself is canonical §6.5.
      const canonical = (payload as { report?: unknown })?.report ?? payload;
      if (isCanonicalReport(canonical)) {
        const rows = await req<unknown>(`/api/merchants/${merchantId}/transactions`);
        return {
          mock: false,
          data: adaptCanonicalReport(canonical, txList(rows)),
        } as Labeled<CreditReportPreview>;
      }
      return { mock: false, data: { ...(payload as CreditReportPreview), mock: false } };
    },
  };
}

// -- mock client ------------------------------------------------------------------

function mockClient(): ApiClient {
  const state = new Map<string, Transaction>(MOCK_TRANSACTIONS.map((t) => [t.id, { ...t }]));
  const delay = <T>(value: T): Promise<Labeled<T>> =>
    new Promise((resolve) => setTimeout(() => resolve({ mock: true, data: value }), 120));

  return {
    mock: true,
    merchantId: MOCK_MERCHANT.id,
    async listTransactions(query = {}) {
      const items = [...state.values()]
        .filter((t) => (query.kind ? t.kind === query.kind : true))
        .filter((t) =>
          query.from ? t.occurred_at.slice(0, 10) >= query.from! : true,
        )
        .filter((t) => (query.to ? t.occurred_at.slice(0, 10) <= query.to! : true))
        .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
      return delay(items);
    },
    async listUdhar() {
      return delay(deriveUdhar([...state.values()]));
    },
    async confirmTransaction(id) {
      const t = state.get(id);
      if (!t) throw new Error(`mock: no transaction ${id}`);
      t.status = 'confirmed';
      state.set(id, t);
      return delay(t);
    },
    async patchTransaction(id, patch) {
      const t = state.get(id);
      if (!t) throw new Error(`mock: no transaction ${id}`);
      const next: Transaction = {
        ...t,
        ...patch,
        status: patch.status ?? (t.status === 'pending' ? 'edited' : t.status),
        // NOTE: the real server keeps the original values alongside for the audit
        // trail (schema.md §4); the mock only reflects the visible outcome.
      };
      state.set(id, next);
      return delay(next);
    },
    async reportPreview() {
      return delay(deriveReportPreview([...state.values()]));
    },
  };
}

// -- fallback orchestration --------------------------------------------------------

/** Active merchant for every live call (D3-2 merchant picker). The client is a
    module singleton; setActiveMerchant swaps its live instance — surgical, no
    context-ification of every call site. 'me' = server-side first merchant. */
let liveMerchantId = MERCHANT_ID;
let live = liveClient(BASE_URL, MERCHANT_ID);

/** Re-key all live calls to a merchant (loan-officer picker, D1-2/D3-2). */
export function setActiveMerchant(merchantId: string): void {
  if (merchantId === liveMerchantId) return;
  liveMerchantId = merchantId;
  live = liveClient(BASE_URL, merchantId);
}

/** The id every live call currently keys on (mock fixtures are single-merchant). */
export function currentMerchantId(): string {
  return fellBack ? getMock().merchantId : liveMerchantId;
}

/** GET /api/merchants — picker source (schema.md §4, D1-2). Deliberately OUTSIDE
    the attempt() machinery: an older server without the route (or a down server)
    must not flip the whole app to mock fixtures — the picker just stays hidden.
    Mock mode lists the single fixture merchant (also hidden: ≤1 merchant). */
export async function listMerchants(): Promise<MerchantSummary[]> {
  if (fellBack) return [MOCK_MERCHANT];
  try {
    const res = await fetch(`${BASE_URL}/api/merchants`, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) return [];
    const data: unknown = await res.json();
    if (!Array.isArray(data)) return [];
    return data.filter(
      (m): m is MerchantSummary =>
        !!m && typeof (m as MerchantSummary).id === 'string' && typeof (m as MerchantSummary).display_name === 'string',
    );
  } catch {
    return []; // server down / route missing → single-merchant demo stays clean
  }
}

let mockImpl: ApiClient | null = null;
const getMock = (): ApiClient => (mockImpl ??= mockClient());

/** GET /api/merchants/{id}/report/history (schema.md §7.2) — trend sparkline
    source. OPTIONAL endpoint (backend lands in parallel): any absence (404,
    older server, network) → null and the sparkline simply doesn't render —
    never an error, never a fabricated trend. Mock fixtures carry no report
    history (only a single preview) → null there too. */
export async function fetchReportHistory(): Promise<ReadinessHistoryPoint[] | null> {
  if (fellBack) return null;
  try {
    const res = await fetch(
      `${BASE_URL}/api/merchants/${encodeURIComponent(currentMerchantId())}/report/history`,
      { headers: { 'Content-Type': 'application/json' } },
    );
    if (!res.ok) return null;
    const payload: unknown = await res.json();
    const history = (payload as { history?: unknown })?.history;
    if (!Array.isArray(history)) return null;
    const points = history.filter(
      (p): p is ReadinessHistoryPoint =>
        !!p &&
        typeof (p as ReadinessHistoryPoint).generated_at === 'string' &&
        typeof (p as ReadinessHistoryPoint).score === 'number' &&
        Number.isFinite((p as ReadinessHistoryPoint).score),
    );
    return points.length >= 2 ? points : null; // a trend needs ≥2 points
  } catch {
    return null;
  }
}

/** GET /api/merchants/{id}/streak (schema.md §7.3) — ledger hero chip source.
    OPTIONAL endpoint: any absence → null, chip hidden. In mock mode the streak
    is DERIVED from the fixture transactions (deriveStreak — an honest
    computation over the same data the ledger shows, never a made-up number). */
export async function fetchStreak(): Promise<SavingsStreak | null> {
  if (fellBack) return deriveStreak(MOCK_TRANSACTIONS);
  try {
    const res = await fetch(
      `${BASE_URL}/api/merchants/${encodeURIComponent(currentMerchantId())}/streak`,
      { headers: { 'Content-Type': 'application/json' } },
    );
    if (!res.ok) return null;
    const d: unknown = await res.json();
    if (!d || typeof (d as SavingsStreak).streak_weeks !== 'number') return null;
    const s = d as SavingsStreak;
    return {
      streak_weeks: s.streak_weeks,
      best_streak_weeks: typeof s.best_streak_weeks === 'number' ? s.best_streak_weeks : s.streak_weeks,
      current_week_positive: Boolean(s.current_week_positive),
    };
  } catch {
    return null;
  }
}

/** GET+PUT /api/merchants/{id}/settings (schema.md §8, ruling D4-2) — per-
    merchant account settings. Standalone functions taking an EXPLICIT merchant
    id (callers pass the merchant-picker selection), deliberately OUTSIDE the
    attempt() mock-flip machinery like listMerchants: settings are account
    config, not financial data, and an older server without the route must
    never flip the whole app to fixtures.
    Read: any absence (network, 4xx/5xx, bad shape) → null; the app keeps its
    localStorage first-paint state (§8). Write: throws on live failure so the
    Settings screen can show the inline error; in mock mode it writes an
    in-memory row so the offline demo still saves visibly. */

function normalizeSettings(payload: unknown): MerchantSettings | null {
  if (!payload || typeof payload !== 'object') return null;
  const row = payload as Record<string, unknown>;
  const { language, numeral_style, updated_at } = row;
  if (language !== 'ur' && language !== 'en' && language !== 'mixed') return null;
  if (numeral_style !== 'western' && numeral_style !== 'urdu') return null;
  return {
    language,
    numeral_style,
    updated_at: typeof updated_at === 'string' ? updated_at : null,
  };
}

/** Mock-mode stand-in for merchant_settings rows (session-lifetime only). */
const mockSettingsRows = new Map<string, MerchantSettings>();

export async function getSettings(merchantId: string): Promise<MerchantSettings | null> {
  if (fellBack) {
    return (
      mockSettingsRows.get(merchantId) ?? {
        language: 'mixed',
        numeral_style: 'western',
        updated_at: null,
      }
    );
  }
  try {
    const res = await fetch(`${BASE_URL}/api/merchants/${encodeURIComponent(merchantId)}/settings`, {
      headers: { 'Content-Type': 'application/json' },
    });
    // Missing row is a 200 with implied defaults (§8) — only a missing ROUTE
    // or a down server lands here, and both mean "keep local state".
    if (!res.ok) return null;
    return normalizeSettings(await res.json());
  } catch {
    return null;
  }
}

export async function putSettings(
  merchantId: string,
  body: MerchantSettingsPut,
): Promise<MerchantSettings> {
  // Nulls count as "not provided" (mirrors the server's MerchantSettingsPut).
  const clean: { language?: LanguageSetting; numeral_style?: NumeralStyle } = {};
  if (body.language != null) clean.language = body.language;
  if (body.numeral_style != null) clean.numeral_style = body.numeral_style;
  if (clean.language === undefined && clean.numeral_style === undefined) {
    throw new Error('No settings to save'); // the server 422s an empty body too
  }
  if (fellBack) {
    const current =
      mockSettingsRows.get(merchantId) ??
      ({ language: 'mixed', numeral_style: 'western', updated_at: null } as MerchantSettings);
    const merged: MerchantSettings = {
      language: clean.language ?? current.language,
      numeral_style: clean.numeral_style ?? current.numeral_style,
      updated_at: new Date().toISOString(),
    };
    mockSettingsRows.set(merchantId, merged);
    await new Promise((resolve) => setTimeout(resolve, 120)); // demo-feel parity
    return merged;
  }
  const res = await fetch(`${BASE_URL}/api/merchants/${encodeURIComponent(merchantId)}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(clean),
  });
  if (!res.ok) throw new Error(`API ${res.status} ${res.statusText} — could not save settings`);
  const row = normalizeSettings(await res.json());
  if (!row) throw new Error('Unexpected settings response from server');
  return row;
}

/** Flips to true only when a live call fails BEFORE any live success — after
    that, live is genuinely up and failures are surfaced as errors instead. */
let fellBack = false;
let liveEverSucceeded = false;
let fallbackReason: string | null = null;

const listeners = new Set<() => void>();
/** Stable cached snapshot — useSyncExternalStore requires referential stability. */
let snapshot = JSON.stringify({ mock: false, reason: null as string | null });

function notify() {
  snapshot = JSON.stringify({ mock: fellBack, reason: fallbackReason });
  for (const l of listeners) l();
}

/** Subscribe to live/mock mode flips (MockBanner). Returns an unsubscribe fn. */
export function subscribeClient(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Cached {mock, reason} snapshot for useSyncExternalStore. */
export function clientSnapshot(): string {
  return snapshot;
}

async function attempt<T>(op: (c: ApiClient) => Promise<Labeled<T>>): Promise<Labeled<T>> {
  if (!fellBack) {
    try {
      const res = await op(live);
      liveEverSucceeded = true;
      return res;
    } catch (e) {
      if (liveEverSucceeded) throw e; // live was working — a real error, show it
      fellBack = true;
      fallbackReason = e instanceof Error ? e.message : String(e);
      notify();
    }
  }
  return op(getMock());
}

/** App-wide client. Live-first (same-origin /api by default); honest mock
    fallback on first failure — see the header comment and MockBanner. */
export const api: ApiClient = {
  get mock() {
    return fellBack;
  },
  get merchantId() {
    return currentMerchantId();
  },
  listTransactions: (query) => attempt((c) => c.listTransactions(query)),
  listUdhar: () => attempt((c) => c.listUdhar()),
  confirmTransaction: (id) => attempt((c) => c.confirmTransaction(id)),
  patchTransaction: (id, patch) => attempt((c) => c.patchTransaction(id, patch)),
  reportPreview: () => attempt((c) => c.reportPreview()),
};

/** Absolute URL for GET /api/media/{id} (audit drill-down). Never called while
    the client runs on mock fixtures — mock media ids cannot resolve. */
export function mediaUrl(id: string): string {
  return `${BASE_URL}/api/media/${encodeURIComponent(id)}`;
}
