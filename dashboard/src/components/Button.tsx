/* Button — design.md §4.4: solid ink-green, 48px+ touch target, ONE primary action
   per screen (enforced at usage sites, not by the API). Secondary = quiet cream
   surface + rule-line border. Danger-quiet = red text for destructive corrections.
   D3-4: .bizro-btn-lift adds the subtle -1px hover rise + soft shadow (the only
   motion tokens: 200ms fast, flattened under prefers-reduced-motion). */

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
    'bg-ink-green text-paper-cream border border-ink-green hover:bg-ink-green-hover hover:border-ink-green-hover active:bg-ink-green disabled:bg-ink-green-disabled disabled:border-ink-green-disabled',
  secondary:
    'bg-paper-raised text-ink-black border border-rule-line hover:bg-paper-cream disabled:text-ink-green-disabled',
  danger:
    'bg-paper-raised text-ledger-red border border-rule-line hover:bg-paper-cream disabled:text-ink-green-disabled',
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
      className={`bizro-btn-lift inline-flex min-h-touch items-center justify-center gap-2 rounded-button px-4 py-3 font-semibold disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
