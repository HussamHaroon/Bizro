/* Bizro icon set — design.md §4.3: rounded, single-weight, FILLED (outline disappears
   for weaker near-vision). Every icon MUST be paired with a word at its usage site
   (never icon-only navigation) — the components here are decorative by default
   (aria-hidden); the label carries the meaning.

   Form: a filled circular badge (currentColor) with the glyph knocked out in
   paper-cream — reads as a solid stamp at any size and keeps one visual weight
   across the set. Arrow direction encodes money direction:
     sale ↓ in · expense ↑ out · udhar_given → out · udhar_settlement ← in
   (design.md §4.7: color is never the only signal — direction + label + position
   always accompany red/teal). */

import type { ReactNode, SVGProps } from 'react';

export type IconProps = SVGProps<SVGSVGElement> & { className?: string };

function Badge({ children, className = '', ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-hidden="true"
      focusable="false"
      className={`inline-block shrink-0 ${className}`}
      {...rest}
    >
      <circle cx="12" cy="12" r="11" fill="currentColor" />
      {/* Glyph fill defaults to paper-cream (dark circle on light surface). On
          surfaces where currentColor is LIGHT (cream tab on the ink-green top
          bar), the cascade in index.css flips .bizro-badge-glyph to ink-green —
          presentation attributes lose to CSS, so no per-call-site props. */}
      <g fill="var(--bizro-paper-cream)" className="bizro-badge-glyph">
        {children}
      </g>
    </svg>
  );
}

/* ---- Money direction (kinds) ---------------------------------------------- */

/** Sale — cash IN. Pair with the word "Sale · فروخت". */
export function IconSale({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M10.6 6h2.8v6.1h2.2L12 16l-3.6-3.9h2.2z" />
      <rect x="7.5" y="17.2" width="9" height="1.8" rx="0.9" />
    </Badge>
  );
}

/** Expense — cash OUT (gone). Pair with "Expense · خرچ". */
export function IconExpense({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M13.4 17.5h-2.8v-6.1H8.4L12 7.6l3.6 3.8h-2.2z" />
      <rect x="7.5" y="5" width="9" height="1.8" rx="0.9" />
    </Badge>
  );
}

/** Udhar given — credit OUT to a customer (they owe it back). Pair with "Udhar · ادھار". */
export function IconUdharGiven({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M6.5 10.6v2.8h6.1v2.2L16 12l-3.4-3.6v2.2z" />
      <rect x="17.2" y="7.5" width="1.8" height="9" rx="0.9" />
    </Badge>
  );
}

/** Udhar settlement — money back IN. Pair with "Repaid · وصولی". */
export function IconUdharSettled({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M17.5 13.4v-2.8h-6.1V8.4L8 12l3.4 3.6v-2.2z" />
      <rect x="5" y="7.5" width="1.8" height="9" rx="0.9" />
    </Badge>
  );
}

/* ---- Sources ---------------------------------------------------------------- */

/** Voice note source. Pair with "Voice · آواز". */
export function IconVoice({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <rect x="9.75" y="5.25" width="4.5" height="7.5" rx="2.25" />
      <path d="M8 11.5a4 4 0 0 0 8 0h-1.5a2.5 2.5 0 0 1-5 0z" />
      <rect x="11.1" y="15.2" width="1.8" height="3.3" rx="0.9" />
    </Badge>
  );
}

/** Receipt photo source. Pair with "Photo · تصویر". */
export function IconPhoto({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M9 5.25h6a1 1 0 0 1 1 1V8h2.25a1 1 0 0 1 1 1v8.75a1 1 0 0 1-1 1H5.75a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1H8V6.25a1 1 0 0 1 1-1z" />
      <circle cx="12" cy="13" r="2.9" fill="currentColor" />
    </Badge>
  );
}

