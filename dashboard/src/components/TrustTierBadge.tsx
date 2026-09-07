/* TrustTierBadge — schema.md §11 trust ladder as a chip (officer-portal).
   The tier answers ONE officer question: who besides the merchant has vouched
   for this entry?

     self_reported      — neutral rule-line chip: it is the merchant's word,
                          nothing more (the honest default, never styled down)
     customer_confirmed — settled-teal: the counterparty on the entry confirmed
     third_party        — seal-gold with the seal motif: an external party (e.g.
                          the distributor via POST /transactions/{id}/
                          verify-supplier) confirmed it — the top of the ladder

   §4.7 law: ALWAYS icon + word — color is never the only signal. The chip is
   SQUARE (radius 0, D4-1); the rotated rubber stamp stays the one tilted
   sticker on a screen, so this seal motif is an upright dashed roundel.
   AA pairs per tokens.css: ink-line on tint-neutral, teal-ink on tint-teal,
   ink-line on gold-fill (the approved stamp pair). */

import type { TrustTier } from '../types/schema';
import { IconCheck, IconManual } from './icons';

export type TrustTierBadgeSize = 'sm' | 'md';

export interface TrustTierBadgeProps {
  /** Undefined/null renders the honest default: self_reported (server
      transaction_to_wire does the same). */
  tier: TrustTier | null | undefined;
  size?: TrustTierBadgeSize;
  className?: string;
}

const TIER_WORDS: Record<TrustTier, string> = {
  self_reported: 'Self-reported',
  customer_confirmed: 'Customer confirmed',
  third_party: 'Supplier verified',
};

const TIER_TITLES: Record<TrustTier, string> = {
  self_reported: 'Entry as the merchant told it — no one else has confirmed it yet',
  customer_confirmed: 'The customer on this entry confirmed the amount',
  third_party: 'An external party (the supplier/distributor) confirmed this entry via WhatsApp',
};

/** The upright seal roundel — dashed ink ring + check, reads "stamped" at
    14px. currentColor keeps it on-token inside the gold fill. */
function SealTierGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" focusable="false">
      <circle
        cx="12"
        cy="12"
        r="10"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeDasharray="3 2.2"
      />
      <path
        d="M8 12.2 11 15.2 16.2 9.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="square"
      />
    </svg>
  );
}

const ICON_CLASS: Record<TrustTierBadgeSize, string> = {
  sm: 'h-[18px] w-[18px]',
  md: 'h-5 w-5',
};

const SIZE_CLASS: Record<TrustTierBadgeSize, string> = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
};

export function TrustTierBadge({ tier, size = 'sm', className = '' }: TrustTierBadgeProps) {
  const t: TrustTier = tier ?? 'self_reported';
  const iconClass = ICON_CLASS[size];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line font-semibold ${SIZE_CLASS[size]} ${
        t === 'third_party'
          ? 'bg-fill-gold text-ink-line'
          : t === 'customer_confirmed'
            ? 'bizro-tint-teal text-teal-ink'
            : 'bizro-tint-neutral text-ink-line'
      } ${className}`}
      title={TIER_TITLES[t]}
    >
      {t === 'third_party' ? (
        <SealTierGlyph className={iconClass} />
      ) : t === 'customer_confirmed' ? (
        <IconCheck className={iconClass} />
      ) : (
        <IconManual className={iconClass} />
      )}
      {TIER_WORDS[t]}
    </span>
  );
}
