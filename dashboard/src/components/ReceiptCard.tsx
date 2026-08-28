/* ReceiptCard — design.md §4.4: cream card, thin rule-line border on all four sides,
   amount in slab numerals. The torn/perforated edge is RESERVED for the WhatsApp
   invoice image itself (D3-3 ruling; DA-UI review) — dashboard cards never use it.
   NO box-shadow (elevation rule: rule-lines read as "register"). */

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
      <div className="rounded-card border border-rule-line bg-paper-raised px-4 py-4 sm:px-5">
        <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="flex flex-wrap items-baseline gap-x-2">
            <T
              en={title}
              ur={titleUr}
              className="font-numerals text-lg font-semibold text-ink-black"
              urClassName="text-base font-semibold text-ink-black"
            />
          </h2>
          {meta && <p className="text-xs text-ink-black opacity-75">{meta}</p>}
        </header>
        {children}
      </div>
    </section>
  );
}
