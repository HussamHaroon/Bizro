/* MerchantPicker (D3-2, schema.md §4 GET /api/merchants) — the loan-officer
   switcher. Styled native <select> (a picker is the one control where the
   platform widget beats a custom sheet: keyboard + screen-reader + touch free).
   Hidden when the server knows ≤1 merchant (the current demo default) so the
   single-merchant UI stays clean. text-base input = iOS zoom prevention.
   Icon (IconCustomer) is paired with the selected merchant's name — the word
   travels with the icon at every state (§4.7). */

import { useMerchant } from '../merchant';
import { useT } from '../i18n';
import { IconCustomer } from './icons';

export interface MerchantPickerProps {
  /** Layout tweaks from the call site (top bar vs mobile sheet). */
  className?: string;
  selectClassName?: string;
}

export function MerchantPicker({ className = '', selectClassName = '' }: MerchantPickerProps) {
  const { merchants, merchantId, setMerchant } = useMerchant();
  const { pick } = useT();
  if (merchants.length <= 1) return null;
  return (
    <label className={`inline-flex min-h-touch items-center gap-2 ${className}`.trim()}>
      <IconCustomer className="h-6 w-6 shrink-0 text-ink-green" />
      <select
        value={merchantId}
        onChange={(e) => setMerchant(e.target.value)}
        aria-label={pick('Choose merchant', 'دکاندار چنیں')}
        className={`min-h-touch w-full max-w-44 rounded-chip border-[3px] border-ink-line bg-paper-raised px-2 text-base font-semibold text-ink-line ${selectClassName}`.trim()}
      >
        {merchants.map((m) => (
          <option key={m.id} value={m.id}>
            {m.display_name}
          </option>
        ))}
      </select>
    </label>
  );
}
