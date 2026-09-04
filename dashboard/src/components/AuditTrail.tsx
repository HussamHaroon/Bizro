/* AuditTrail — the drill-down behind every entry (design.md §7.2 / §7.1's defence
   line for the Credit Readiness Report): source reference (voice note / receipt
   photo / manual), model, confidence, raw transcript where present, and the
   always-visible edit affordance. Used by LedgerRow expansions and the credit
   report line items. Cream panel + rule-line border, no shadow (elevation rule).
   Urdu runs below (transcript, WhatsApp confirmation) are SERVER DATA — the
   original artifact under audit — so they stay as-is. */

import type { Transaction } from '../types/schema';
import { AmountText, toneForKind } from './AmountText';
import { Button } from './Button';
import { SourceMedia } from './SourceMedia';
import { TrustSealBadge } from './TrustSealBadge';
import { formatConfidence, formatDateTime, formatPkr } from '../lib/format';

export interface AuditTrailProps {
  transaction: Transaction;
  onEdit?: () => void;
  onConfirm?: () => void;
  justConfirmed?: boolean;
}

const SOURCE_WORDS: Record<Transaction['source']['type'], string> = {
  voice: 'Voice note',
  photo: 'Receipt photo',
  manual: 'Entered by hand',
};

export function AuditTrail({ transaction: t, onEdit, onConfirm, justConfirmed = false }: AuditTrailProps) {
  const ai = t.source.type !== 'manual';
  const src = SOURCE_WORDS[t.source.type];

  return (
    <div className="bizro-card flex flex-col gap-3 px-4 py-4 text-sm">
      {/* The seal with its always-visible correction affordance (design.md §7.2). */}
      {ai && onEdit && (
        <TrustSealBadge
          variant={t.status === 'pending' ? 'pending' : 'verified'}
          model={t.source.model}
          confidence={t.source.confidence}
          stampIn={justConfirmed}
          onEdit={onEdit}
        />
      )}
      {!ai && (
        <p className="flex flex-wrap items-baseline gap-x-2 font-semibold text-ink-line">
          {src}
          <span className="text-ink-line opacity-70">— no AI involved in this entry</span>
        </p>
      )}

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="flex flex-col gap-0.5">
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            When
          </dt>
          <dd className="text-ink-line">{formatDateTime(t.occurred_at)}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            Amount
          </dt>
          <dd>
            <AmountText value={t.amount_pkr} tone={toneForKind(t.kind)} />
          </dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            Source
          </dt>
          <dd className="flex flex-col gap-0.5 text-ink-line">
            <span>{src}</span>
            <span className="font-mono text-xs opacity-80">
              {t.source.media_id ? `media ${t.source.media_id} · stored on server (never deleted)` : 'no media (manual entry)'}
            </span>
          </dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            Model
          </dt>
          <dd className="flex flex-col gap-1 text-ink-line">
            <span>{t.source.model ?? '— (manual entry)'}</span>
            {ai && (
              <span className="flex items-center gap-2">
                <span
                  className="inline-block h-2.5 w-24 overflow-hidden rounded-card border-2 border-ink-line bg-paper-raised"
                  aria-hidden="true"
                >
                  <span
                    className="block h-full bg-fill-gold"
                    style={{ width: `${Math.round((t.source.confidence ?? 0) * 100)}%` }}
                  />
                </span>
                <span>confidence {formatConfidence(t.source.confidence)}</span>
              </span>
            )}
          </dd>
        </div>
      </dl>

      {/* The original artifact — deepest drill-down level (design.md §4.5):
           tap a line → source → original voice note / receipt photo. */}
      <SourceMedia mediaId={t.source.media_id} sourceType={t.source.type} />

      {(t.source.raw_output as { transcript?: string } | null | undefined)?.transcript && (
        <div className="flex flex-col gap-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            What we heard
          </p>
          <p className="bizro-urdu rounded-card border-2 border-ink-line bg-paper-raised px-3 py-2 text-ink-line" lang="ur">
            {(t.source.raw_output as { transcript?: string }).transcript}
          </p>
        </div>
      )}

      {t.item_lines.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            Items read from receipt
          </p>
          <table className="w-full border-collapse text-ink-line">
            <thead>
              <tr className="bizro-rule-h text-left text-xs uppercase tracking-wide opacity-70">
                <th className="py-1 pr-2 font-semibold">Item</th>
                <th className="py-1 pr-2 font-semibold">Qty</th>
                <th className="py-1 pr-2 font-semibold">Unit price</th>
                <th className="py-1 text-right font-semibold">Line total</th>
              </tr>
            </thead>
            <tbody>
              {t.item_lines.map((line, i) => (
                <tr key={i} className="bizro-rule-h">
                  <td className="py-1.5 pr-2">{line.item}</td>
                  <td className="py-1.5 pr-2">
                    {line.qty} {line.unit}
                  </td>
                  <td className="py-1.5 pr-2">{formatPkr(line.unit_price)}</td>
                  <td className="py-1.5 text-right font-numerals font-semibold">
                    {formatPkr(line.line_total)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {t.confirmation_ur && (
        <div className="flex flex-col gap-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            WhatsApp confirmation
          </p>
          <p className="bizro-urdu rounded-card border-2 border-ink-line bg-paper-raised px-3 py-2 text-ink-line" lang="ur">
            {t.confirmation_ur}
          </p>
        </div>
      )}

      {t.status === 'pending' && onConfirm && (
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onConfirm}>
            Confirm this entry
          </Button>
          <p className="text-xs text-ink-line opacity-75">
            Low-confidence entries stay pending until you confirm them.
          </p>
        </div>
      )}
    </div>
  );
}
