/* App shell — two demo surfaces (design.md §6 screens 3–4) + the /dev/components
   gallery. D4-1 "stamped-ledger" restyle: the sticky top bar is PAPER with a 3px
   ink-line bottom rule and a 6px seal-gold accent segment; the brand wordmark is
   slab bold ink; screen tabs and the language control are chunky bordered
   segments (active = green-fill with paper text); nav links stay icon+word
   pairs (§4.3: never icon-only); the Nastaliq بزرو is the one display moment
   allowed in dense UI.

   D3 MOBILE-FIRST PASS (owner priority: "the most important part is the UI and
   also ui for the mobile phones"): below md the screen tabs move out of the top
   bar into a fixed BOTTOM tab bar (thumb-reachable, 48px+ targets, paper surface
   + 3px ink-line top border, safe-area inset; active tab = green-fill raised
   chip with a hard shadow). The top bar keeps brand + language control only.
   No hamburger menus (bizro-ui-design anti-pattern) — the same two icon+word
   tabs stay one tap away at every width. Desktop (≥md) keeps top tabs and never
   shows the bottom bar. */

import { BrowserRouter, Link, NavLink, Route, Routes, Navigate } from 'react-router-dom';
import { MerchantPicker } from './components/MerchantPicker';
import { MockBanner } from './components/MockBanner';
import { IconLedger, IconReport } from './components/icons';
import { LanguageControl } from './i18n/LanguageControl';
import { T, useT } from './i18n';
import { MonthlyLedgerScreen } from './screens/MonthlyLedgerScreen';
import { CreditReadinessScreen } from './screens/CreditReadinessScreen';
import { ComponentsGallery } from './dev/ComponentsGallery';
import { useMerchant } from './merchant';

const SCREEN_TABS = [
  { to: '/ledger', icon: IconLedger, en: 'Ledger', ur: 'کھاتہ' },
  { to: '/credit', icon: IconReport, en: 'Credit', ur: 'کریڈٹ' },
] as const;

function TopBar() {
  const { pick } = useT();
  /* D4r fix 3 (desktop de-busying): tabs / merchant select / language control
     all sit at ONE height — 48px target + 2px border = 52px — and the bar's
     vertical padding is down (py-2), so the header stops being the tallest
     thing on the screen. Brand stays left; picker + language group right. */
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `bizro-topbar-tab inline-flex min-h-touch items-center gap-2 rounded-chip border-2 px-3 text-sm font-semibold transition-colors duration-200 ease-out ${
      isActive
        ? 'border-ink-line bg-fill-green text-paper shadow-hard-sm'
        : 'border-transparent text-ink-line hover:border-ink-line hover:bg-paper-raised'
    }`;
  return (
    <header
      className="bizro-no-print sticky top-0 z-40 border-b-[3px] border-ink-line bg-paper text-ink-line"
    >
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
        <Link
          to="/ledger"
          className="flex items-center gap-2.5 py-1"
          aria-label={pick('Bizro home — ledger', 'بزرو — کھاتہ')}
        >
          {/* Nastaliq display moment — line-height 2 (not leading-none) so the
              tall script never clips inside the slimmer bar (D4r fix 4a). */}
          <span className="bizro-display-ur text-2xl leading-[2] text-ink-green" lang="ur">
            بزرو
          </span>
          <span className="font-numerals text-2xl font-bold tracking-wide text-ink-line">
            Bizro
          </span>
        </Link>
        {/* Desktop tabs — on phones these move to the bottom tab bar below. */}
        <nav
          aria-label={pick('Screens', 'اسکرین')}
          className="ml-2 hidden flex-wrap items-center gap-1.5 md:flex"
        >
          {SCREEN_TABS.map(({ to, icon: Icon, en, ur }) => (
            <NavLink key={to} to={to} className={tabClass}>
              <Icon className="h-6 w-6" />
              <T en={en} ur={ur} />
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {/* Merchant switcher (D3-2) — desktop top bar, compact select beside
              the language control at the same 52px height; hidden at ≤1
              merchant. Phones get it inside the bottom nav sheet instead. */}
          <MerchantPicker className="hidden md:inline-flex" selectClassName="max-w-36" compact />
          <LanguageControl />
        </div>
      </div>
      {/* 6px seal-gold accent segment riding the bottom ink rule (D4-1) */}
      <span
        aria-hidden="true"
        className="absolute bottom-[-4px] left-4 h-[6px] w-24 bg-seal-gold sm:left-6"
      />
    </header>
  );
}

/** Fixed bottom tab bar — phones/tablet-portrait only (<md). Thumb-reachable
    icon+word pairs (§4.7), 48px+ targets, paper surface + 3px ink-line top
    border, active tab = green-fill raised chip with a hard shadow, notch-safe
    padding. Hidden on desktop and in print. */
function BottomNav() {
  const { pick } = useT();
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `bizro-topbar-tab flex min-h-touch flex-1 flex-col items-center justify-center gap-0.5 rounded-chip border-[3px] px-2 py-1 text-xs font-semibold transition-colors duration-200 ease-out ${
      isActive
        ? 'border-ink-line bg-fill-green text-paper shadow-hard-sm'
        : 'border-transparent text-ink-line'
    }`;
  return (
    <nav
      aria-label={pick('Screens', 'اسکرین')}
      className="bizro-no-print bizro-safe-b fixed inset-x-0 bottom-0 z-40 border-t-[3px] border-ink-line bg-paper md:hidden"
    >
      {/* Merchant switcher sits ABOVE the tabs on mobile (D3-2) — 2px ink rule
          separated, full-width target. Renders nothing at ≤1 merchant. */}
      <div className="border-b-2 border-ink-line px-3 py-2">
        <MerchantPicker className="w-full" selectClassName="max-w-none" />
      </div>
      <div className="mx-auto flex w-full max-w-md items-stretch gap-1 px-2 py-1">
        {SCREEN_TABS.map(({ to, icon: Icon, en, ur }) => (
          <NavLink key={to} to={to} className={tabClass}>
            <Icon className="h-7 w-7" aria-hidden="true" />
            <T en={en} ur={ur} />
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export function App() {
  // The bottom sheet grows by one picker row on multi-merchant servers — the
  // reserved padding below grows with it (full class strings so Tailwind emits both).
  const { merchants } = useMerchant();
  const reserveClass =
    merchants.length > 1
      ? 'pb-[calc(140px+env(safe-area-inset-bottom))] md:pb-0'
      : 'pb-[calc(76px+env(safe-area-inset-bottom))] md:pb-0';
  return (
    <BrowserRouter>
      {/* pb reserves the fixed bottom tab bar's height + notch inset on <md so
          the footer/ledger tail is never covered. */}
      <div className={`flex min-h-dvh flex-col bg-paper ${reserveClass}`}>
        <MockBanner />
        <TopBar />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4.5 py-7 sm:px-6 sm:py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/ledger" replace />} />
            <Route path="/ledger" element={<MonthlyLedgerScreen />} />
            <Route path="/credit" element={<CreditReadinessScreen />} />
            <Route path="/dev/components" element={<ComponentsGallery />} />
          </Routes>
        </main>
        <footer className="bizro-no-print border-t border-gridline px-4 py-3">
          <p className="mx-auto max-w-6xl text-xs text-ink-line opacity-70">
            <T en="Bizro control room · stamped-ledger edition" ur="بزرو کنٹرول روم" /> ·{' '}
            <Link to="/dev/components" className="font-semibold underline">
              <T en="Component gallery" ur="اجزاء کی نمائش" />
            </Link>
          </p>
        </footer>
        <BottomNav />
      </div>
    </BrowserRouter>
  );
}
