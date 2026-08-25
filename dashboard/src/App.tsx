/* App shell — two demo surfaces (design.md §6 screens 3–4) + the /dev/components
   gallery. D1-1 visual elevation: a sticky deep ink-green top bar (cream text,
   Nastaliq brand word + slab "Bizro", tab switcher, language segmented control,
   seal-gold bottom rule) replaces the old paper band — this single move kills the
   "beige website" first impression. Nav links are icon+word pairs (§4.3: never
   icon-only); the Nastaliq بزرو is the one display moment allowed in dense UI. */

import { BrowserRouter, Link, NavLink, Route, Routes, Navigate } from 'react-router-dom';
import { MockBanner } from './components/MockBanner';
import { IconLedger, IconReport } from './components/icons';
import { LanguageControl } from './i18n/LanguageControl';
import { T, useT } from './i18n';
import { MonthlyLedgerScreen } from './screens/MonthlyLedgerScreen';
import { CreditReadinessScreen } from './screens/CreditReadinessScreen';
import { ComponentsGallery } from './dev/ComponentsGallery';

function TopBar() {
  const { pick } = useT();
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `inline-flex min-h-touch items-center gap-2 rounded-button px-3 text-sm font-semibold transition-colors duration-200 ease-out ${
      isActive
        ? 'bg-paper-cream text-ink-green'
        : 'text-paper-cream hover:bg-ink-green-hover'
    }`;
  return (
    <header
      className="sticky top-0 z-40 border-b-2 border-seal-gold bg-ink-green text-paper-cream shadow-card"
    >
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
        <Link
          to="/ledger"
          className="flex items-center gap-2.5 py-1"
          aria-label={pick('Bizro home — ledger', 'بزرو — کھاتہ')}
        >
          <span className="bizro-display-ur text-2xl leading-none text-paper-cream" lang="ur">
            بزرو
          </span>
          <span className="font-numerals text-xl font-bold tracking-wide text-paper-cream">
            Bizro
          </span>
        </Link>
        <nav aria-label={pick('Screens', 'اسکرین')} className="ml-2 flex flex-wrap items-center gap-1">
          <NavLink to="/ledger" className={tabClass}>
            <IconLedger className="h-6 w-6" />
            <T en="Ledger" ur="کھاتہ" />
          </NavLink>
          <NavLink to="/credit" className={tabClass}>
            <IconReport className="h-6 w-6" />
            <T en="Credit" ur="کریڈٹ" />
          </NavLink>
        </nav>
        <div className="ml-auto">
          <LanguageControl onDark />
        </div>
      </div>
    </header>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-dvh flex-col bg-paper-cream">
        <MockBanner />
        <TopBar />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/ledger" replace />} />
            <Route path="/ledger" element={<MonthlyLedgerScreen />} />
            <Route path="/credit" element={<CreditReadinessScreen />} />
            <Route path="/dev/components" element={<ComponentsGallery />} />
          </Routes>
        </main>
        <footer className="border-t border-rule-line px-4 py-3">
          <p className="mx-auto max-w-6xl text-xs text-ink-black opacity-70">
            <T en="Bizro control room · Khata Modern" ur="بزرو کنٹرول روم" /> ·{' '}
            <Link to="/dev/components" className="font-semibold underline">
              <T en="Component gallery" ur="اجزاء کی نمائش" />
            </Link>
          </p>
        </footer>
      </div>
    </BrowserRouter>
  );
}
