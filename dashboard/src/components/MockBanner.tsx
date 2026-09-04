/* MockBanner — STATUS.md D0-3: mock data must be clearly labeled and never
   presented as real model output. TWO distinct honest messages:

   1. api.mock (offline fixtures): the live client failed before ever succeeding
      and the app fell back to fixtures — the banner says exactly that,
      subscribing to the client's mode flips via useSyncExternalStore.
   2. Seeded demo history on the LIVE server: rows whose source.raw_output
      carries mock === true are seeded examples, not real voice/photo entries.
      api.mock stays false against the live server, so the screens that render
      such rows report them via reportDemoRows() and this banner shows a
      persistent stamped disclosure while that data is on screen.

   Both wear the tokens' approved stamp pair — seal-gold fill + ink-black text.
   Both are hidden in print (bizro-no-print). */

import { useSyncExternalStore } from 'react';
import { api, clientSnapshot, subscribeClient } from '../api/client';

/* -- demo-rows store ---------------------------------------------------------
   Screens owning ledger data (MonthlyLedgerScreen today) publish whether the
   rows they are currently showing contain seeded demo entries. Module-level
   store + useSyncExternalStore keeps App.tsx wiring untouched. */

let demoRowsVisible = false;
const demoListeners = new Set<() => void>();

/** Call from the screen rendering the rows: true while any viewed row carries
    source.raw_output.mock === true. */
export function reportDemoRows(visible: boolean): void {
  if (demoRowsVisible === visible) return;
  demoRowsVisible = visible;
  for (const l of demoListeners) l();
}

function subscribeDemo(fn: () => void): () => void {
  demoListeners.add(fn);
  return () => {
    demoListeners.delete(fn);
  };
}

function demoSnapshot(): boolean {
  return demoRowsVisible;
}

export function MockBanner() {
  useSyncExternalStore(subscribeClient, clientSnapshot);
  const hasDemoRows = useSyncExternalStore(subscribeDemo, demoSnapshot);

  if (api.mock) {
    return (
      <p
        role="status"
        className="bizro-no-print border-b-[3px] border-ink-line bg-fill-gold px-4 py-2 text-center text-sm font-semibold text-ink-line"
      >
        Live server unreachable — showing clearly-labeled demo data
      </p>
    );
  }

  if (hasDemoRows) {
    return (
      <p
        role="status"
        className="bizro-no-print flex flex-wrap items-center justify-center gap-x-2 border-b-[3px] border-ink-line bg-fill-gold px-4 py-2 text-center text-sm font-semibold text-ink-line"
      >
        <span className="bizro-stamp bg-paper-raised text-xs">Demo data</span>
        <span>— seeded example entries</span>
      </p>
    );
  }

  return null;
}
