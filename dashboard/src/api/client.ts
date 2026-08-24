/* Typed API client — hits the REST surface in server/schema.md §4:
     GET  /api/merchants/{id}/transactions?from=&to=&kind=
     GET  /api/merchants/{id}/udhar
     POST /api/transactions/{id}/confirm
     PATCH /api/transactions/{id}          (correction; server keeps original for audit)
     GET  /api/merchants/{id}/report/preview
   Live mode: set VITE_API_BASE_URL (e.g. http://localhost:8000) — that single env
   change swaps every screen from mock fixtures to the real server.
   Mock mode (no VITE_API_BASE_URL): clearly-labeled fixtures (STATUS.md D0-3) shaped
   exactly like schema.md §1; every result carries mock:true and screens surface a
   "mock data" banner so nothing fabricated is ever presented as real. */

import {
  MOCK_MERCHANT,
  MOCK_TRANSACTIONS,
  deriveReportPreview,
  deriveUdhar,
} from './mockData';
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
    reportPreview() {
      return req<CreditReportPreview>(`/api/merchants/${merchantId}/report/preview`).then(
        (data): Labeled<CreditReportPreview> => ({ mock: false, data: { ...data, mock: false } }),
      );
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

/** App-wide client. Mock unless VITE_API_BASE_URL is set (see dashboard/.env.example). */
export const api: ApiClient = env.VITE_API_BASE_URL
  ? liveClient(String(env.VITE_API_BASE_URL), String(env.VITE_MERCHANT_ID ?? 'me'))
  : mockClient();
