/* ReceiptCard — design.md §4.4 + D4-1: raised paper card, 3px ink-line border,
   hard-md shadow, 2px radius. The torn/perforated edge stays RESERVED for the
   WhatsApp invoice image itself (D3-3 ruling; DA-UI review) — dashboard cards
   never use it, and no gradients (D4-1 kills the D3-4 card gradient). */

import type { ReactNode } from 'react';
import { T } from '../i18n';

export interface ReceiptCardProps {
  title: string;
  titleUr: string;
  meta?: string;
  children: ReactNode;
  className?: string;
}

export function ReceiptCard({ title, titleUr, meta, children, className = '' }: ReceiptCardProps) {
  return (
    <section className={`w-full ${className}`}>
      <div className="bizro-card px-4 py-4 sm:px-5">
        <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="flex flex-wrap items-baseline gap-x-2">
            <T
              en={title}
              ur={titleUr}
              className="font-numerals text-lg font-semibold text-ink-line"
              urClassName="text-base font-semibold text-ink-line"
            />
          </h2>
          {meta && <p className="text-xs text-ink-line opacity-75">{meta}</p>}
        </header>
        {children}
      </div>
    </section>
  );
}
