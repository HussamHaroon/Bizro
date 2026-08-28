/* StatusPill — schema.md §1 `status` (pending | confirmed | edited | rejected).
   Always icon + word (design.md §4.7 — never a bare colored dot). D3-4: soft
   tinted chip (10–12% alpha of the token color + hairline border) instead of
   outline-only. Text pairs per tokens.css AA list: teal-ink on tint-teal,
   ledger-red on tint-red, ink-black on tint-gold / tint-neutral. Radius stays
   6px (tokens: "crisp, stamp-like — no pill shapes"). */

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
    classes: 'bizro-tint-neutral text-ink-black',
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
    classes: 'bizro-tint-gold text-ink-black',
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
      className={`inline-flex items-center gap-1.5 rounded-card border px-2.5 py-1 text-xs font-semibold ${classes} ${className}`}
    >
      <Icon className="h-[18px] w-[18px]" />
      <T en={en} ur={ur} />
    </span>
  );
}
