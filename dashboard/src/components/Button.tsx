/* Button — design.md §4.4 + D4-1: solid fills + 3px ink-line border +
   shadow-hard-sm (via .bizro-btn-press); ACTIVE = translate(2px,2px) +
   shadow-none — the tactile "press" onto the page. 48px+ touch target, ONE
   primary action per screen (enforced at usage sites, not by the API).
   Secondary = quiet raised surface + ink text. Danger-quiet = red text for
   destructive corrections. */

import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Icon + word pair (design.md §4.7). Icon alone is never enough. */
  icon?: ReactNode;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'border-ink-line bg-fill-green text-paper hover:bg-ink-green-hover disabled:bg-ink-green-disabled disabled:text-paper',
  secondary:
    'border-ink-line bg-paper-raised text-ink-line hover:bg-paper disabled:border-ink-green-disabled disabled:text-ink-green-disabled',
  danger:
    'border-ink-line bg-paper-raised text-ledger-red hover:bg-paper disabled:border-ink-green-disabled disabled:text-ink-green-disabled',
};

export function Button({
  variant = 'primary',
  icon,
  children,
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`bizro-btn-press inline-flex min-h-touch items-center justify-center gap-2 rounded-button border-[3px] px-4 py-3 font-semibold disabled:cursor-not-allowed disabled:shadow-none ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
