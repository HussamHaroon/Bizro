/* LedgerRow — design.md §4.4: transaction lists sit on horizontal ledger rules
   like a physical register, never floating shadow cards. Money direction is
   signaled by icon + word + position + color together (§4.7). AI-sourced rows
   show the seal mark and a one-tap edit affordance (§7.2); pending rows get an
   inline confirm action that fires the stamp "thud" on the row's seal.

   D4r fix 1 (owner review 2026-08-29, row de-density): "cards shout, rows
   whisper." Rows ride THIN 1.5px ink rules with NO shadows and no 3px borders;
   the meta line carries ONE status chip (the row's price flag folds into it —
   StatusPill flag prop); the per-row source chip is gone (provenance stays in
   the drill-down AuditTrail, and the SealMark still marks AI vs manual);
   vertical padding is up ~15%; Edit / Confirm keep 48px targets but take the
   quiet shadowless treatment (.bizro-btn-quiet) — rows never carry shadows. */

import type { ReactNode } from 'react';
import type { Transaction, TransactionKind } from '../types/schema';
import { AmountText, toneForKind } from './AmountText';
import { AuditTrail } from './AuditTrail';
import { SealMark } from './TrustSealBadge';
import { StatusPill } from './StatusPill';
import {
  IconChevronDown,
  IconEdit,
  IconExpense,
  IconSale,
  IconUdharGiven,
  IconUdharSettled,
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
      {/* min-h-14 (56px) touch-friendly row height + py-[7px] (~15% over the
          D3 py-1.5) breathing room (D4r fix 1); row buttons keep 48px targets. */}
      <div className="flex min-h-14 flex-wrap items-center gap-y-1 py-[7px]">
        {/* Main target: row details / audit drill-down. */}
        <button
          type="button"
          onClick={onToggleDetails}
          aria-expanded={expanded}
          className="flex min-h-touch flex-1 items-center gap-3 rounded-button px-1 py-1 text-left transition-colors duration-200 ease-out hover:bg-paper"
        >
          <KindIcon className={`h-8 w-8 ${kind.tone}`} />
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold text-ink-line">
                <T en={kind.en} ur={kind.ur} />
              </span>
              {t.counterparty && (
                <span className="truncate text-sm text-ink-line opacity-80">· {t.counterparty.name}</span>
              )}
              {aiSourced && (
                <SealMark
                  variant={t.status === 'pending' ? 'pending' : 'verified'}
                  stampIn={justConfirmed}
                  className="translate-y-[1px]"
                />
              )}
            </span>
            {/* Meta line (D4r fix 1): datetime + the ONE status chip — the
                flag folds into it; source detail lives in the drill-down. */}
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <span className="text-ink-line opacity-75">{formatDateTime(t.occurred_at)}</span>
              <StatusPill status={t.status} flag={t.flag !== 'none' ? t.flag : null} />
            </span>
          </span>
          <span className="ml-auto pr-1 text-right">
            <AmountText value={t.amount_pkd} tone={toneForKind(t.kind)} />
          </span>
          <IconChevronDown
            className={`h-6 w-6 text-ink-green transition-transform duration-200 ease-out motion-reduce:transition-none ${expanded ? 'rotate-180' : ''}`}
          />
        </button>

        <span className="flex items-center gap-2">
          {aiSourced && onEdit && (
            <button
              type="button"
              onClick={() => onEdit(t)}
              className="bizro-btn-quiet inline-flex min-h-touch items-center gap-1.5 rounded-button border-2 border-ink-line bg-paper-raised px-2.5 text-sm font-semibold text-ink-line hover:bg-paper"
            >
              <IconEdit className="h-[18px] w-[18px] text-ink-green" />
              <T en="Edit" ur="بدلیں" />
            </button>
          )}
          {canConfirm && (
            <button
              type="button"
              onClick={() => onConfirm(t)}
              className="bizro-btn-quiet inline-flex min-h-touch items-center gap-1.5 rounded-button border-2 border-ink-line bg-fill-green px-3 text-sm font-semibold text-paper hover:bg-ink-green-hover"
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

/** Day-group heading between ledger rule runs — generous spacing on touch (D3). */
export function LedgerDayHeader({ children }: { children: ReactNode }) {
  return (
    <li className="bizro-rule-h bizro-tint-neutral">
      <p className="px-1 py-[9px] font-numerals text-sm font-semibold tracking-wide text-ink-green sm:py-1.5">
        {children}
      </p>
    </li>
  );
}
