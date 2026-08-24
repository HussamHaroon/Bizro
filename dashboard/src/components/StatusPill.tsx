/* StatusPill — schema.md §1 `status` (pending | confirmed | edited | rejected).
   Always icon + word (design.md §4.7 — never a bare colored dot). Radius stays 6px
   (tokens: "crisp, stamp-like — no pill shapes" even though the name says pill). */

import type { TransactionStatus } from '../types/schema';
import { IconCheck, IconEdited, IconPending, IconRejected } from './icons';

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
    classes: 'bg-paper-raised text-ink-black border-rule-line',
  },
  confirmed: {
    icon: IconCheck,
    en: 'Verified',
    ur: 'تصدیق شدہ',
    classes: 'bg-paper-raised text-settled-teal border-rule-line',
  },
  edited: {
    icon: IconEdited,
    en: 'Edited',
    ur: 'ترمیم شدہ',
    classes: 'bg-paper-raised text-ink-black border-seal-gold',
  },
  rejected: {
    icon: IconRejected,
    en: 'Rejected',
    ur: 'مسترد',
    classes: 'bg-paper-raised text-ledger-red border-rule-line',
  },
};

export function StatusPill({ status, className = '' }: StatusPillProps) {
  const { icon: Icon, en, ur, classes } = SPECS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-card border px-2 py-0.5 text-xs font-semibold ${classes} ${className}`}
    >
      <Icon className="h-[18px] w-[18px]" />
      <span>{en}</span>
      <span className="bizro-urdu font-normal" lang="ur">
        {ur}
      </span>
    </span>
  );
}
