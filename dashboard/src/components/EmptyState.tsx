/* EmptyState — friendly zero-data state. Icon + word + one short line (EN + UR) +
   optional action. No shadows, rule-line card, cream surface (elevation rule). */

import type { ReactNode } from 'react';
import { Button } from './Button';

export interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  titleUr: string;
  hint?: string;
  actionLabel?: string;
  actionLabelUr?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  titleUr,
  hint,
  actionLabel,
  actionLabelUr,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="bizro-card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="text-ink-green">{icon}</span>
      <p className="flex flex-wrap items-baseline justify-center gap-x-2">
        <span className="font-numerals text-lg font-semibold text-ink-black">{title}</span>
        <span className="bizro-urdu text-base text-ink-black" lang="ur">
          {titleUr}
        </span>
      </p>
      {hint && <p className="max-w-xs text-sm text-ink-black opacity-80">{hint}</p>}
      {actionLabel && onAction && (
        <Button onClick={onAction} className="mt-2">
          {actionLabel}
          {actionLabelUr && (
            <span className="bizro-urdu font-normal" lang="ur">
              {actionLabelUr}
            </span>
          )}
        </Button>
      )}
    </div>
  );
}