/** Manual entry. Pair with "Manual · دستی". */
export function IconManual({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M7.2 16.8v-2.3l6.9-6.9 2.3 2.3-6.9 6.9z" />
      <rect x="15.2" y="6.4" width="2.6" height="2.2" rx="0.5" transform="rotate(45 16.5 7.5)" />
    </Badge>
  );
}

/* ---- States ------------------------------------------------------------------ */

/** Confirmed / verified check. Pair with "Verified · تصدیق شدہ". */
export function IconCheck({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M10.3 15.6 6.7 12l1.3-1.35 2.3 2.3 5.7-5.7L17.3 8.6z" />
    </Badge>
  );
}

/** Awaiting merchant confirmation. Pair with "Confirm pending · تصدیق باقی". */
export function IconPending({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M7.6 6.2h8.8L12 11.4z" />
      <path d="M7.6 17.8h8.8L12 12.6z" />
    </Badge>
  );
}

/** Merchant corrected an entry. Pair with "Edited · ترمیم شدہ". */
export function IconEdited({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M14.9 6.5l2.6 2.6-7.4 7.4-3.1.5.5-3.1z" />
      <rect x="16.2" y="5.1" width="2.9" height="2.4" rx="0.6" transform="rotate(45 17.6 6.3)" />
    </Badge>
  );
}

/** Rejected entry. Pair with "Rejected · مسترد". */
export function IconRejected({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M8.4 6.8 12 10.4l3.6-3.6 1.6 1.6-3.6 3.6 3.6 3.6-1.6 1.6-3.6-3.6-3.6 3.6-1.6-1.6 3.6-3.6-3.6-3.6z" />
    </Badge>
  );
}

/** Flag / warning on an entry. Pair with the flag's word label. */
export function IconFlag({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M11 5.4h6.2l-1.7 2.8 1.7 2.8H12.6v7.6H11z" />
      <rect x="7.6" y="5.4" width="1.9" height="13.2" rx="0.9" />
    </Badge>
  );
}

/* ---- Feature glyphs ------------------------------------------------------------ */

/** Udhar Radar widget. Pair with "Udhar Radar · ادھار راڈار". */
export function IconRadar({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path
        d="M12 11a1.6 1.6 0 1 1 0 3.2A1.6 1.6 0 0 1 12 11zm3.9-2.9a5.5 5.5 0 0 1 0 7.8l-1.15-1.15a3.9 3.9 0 0 0 0-5.5zm-7.8 0 1.15 1.15a3.9 3.9 0 0 0 0 5.5L6.1 15.9a5.5 5.5 0 0 1 0-7.8zm10.2-2.4a8.9 8.9 0 0 1 0 12.6l-1.15-1.15a7.3 7.3 0 0 0 0-10.3zm-12.6 0 1.15 1.15a7.3 7.3 0 0 0 0 10.3L4.7 15.3a8.9 8.9 0 0 1 0-12.6z"
        fillRule="evenodd"
      />
    </Badge>
  );
}

/** Savings streak flame (D3-3). Pair with the week-streak words, e.g.
    "3 week streak · ہفتوں کا سلسلہ". */
export function IconStreak({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      {/* flame teardrop, hollowed like the camera-lens cut in IconPhoto */}
      <path d="M12 4.8c3 3.1 4.5 5.6 4.5 8.3a4.5 4.5 0 0 1-9 0C7.5 10.4 9 7.9 12 4.8z" />
      <circle cx="12" cy="14.4" r="2.1" fill="currentColor" />
    </Badge>
  );
}

/** Credit report document. Pair with "Report · رپورٹ". */
export function IconReport({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M8 4.8h5.2L17.2 9v10.2H8z" />
      <g fill="currentColor">
        <rect x="9.6" y="9.4" width="6" height="1.2" rx="0.6" />
        <rect x="9.6" y="12" width="6" height="1.2" rx="0.6" />
        <rect x="9.6" y="14.6" width="4" height="1.2" rx="0.6" />
      </g>
    </Badge>
  );
}

