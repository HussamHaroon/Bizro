/* App shell — two demo surfaces (design.md §6 screens 3–4) + the /dev/components
   gallery. Nav links are icon+word pairs (design.md §4.3: never icon-only); the
   app name is the one Nastaliq display moment allowed in dense UI (§4.2). */

import { BrowserRouter, Link, NavLink, Route, Routes, Navigate } from 'react-router-dom';
import { MockBanner } from './components/MockBanner';
import { IconLedger, IconReport } from './components/icons';
import { MonthlyLedgerScreen } from './screens/MonthlyLedgerScreen';
import { CreditReadinessScreen } from './screens/CreditReadinessScreen';
import { ComponentsGallery } from './dev/ComponentsGallery';

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `inline-flex min-h-touch items-center gap-2 rounded-button px-3 text-sm font-semibold transition-colors duration-200 ease-out ${
      isActive
        ? 'bg-ink-green text-paper-cream'
        : 'text-ink-black hover:bg-paper-cream'
    }`;
  return (
    <nav
      aria-label="Screens · اسکرین"
      className="border-b border-rule-line bg-paper-raised"
    >
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
        <Link
          to="/ledger"
          className="flex items-baseline gap-2 py-1"
          aria-label="Bizro home — ledger"
        >
          <span className="font-numerals text-xl font-bold tracking-wide text-ink-green">Bizro</span>
          <span className="bizro-display-ur text-xl leading-none text-ink-green" lang="ur">
            بزرو
          </span>
        </Link>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          <NavLink to="/ledger" className={linkClass}>
            <IconLedger className="h-6 w-6" />
            Ledger <span className="bizro-urdu font-normal" lang="ur">کھاتہ</span>
          </NavLink>
          <NavLink to="/credit" className={linkClass}>
            <IconReport className="h-6 w-6" />
            Credit <span className="bizro-urdu font-normal" lang="ur">کریڈٹ</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-dvh flex-col bg-paper-cream">
        <MockBanner />
        <Nav />
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/ledger" replace />} />
            <Route path="/ledger" element={<MonthlyLedgerScreen />} />
            <Route path="/credit" element={<CreditReadinessScreen />} />
            <Route path="/dev/components" element={<ComponentsGallery />} />
          </Routes>
        </main>
        <footer className="border-t border-rule-line px-4 py-3">
          <p className="mx-auto max-w-4xl text-xs text-ink-black opacity-70">
            Bizro control room · Khata Modern ·{' '}
            <Link to="/dev/components" className="font-semibold underline">
              Component gallery
            </Link>
          </p>
        </footer>
      </div>
    </BrowserRouter>
  );
}
