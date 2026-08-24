/* MockBanner — STATUS.md D0-3: mock data must be clearly labeled and never
   presented as real model output. Shipped whenever the API client runs on
   fixtures (no VITE_API_BASE_URL). seal-gold fill + ink-black text = the
   tokens' approved stamp pair. */

import { api } from '../api/client';

export function MockBanner() {
  if (!api.mock) return null;
  return (
    <p
      role="status"
      className="bg-seal-gold px-4 py-2 text-center text-sm font-semibold text-ink-black"
    >
      Demo data (no live server) ·{' '}
      <span className="bizro-urdu font-normal" lang="ur">
        نمائشی ڈیٹا
      </span>{' '}
      — set <code className="font-mono">VITE_API_BASE_URL</code> for live records
    </p>
  );
}
