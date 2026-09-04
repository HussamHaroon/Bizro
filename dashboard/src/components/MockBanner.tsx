/* MockBanner — STATUS.md D0-3: mock data must be clearly labeled and never
   presented as real model output. Live-by-default wiring (D1-1): the banner
   appears only when the live client actually failed before ever succeeding and
   the app fell back to fixtures — and it says exactly that, subscribing to the
   client's mode flips via useSyncExternalStore. seal-gold fill + ink-black
   text = the tokens' approved stamp pair. Hidden in print. */

import { useSyncExternalStore } from 'react';
import { api, clientSnapshot, subscribeClient } from '../api/client';

export function MockBanner() {
  useSyncExternalStore(subscribeClient, clientSnapshot);
  if (!api.mock) return null;
  return (
    <p
      role="status"
      className="bizro-no-print border-b-[3px] border-ink-line bg-fill-gold px-4 py-2 text-center text-sm font-semibold text-ink-line"
    >
      Live server unreachable — showing clearly-labeled demo data
    </p>
  );
}
