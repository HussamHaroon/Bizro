/* TrustSealBadge — design.md §4.4 + §7.2 + D4-1: the trust marker is now a
   rubber STAMP — 2px dashed ink border, uppercase bold text, rotate(-4deg),
   green ink when verified / red ink while pending. The existing stamp-in
   "thud" animation (300ms ease-out, the ONE animation, design.md §4.6) now
   lands an actual stamp, so it stays untouched. Load-bearing for the
   credit-readiness audit trail, not decoration — `onEdit` is REQUIRED:
   callers cannot render a seal without the correction path.

   Variants differ by WORD + INK color + GLYPH (design.md §4.7 — color never
   the only signal):
     verified — green ink "AI-PARSED · CONFIRMED" with a check
     pending  — red ink "NEEDS YOUR CHECK" with an hourglass

   SealMark is the dense-row form: a small upright dashed stamp glyph (square,
   never rotated — the badge is the ONE rotated sticker per screen, D4-1). */

import type { MouseEvent } from 'react';
import { formatConfidence } from '../lib/format';
import { IconEdit } from './icons';
import { T, useT } from '../i18n';

export type SealVariant = 'verified' | 'pending';

export interface TrustSealBadgeProps {
  variant?: SealVariant;
  /** Stamp size: sm rows · md callouts · lg screen verdicts. */
  size?: 'sm' | 'md' | 'lg';
  /** Model that parsed the entry (schema.md §1 source.model), e.g. qwen3.5-omni-plus. */
  model: string | null;
  /** schema.md §1 source.confidence — null only for manual entries (no seal). */
  confidence: number | null;
  /** Fire the 300ms stamp "thud" (mount it when an entry just got verified). */
  stampIn?: boolean;
  /** REQUIRED — always-visible edit affordance (design.md §7.2 audit trail). */
  onEdit: (e: MouseEvent<HTMLButtonElement>) => void;
  editLabel?: string;
  editLabelUr?: string;
  className?: string;
}

const STAMP_TEXT: Record<SealVariant, { ink: string }> = {
  verified: { ink: 'text-ink-green' },
  pending: { ink: 'text-ledger-red' },
};

const STAMP_TEXT_CLASS: Record<NonNullable<TrustSealBadgeProps['size']>, string> = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
};

function StampGlyph({ variant, px }: { variant: SealVariant; px: number }) {
  const vb = 48;
  return (
    <svg width={px} height={px} viewBox={`0 0 ${vb} ${vb}`} aria-hidden="true" focusable="false">
      {/* upright dashed stamp box — the mark reads "stamped" even at row size */}
      <rect
        x="3"
        y="3"
        width={vb - 6}
        height={vb - 6}
        fill="none"
        stroke="var(--bizro-ink-line)"
        strokeWidth="3"
        strokeDasharray="5 4"
      />
      {variant === 'verified' ? (
        <path
          d="M14 24.5 21 31.5 34 17"
          fill="none"
          stroke="var(--bizro-ink-green)"
          strokeWidth="5"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
      ) : (
        /* hourglass — waiting on the merchant's confirmation */
        <path d="M17 14h14L24 22.5zM17 34h14L24 25.5z" fill="var(--bizro-ledger-red)" />
      )}
    </svg>
  );
}

export function TrustSealBadge({
  variant = 'verified',
  size = 'sm',
  model,
  confidence,
  stampIn = false,
  onEdit,
  editLabel,
  editLabelUr,
  className = '',
}: TrustSealBadgeProps) {
  const { pick } = useT();
  const spec = STAMP_TEXT[variant];
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-3 gap-y-2 ${className}`}>
      {/* The rubber stamp — the ONE rotated sticker on any screen (D4-1). */}
      <span
        className={`bizro-stamp font-numerals ${spec.ink} ${STAMP_TEXT_CLASS[size]} ${stampIn ? 'bizro-stamp-in' : ''}`}
        title={pick('AI-parsed entry, merchant-confirmed', 'اے آئی سے درج، تاجر کی تصدیق شدہ')}
      >
        {variant === 'verified' ? (
          <T en="AI-parsed · confirmed" ur="اے آئی درج · تصدیق شدہ" />
        ) : (
          <T en="Needs your check" ur="تصدیق باقی" />
        )}
      </span>
      <span className={`flex flex-col ${STAMP_TEXT_CLASS[size]} leading-tight`}>
        <span className="text-ink-line opacity-75">
          {variant === 'verified' ? (
            <>
              {model ?? 'unknown model'} · confidence {formatConfidence(confidence)}
            </>
          ) : (
            <>
              {model ?? 'unknown model'} · confidence {formatConfidence(confidence)} (below 75%)
            </>
          )}
        </span>
      </span>
      {/* ALWAYS visible — one tap from any AI entry to the correction path. */}
      <button
        type="button"
        onClick={onEdit}
        className="bizro-btn-press inline-flex min-h-touch items-center gap-2 rounded-button border-[3px] border-ink-line bg-paper-raised px-3 text-sm font-semibold text-ink-line"
      >
        <IconEdit className="h-[18px] w-[18px] text-ink-green" />
        <T en={editLabel ?? 'Edit if wrong'} ur={editLabelUr ?? 'غلط ہو تو بدلیں'} />
      </button>
    </span>
  );
}

/** The stamp mark alone (no microcopy) — for dense rows; still pair with a word.
    Upright by design: the rotated badge is reserved for the drill-down seal. */
export function SealMark({
  variant = 'verified',
  stampIn = false,
  size = 'sm',
  className = '',
}: {
  variant?: SealVariant;
  stampIn?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const px = { sm: 20, md: 28, lg: 44 }[size];
  return (
    <span className={`inline-block ${stampIn ? 'bizro-stamp-in' : ''} ${className}`}>
      <StampGlyph variant={variant} px={px} />
    </span>
  );
}
