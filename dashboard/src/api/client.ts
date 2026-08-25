/* Typed API client — hits the REST surface in server/schema.md §4:
     GET  /api/merchants/{id}/transactions?from=&to=&kind=
     GET  /api/merchants/{id}/udhar
     POST /api/transactions/{id}/confirm
     PATCH /api/transactions/{id}          (correction; server keeps original for audit)
     GET  /api/merchants/{id}/report/preview
     GET  /api/media/{id}                  (audit drill-down: original voice note / photo)

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
  deriveUdhar,
} from './mockData';
import { adaptCanonicalReport, isCanonicalReport } from './reportAdapter';
import type {
  CreditReportPreview,
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

/** '' = same-origin (dev proxy → :8000); or an explicit origin. */
const BASE_URL = env.VITE_API_BASE_URL ? String(env.VITE_API_BASE_URL).replace(/\/$/, '') : '';
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
  return {
    mock: false,
    merchantId,
    listTransactions(query = {}) {
      const qs = new URLSearchParams();
      if (query.from) qs.set('from', query.from);
      if (query.to) qs.set('to', query.to);
      if (query.kind) qs.set('kind', query.kind);
      const suffix = qs.size ? `?${qs}` : '';
      return req<Transaction[]>(`/api/merchants/${merchantId}/transactions${suffix}`).then(
        (data): Labeled<Transaction[]> => ({ mock: false, data }),
      );
    },
    listUdhar() {
      return req<UdharOutstanding[]>(`/api/merchants/${merchantId}/udhar`).then(
        (data): Labeled<UdharOutstanding[]> => ({ mock: false, data }),
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
        const rows = await req<Transaction[]>(`/api/merchants/${merchantId}/transactions`);
        return {
          mock: false,
          data: adaptCanonicalReport(canonical, rows),
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

const live = liveClient(BASE_URL, MERCHANT_ID);
let mockImpl: ApiClient | null = null;
const getMock = (): ApiClient => (mockImpl ??= mockClient());

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
    return fellBack ? getMock().merchantId : MERCHANT_ID;
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