/** Customer / counterparty. Pair with the customer's name. */
export function IconCustomer({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <circle cx="12" cy="8.6" r="2.7" />
      <path d="M7.1 17.9a4.9 4.9 0 0 1 9.8 0z" />
    </Badge>
  );
}

/** Ledger book (screen identity). Pair with "Ledger · کھاتہ". */
export function IconLedger({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M6.8 5h10.4v14H6.8z" />
      <g fill="currentColor">
        <rect x="8.4" y="7.2" width="7.2" height="1.2" rx="0.6" />
        <rect x="8.4" y="9.8" width="7.2" height="1.2" rx="0.6" />
        <rect x="8.4" y="12.4" width="4.8" height="1.2" rx="0.6" />
      </g>
    </Badge>
  );
}

/** Previous / next chevrons (month navigation, paired with month names). */
export function IconChevronLeft({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M13.9 6.4 15 7.5l-4.5 4.5 4.5 4.5-1.1 1.1-5.6-5.6z" />
    </Badge>
  );
}
export function IconChevronRight({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M10.1 6.4 9 7.5l4.5 4.5L9 16.5l1.1 1.1 5.6-5.6z" />
    </Badge>
  );
}

/** Edit affordance (always visible on AI entries). Pair with "Edit if wrong · غلط ہو تو بدلیں". */
export function IconEdit({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M7.2 16.8v-2.3l6.9-6.9 2.3 2.3-6.9 6.9zm8.9-9.9 1.1 1.1 1.15-1.15a.8.8 0 0 0 0-1.1l-.1-.1a.8.8 0 0 0-1.1 0z" />
    </Badge>
  );
}

/** Source drill-down chevron (details). */
export function IconChevronDown({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <path d="M6.4 9.9 7.5 8.8l4.5 4.5 4.5-4.5 1.1 1.1-5.6 5.6z" />
    </Badge>
  );
}

/* ---- Language modes (D1-1a segmented control) ------------------------------ */
/* Letter-glyph badges: the word on the segment carries the meaning; the icon
   keeps the filled-badge weight consistent with the rest of the set. */

/** Urdu mode. Pair with the word "اردو". */
export function IconLangUr({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <text x="12" y="16.5" textAnchor="middle" fontSize="13" fontWeight="700">
        ا
      </text>
    </Badge>
  );
}

/** English mode. Pair with the word "English". */
export function IconLangEn({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <text x="12" y="16.5" textAnchor="middle" fontSize="12" fontWeight="700">
        A
      </text>
    </Badge>
  );
}

/** Mixed mode — both scripts side by side. Pair with the word "Mixed". */
export function IconLangMixed({ className, ...rest }: IconProps) {
  return (
    <Badge className={className} {...rest}>
      <text x="7.6" y="16" textAnchor="middle" fontSize="10" fontWeight="700">
        ا
      </text>
      <text x="15.6" y="16" textAnchor="middle" fontSize="10" fontWeight="700">
        A
      </text>
    </Badge>
  );
}

/* ---- Non-badge glyphs (inline inside filled buttons, currentColor) ---------- */

/** Print / PDF. Solid currentColor — sits inside the ink-green primary button
    where the filled-badge treatment would vanish. Pair with a word. */
export function IconPrint({ className, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-hidden="true"
      focusable="false"
      className={`inline-block shrink-0 ${className}`}
      {...rest}
    >
      <path
        fillRule="evenodd"
        d="M6.8 8.6V4.6h10.4v4h2a1.5 1.5 0 0 1 1.5 1.5v4.4a1.5 1.5 0 0 1-1.5 1.5h-2.3v3.4H7.1v-3.4H4.8a1.5 1.5 0 0 1-1.5-1.5v-4.4A1.5 1.5 0 0 1 4.8 8.6zm3.2 2a1 1 0 0 0-1 1v2.2h6V11.6a1 1 0 0 0-1-1z"
      />
    </svg>
  );
}
