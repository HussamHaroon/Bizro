/* Settings screen — simplified English-only (owner directive 2026-09-04:
   "keep everything in english"). The old language (ur / mixed / en) and
   numeral-style pickers were removed with the language-mode system; the
   GET/PUT /api/merchants/{id}/settings endpoint still exists server-side and
   the client functions stay in api/client.ts, but this screen no longer
   drives them. What remains is the one thing a merchant (or a loan officer
   demoing the dashboard) needs to confirm here: which account is active. */

import { IconSettings } from '../components/icons';
import { ScreenHeader } from '../components/ScreenHeader';
import { useMerchant } from '../merchant';

export function SettingsScreen() {
  const { merchants, merchantId } = useMerchant();
  const merchant = merchants.find((m) => m.id === merchantId);

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconSettings className="h-9 w-9 text-ink-green" />}
        title="Settings"
        purpose="Your account"
      />

      <section className="bizro-card bizro-card-hover flex flex-col gap-4 px-5 py-5 sm:px-6 sm:py-6">
        <header className="flex flex-col gap-1">
          <h2 className="font-numerals text-[22px] font-semibold text-ink-line">Account</h2>
          <p className="text-sm text-ink-line opacity-80">
            The merchant whose records you are viewing.
          </p>
        </header>

        <div className="flex flex-wrap items-baseline gap-x-2 border-t-2 border-ink-line pt-4 text-sm text-ink-line">
          <span className="font-semibold">Shop name:</span>
          <span className="font-numerals text-base font-semibold">
            {merchant?.display_name ?? 'Demo merchant'}
          </span>
        </div>

        <p className="text-xs text-ink-line opacity-75">
          Bizro works in English, and all amounts use regular numbers (1-2-3).
        </p>
      </section>
    </div>
  );
}
