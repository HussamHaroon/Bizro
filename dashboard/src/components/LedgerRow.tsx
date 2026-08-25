/* LedgerRow — design.md §4.4: transaction lists sit on horizontal ledger rules
   like a physical register, never floating shadow cards. Money direction is
   signaled by icon + word + position + color together (§4.7). AI-sourced rows
   show the seal mark and a one-tap edit affordance (§7.2); pending rows get an
   inline confirm action that fires the stamp "thud" on the row's seal. */

import type { ReactNode } from 'react';
import type { Transaction, TransactionFlag, TransactionKind, SourceType } from '../types/schema';
import { AmountText, toneForKind } from './AmountText';
import { AuditTrail } from './AuditTrail';
import { SealMark } from './TrustSealBadge';
import { StatusPill } from './StatusPill';
import {
  IconChevronDown,
  IconEdit,
  IconExpense,
  IconManual,
  IconPhoto,
  IconSale,
  IconUdharGiven,
  IconUdharSettled,
  IconVoice,
} from './icons';
import { formatDateTime } from '../lib/format';
import { T } from '../i18n';

export interface LedgerRowProps {
  transaction: Transaction;
  expanded?: boolean;
  onToggleDetails?: () => void;
  /** One-tap correction (design.md §7.2) — shown on every AI-sourced row. */
  onEdit?: (t: Transaction) => void;
  /** Pending-entry confirm action; triggers the 300ms seal stamp on completion. */
  onConfirm?: (t: Transaction) => void;
  justConfirmed?: boolean;
}

const KIND_SPEC: Record<
  TransactionKind,
  { icon: typeof IconSale; en: string; ur: string; tone: string }
> = {
  sale: { icon: IconSale, en: 'Sale', ur: 'فروخت', tone: 'text-settled-teal' },
  expense: { icon: IconExpense, en: 'Expense', ur: 'خرچ', tone: 'text-ledger-red' },
  udhar_given: { icon: IconUdharGiven, en: 'Udhar', ur: 'ادھار', tone: 'text-ledger-red' },
  udhar_settlement: { icon: IconUdharSettled, en: 'Repaid', ur: 'وصولی', tone: 'text-settled-teal' },
};

const SOURCE_SPEC: Record<SourceType, { icon: typeof IconVoice; en: string; ur: string }> = {
  voice: { icon: IconVoice, en: 'Voice', ur: 'آواز' },
  photo: { icon: IconPhoto, en: 'Photo', ur: 'تصویر' },
  manual: { icon: IconManual, en: 'Manual', ur: 'دستی' },
};

const FLAG_SPEC: Record<Exclude<TransactionFlag, 'none'>, { en: string; ur: string }> = {
  price_anomaly: { en: 'Price check', ur: 'قیمت دیکھیں' },
  total_mismatch: { en: 'Total check', ur: 'کل دیکھیں' },
  duplicate_suspect: { en: 'Duplicate?', ur: 'نقل؟' },
  low_confidence: { en: 'Low confidence', ur: 'کم اعتماد' },
};

function SourceChip({ type }: { type: SourceType }) {
  const { icon: Icon, en, ur } = SOURCE_SPEC[type];
  return (
    <span className="inline-flex items-center gap-1 rounded-card bg-paper-cream px-1.5 py-0.5 text-ink-black opacity-90">
      <Icon className="h-[15px] w-[15px] text-ink-green" />
      <T en={en} ur={ur} />
    </span>
  );
}

function FlagChip({ flag }: { flag: Exclude<TransactionFlag, 'none'> }) {
  const { en, ur } = FLAG_SPEC[flag];
  return (
    <span className="inline-flex items-center gap-1 rounded-card border border-rule-line bg-paper-cream px-1.5 py-0.5 font-semibold text-ledger-red">
      <span aria-hidden="true">▲</span>
      <T en={en} ur={ur} />
    </span>
  );
}

export function LedgerRow({
  transaction: t,
  expanded = false,
  onToggleDetails,
  onEdit,
  onConfirm,
  justConfirmed = false,
}: LedgerRowProps) {
  const kind = KIND_SPEC[t.kind];
  const KindIcon = kind.icon;
  const aiSourced = t.source.type !== 'manual';
  const canConfirm = t.status === 'pending' && onConfirm;

  return (
    <li className="bizro-rule-h">
      <div className="flex flex-wrap items-center gap-y-1 py-1.5">
        {/* Main target: row details / audit drill-down. */}
        <button
          type="button"
          onClick={onToggleDetails}
          aria-expanded={expanded}
          className="flex min-h-touch flex-1 items-center gap-3 rounded-button px-1 py-1 text-left transition-colors duration-200 ease-out hover:bg-paper-cream"
        >
          <KindIcon className={`h-8 w-8 ${kind.tone}`} />
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold text-ink-black">
                <T en={kind.en} ur={kind.ur} />
              </span>
              {t.counterparty && (
                <span className="truncate text-sm text-ink-black opacity-80">· {t.counterparty.name}</span>
              )}
              {aiSourced && (
                <SealMark
                  variant={t.status === 'pending' ? 'pending' : 'verified'}
                  stampIn={justConfirmed}
                  className="translate-y-[1px]"
                />
              )}
            </span>
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <span className="text-ink-black opacity-75">{formatDateTime(t.occurred_at)}</span>
              <SourceChip type={t.source.type} />
              {t.flag !== 'none' && <FlagChip flag={t.flag} />}
              <StatusPill status={t.status} />
            </span>
          </span>
          <span className="ml-auto pr-1 text-right">
            <AmountText value={t.amount_pkd} tone={toneForKind(t.kind)} />
          </span>
          <IconChevronDown
            className={`h-6 w-6 text-ink-green transition-transform duration-200 ease-out ${expanded ? 'rotate-180' : ''}`}
          />
        </button>

        <span className="flex items-center gap-2">
          {aiSourced && onEdit && (
            <button
              type="button"
              onClick={() => onEdit(t)}
              className="inline-flex min-h-touch items-center gap-1.5 rounded-button border border-rule-line bg-paper-raised px-2.5 text-sm font-semibold text-ink-black transition-colors duration-200 ease-out hover:bg-paper-cream"
            >
              <IconEdit className="h-[18px] w-[18px] text-ink-green" />
              <T en="Edit" ur="بدلیں" />
            </button>
          )}
          {canConfirm && (
            <button
              type="button"
              onClick={() => onConfirm(t)}
              className="inline-flex min-h-touch items-center gap-1.5 rounded-button bg-ink-green px-3 text-sm font-semibold text-paper-cream transition-colors duration-200 ease-out hover:bg-ink-green-hover"
            >
              <T en="Confirm" ur="تصدیق" />
            </button>
          )}
        </span>
      </div>

      {expanded && (
        <div className="pb-3 pl-1 pr-1">
          <AuditTrail
            transaction={t}
            onEdit={onEdit ? () => onEdit(t) : undefined}
            onConfirm={onConfirm ? () => onConfirm(t) : undefined}
            justConfirmed={justConfirmed}
          />
        </div>
      )}
    </li>
  );
}

/** Day-group heading between ledger rule runs. */
export function LedgerDayHeader({ children }: { children: ReactNode }) {
  return (
    <li className="bizro-rule-h bg-paper-cream/60">
      <p className="px-1 py-1.5 font-numerals text-sm font-semibold tracking-wide text-ink-green">
        {children}
      </p>
    </li>
  );
}
