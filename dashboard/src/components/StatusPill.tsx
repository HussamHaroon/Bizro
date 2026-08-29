/* StatusPill — schema.md §1 `status` (pending | confirmed | edited | rejected).
   Always icon + word (design.md §4.7 — never a bare colored dot). D4-1:
   sticker chip — tinted bg (10–14% alpha of the token color) + 2px ink-line
   border + radius 0 (square). Text pairs per tokens.css AA list: teal-ink on
   tint-teal, ledger-red on tint-red, ink-line on tint-gold / tint-neutral.
   Stickers stay SQUARE — the one rotated sticker per screen is the seal. */

import type { TransactionStatus } from '../types/schema';
import { IconCheck, IconEdited, IconPending, IconRejected } from './icons';
import { T } from '../i18n';

export interface StatusPillProps {
  status: TransactionStatus;
  className?: string;
}

interface PillSpec {
  icon: typeof IconCheck;
  en: string;
  ur: string;
  classes: string;
}

const SPECS: Record<TransactionStatus, PillSpec> = {
  pending: {
    icon: IconPending,
    en: 'Confirm pending',
    ur: 'تصدیق باقی',
    classes: 'bizro-tint-neutral text-ink-line',
  },
  confirmed: {
    icon: IconCheck,
    en: 'Verified',
    ur: 'تصدیق شدہ',
    classes: 'bizro-tint-teal text-teal-ink',
  },
  edited: {
    icon: IconEdited,
    en: 'Edited',
    ur: 'ترمیم شدہ',
    classes: 'bizro-tint-gold text-ink-line',
  },
  rejected: {
    icon: IconRejected,
    en: 'Rejected',
    ur: 'مسترد',
    classes: 'bizro-tint-red text-ledger-red',
  },
};

export function StatusPill({ status, className = '' }: StatusPillProps) {
  const { icon: Icon, en, ur, classes } = SPECS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip border-2 border-ink-line px-2.5 py-1 text-xs font-semibold ${classes} ${className}`}
    >
      <Icon className="h-[18px] w-[18px]" />
      <T en={en} ur={ur} />
    </span>
  );
}
