/* Merchant scope (D3-2) — the loan-officer reality: the dashboard can be pointed
   at any merchant the server knows (GET /api/merchants, schema.md §4). This
   provider owns the selection; the API singleton re-keys via setActiveMerchant
   (client.ts) and every screen re-fetches on merchantId change (effect dep).

   Persistence: localStorage 'bizro.merchant'; default 'me' (server-side first
   merchant — single-merchant demo needs zero configuration, ruling D1-2).
   Single-merchant state stays clean: the picker hides itself at ≤1 merchant. */

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { listMerchants, setActiveMerchant } from '../api/client';
import type { MerchantSummary } from '../types/schema';

export const MERCHANT_STORAGE_KEY = 'bizro.merchant';
export const DEFAULT_MERCHANT_ID = 'me';

interface MerchantState {
  merchants: MerchantSummary[];
  /** 'me' (first merchant) until a real id is chosen/persisted. */
  merchantId: string;
  setMerchant: (id: string) => void;
}

const MerchantContext = createContext<MerchantState>({
  merchants: [],
  merchantId: DEFAULT_MERCHANT_ID,
  setMerchant: () => {},
});

function readSavedId(): string {
  try {
    const saved = localStorage.getItem(MERCHANT_STORAGE_KEY);
    if (saved) return saved;
  } catch {
    /* private mode / storage disabled — default below */
  }
  return DEFAULT_MERCHANT_ID;
}

export function MerchantProvider({ children }: { children: ReactNode }) {
  const [merchantId, setMerchantId] = useState<string>(readSavedId);
  const [merchants, setMerchants] = useState<MerchantSummary[]>([]);

  // Re-key the API singleton + persist on every selection change.
  useEffect(() => {
    setActiveMerchant(merchantId);
    try {
      localStorage.setItem(MERCHANT_STORAGE_KEY, merchantId);
    } catch {
      /* persistence is best-effort, never fatal */
    }
  }, [merchantId]);

  // Load the picker list once. Normalizations:
  //  - a saved id the server no longer knows (and isn't 'me') → back to 'me';
  //  - 'me' + a multi-merchant list → the concrete first merchant, so the
  //    picker's <select> shows the truth instead of a phantom option.
  useEffect(() => {
    let alive = true;
    listMerchants().then((list) => {
      if (!alive) return;
      setMerchants(list);
      if (list.length === 0) return;
      setMerchantId((cur) => {
        if (cur === 'me') return list[0].id;
        return list.some((m) => m.id === cur) ? cur : 'me';
      });
    });
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo(
    () => ({ merchants, merchantId, setMerchant: setMerchantId }),
    [merchants, merchantId],
  );
  return <MerchantContext.Provider value={value}>{children}</MerchantContext.Provider>;
}

export function useMerchant(): MerchantState {
  return useContext(MerchantContext);
}
