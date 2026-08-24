/* TrustSealBadge — design.md §4.4 + §7.2: a small circular gold stamp
   ("Alibaba Cloud AI Verified" microcopy) on any AI-parsed entry, with an
   ALWAYS-VISIBLE one-tap "edit if wrong" affordance. This is load-bearing for
   the credit-readiness audit trail, not decoration — so `onEdit` is REQUIRED:
   callers cannot render a seal without the correction path.

   Variants differ by SHAPE as well as color (design.md §4.7 — color never the
   only signal):
     verified — solid gold scalloped seal with an ink-black check (AA pair)
     pending  — hollow dashed circle with an hourglass ("not stamped yet")

   `stampIn` triggers the ONE animation worth budget (design.md §4.6): the seal
   "thud" — 300ms ease-out scale-and-settle via the .bizro-stamp-in token class.
*/

import type { MouseEvent } from 'react';
import { formatConfidence } from '../lib/format';
import { IconEdit } from './icons';

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

const SEAL_PX: Record<NonNullable<TrustSealBadgeProps['size']>, number> = { sm: 28, md: 40, lg: 64 };
const TEXT_CLASS: Record<NonNullable<TrustSealBadgeProps['size']>, string> = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
};

/** Notary-style scalloped seal edge — generated, not hand-drawn, so teeth stay
    even at every size. Q-curves bulge from the inner to outer radius. */
function scallopPath(cx: number, cy: number, rInner: number, rOuter: number, teeth: number): string {
  const p = (r: number, a: number) => `${(cx + r * Math.cos(a)).toFixed(2)} ${(cy + r * Math.sin(a)).toFixed(2)}`;
  let d = `M ${p(rInner, -Math.PI / 2)}`;
  for (let i = 0; i < teeth; i++) {
    const a0 = -Math.PI / 2 + (i / teeth) * Math.PI * 2;
    const a1 = -Math.PI / 2 + ((i + 1) / teeth) * Math.PI * 2;
    d += ` Q ${p(rOuter, (a0 + a1) / 2)} ${p(rInner, a1)}`;
  }
  return `${d} Z`;
}

function SealGlyph({ variant, px }: { variant: SealVariant; px: number }) {
  const vb = 48;
  if (variant === 'verified') {
    return (
      <svg width={px} height={px} viewBox={`0 0 ${vb} ${vb}`} aria-hidden="true" focusable="false">
        <path d={scallopPath(24, 24, 18.5, 23, 18)} fill="var(--bizro-seal-gold)" />
        <circle cx="24" cy="24" r="14.5" fill="none" stroke="var(--bizro-ink-black)" strokeWidth="1.4" />
        <path
          d="M18.4 24.6 22.6 28.8 29.8 20.6"
          fill="none"
          stroke="var(--bizro-ink-black)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg width={px} height={px} viewBox={`0 0 ${vb} ${vb}`} aria-hidden="true" focusable="false">
      <circle
        cx="24"
        cy="24"
        r="19"
        fill="var(--bizro-paper-cream-raised)"
        stroke="var(--bizro-ink-black)"
        strokeWidth="1.6"
        strokeDasharray="4.5 3.5"
      />
      {/* hourglass — waiting on the merchant's confirmation */}
      <path
        d="M18.5 15.5h11L24 22.6zM18.5 32.5h11L24 25.4z"
        fill="var(--bizro-ink-black)"
      />
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
  editLabel = 'Edit if wrong',
  editLabelUr = 'غلط ہو تو بدلیں',
  className = '',
}: TrustSealBadgeProps) {
  const px = SEAL_PX[size];
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-2 gap-y-1 ${className}`}>
      <span
        className={stampIn ? 'bizro-stamp-in' : undefined}
        title={variant === 'verified' ? 'AI-verified entry' : 'Waiting for confirmation'}
      >
        <SealGlyph variant={variant} px={px} />
      </span>
      <span className={`flex flex-col ${TEXT_CLASS[size]} leading-tight`}>
        <span className="font-semibold text-ink-black">
          {variant === 'verified' ? (
            <>
              AI-verified <span className="bizro-urdu font-normal" lang="ur">تصدیق شدہ</span>
            </>
          ) : (
            <>
              Needs your check <span className="bizro-urdu font-normal" lang="ur">تصدیق باقی</span>
            </>
          )}
        </span>
        <span className="text-ink-black opacity-75">
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
        className="inline-flex min-h-touch items-center gap-2 rounded-button border border-rule-line bg-paper-raised px-3 text-sm font-semibold text-ink-black transition-colors duration-200 ease-out hover:bg-paper-cream"
      >
        <IconEdit className="h-[18px] w-[18px] text-ink-green" />
        <span>{editLabel}</span>
        <span className="bizro-urdu font-normal" lang="ur">
          {editLabelUr}
        </span>
      </button>
    </span>
  );
}

/** The seal stamp alone (no microcopy) — for dense rows; still pair with a word. */
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
  return (
    <span className={`inline-block ${stampIn ? 'bizro-stamp-in' : ''} ${className}`}>
      <SealGlyph variant={variant} px={SEAL_PX[size]} />
    </span>
  );
}
