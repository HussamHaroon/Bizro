/* EmptyState — friendly zero-data state. Icon + word + one short line +
   optional action. No shadows, rule-line card, cream surface (elevation rule).
   English-only (owner directive 2026-09-04): the *Ur props are accepted from
   older call sites but never rendered. */

import type { ReactNode } from 'react';
import { Button } from './Button';

export interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  /** Ignored — the dashboard renders English only. */
  titleUr?: string;
  hint?: string;
  /** Ignored — the dashboard renders English only. */
  hintUr?: string;
  actionLabel?: string;
  /** Ignored — the dashboard renders English only. */
  actionLabelUr?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  hint,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="bizro-card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="text-ink-green">{icon}</span>
      <p className="flex flex-wrap items-baseline justify-center gap-x-2">
        <span className="font-numerals text-lg font-semibold text-ink-line">{title}</span>
      </p>
      {hint && (
        <p className="max-w-xs text-sm text-ink-line opacity-80">{hint}</p>
      )}
      {actionLabel && onAction && (
        <Button onClick={onAction} className="mt-2">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
