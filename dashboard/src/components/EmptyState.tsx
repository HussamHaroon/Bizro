/* EmptyState — friendly zero-data state. Icon + word + one short line (EN + UR) +
   optional action. No shadows, rule-line card, cream surface (elevation rule). */

import type { ReactNode } from 'react';
import { Button } from './Button';
import { T } from '../i18n';

export interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  titleUr: string;
  hint?: string;
  hintUr?: string;
  actionLabel?: string;
  actionLabelUr?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  titleUr,
  hint,
  hintUr,
  actionLabel,
  actionLabelUr,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="bizro-card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="text-ink-green">{icon}</span>
      <p className="flex flex-wrap items-baseline justify-center gap-x-2">
        <T
          en={title}
          ur={titleUr}
          className="font-numerals text-lg font-semibold text-ink-line"
          urClassName="text-lg font-semibold text-ink-line"
        />
      </p>
      {hint && (
        <p className="max-w-xs text-sm text-ink-line opacity-80">
          {hintUr ? <T en={hint} ur={hintUr} /> : hint}
        </p>
      )}
      {actionLabel && onAction && (
        <Button onClick={onAction} className="mt-2">
          <T en={actionLabel} ur={actionLabelUr ?? actionLabel} />
        </Button>
      )}
    </div>
  );
}
