/* Committee Pack — /committee/:id. The PRINT artifact for the Mawakhat loan
   committee: one page, identity placeholders left honestly empty (they are
   captured ON the visit, not fabricated here), band + score, corroboration,
   top metrics, aging, flags, the ledger integrity statement, and the report's
   limitations.

   Print law (design.md §6 screen 4 + D4-1 ④): the app chrome is already
   .bizro-no-print; this screen adds its own action row to that set, flattens
   shadows via the global print block, and keeps every section
   break-inside:avoid so the pack paginates cleanly. Khata Modern tokens only —
   rule-lines never shadows on paper, icon+word everywhere, nothing color-only.

   Data: the same explicit-merchant fetchers as /officer. Any absent optional
   field (corroboration, aging, collection rate, limitations) simply leaves its
   line out — a pack must never invent a number. */

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { fetchLedgerVerify, fetchMerchantReport, fetchMerchantTransactions } from '../api/client';
import { deriveUdhar } from '../api/mockData';
import type { CreditReportPreview, LedgerVerifyResult, ReadinessLevel, Transaction } from '../types/schema';
import { OfficerAgingBars, WeeklyActivityBars, normalizeAging, normalizeWeekly, toPct } from '../components/OfficerPack';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealGauge } from '../components/SealGauge';
import { SealMark } from '../components/TrustSealBadge';
import {
  IconCustomer,
  IconFlag,
  IconPhoto,
  IconPrint,
  IconReport,
  IconRadar,
  IconUdharGiven,
} from '../components/icons';
import { formatPkr } from '../lib/format';
import { useMerchant } from '../merchant';

const READINESS_WORDS: Record<ReadinessLevel, string> = {
  ready: 'Loan-ready',
  almost: 'Almost ready',
  not_yet: 'Not yet ready',
};

/** Standing disclosures (schema.md §9) — used ONLY when the payload carries no
    `limitations` of its own, and labeled as the house note, not as data. */
const HOUSE_LIMITATIONS = [
  'Every input is merchant-volunteered; omission cannot be detected from ledger internals alone.',
  'Indicators in this pack are disclosures over recorded data — they assert nothing about intent and are not a trust score.',
];

export function CommitteePrintScreen() {
  const { id } = useParams<{ id: string }>();
  const { setMerchant } = useMerchant();
  const [report, setReport] = useState<CreditReportPreview | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [verify, setVerify] = useState<LedgerVerifyResult | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setReport(null);
    setTransactions(null);
    setVerify(null);
    setLoaded(false);
    // Committee navigation means the officer is working ON this merchant —
    // key the app to it so any screen they fall back to agrees.
    setMerchant(id);
    Promise.all([fetchMerchantReport(id), fetchMerchantTransactions(id), fetchLedgerVerify(id)])
      .then(([r, t, v]) => {
        if (!alive) return;
        setReport(r);
        setTransactions(t);
        setVerify(v);
        setLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, [id, setMerchant]);

  const udharOutstanding = useMemo(
    () => (transactions ? deriveUdhar(transactions).reduce((s, u) => s + u.outstanding_pkd, 0) : null),
    [transactions],
  );

  if (!id) return <Navigate to="/officer" replace />;

  const name = report?.merchant.display_name ?? id;
  const level: ReadinessLevel | null = report ? report.readiness.level : null;
  const corroboration = toPct(report?.trust?.corroboration_pct);
  const collection = toPct(report?.officer?.collection_rate_pct ?? report?.officer?.collection_rate);
  const aging = normalizeAging(report?.officer?.aging);
  const weekly = normalizeWeekly(report?.officer?.weekly_activity);
  const limitations = report?.limitations && report.limitations.length > 0 ? report.limitations : null;
  const redFlags = report ? report.flags.reduce((s, f) => s + f.count, 0) : null;

  const integrityLine = (() => {
    if (!verify) return 'Not verified in this pack — the integrity service did not answer.';
    const amended = verify.amended_after_sealing.length;
    if (verify.broken_at != null) {
      return `Chain BROKEN at entry ${verify.broken_at} — a sealed link is missing; the gap is the detection and it is under review.`;
    }
    if (amended > 0) {
      return `${verify.checked} entries hash-sealed; ${amended} amended after sealing — every edit remains visible in the audit trail. Tamper-evident, not tamper-proof.`;
    }
    return `${verify.checked} entries hash-sealed, chain intact, no silent edits. Tamper-evident, not tamper-proof.`;
  })();

  return (
    <div className="flex flex-col gap-6">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-ink-green" />}
        title="Committee Pack"
        purpose="One-page loan review"
        actions={
          <div className="flex flex-wrap items-center gap-3 bizro-no-print">
            <Link
              to="/officer"
              className="inline-flex min-h-touch items-center gap-2 rounded-button border-2 border-ink-line bg-paper-raised px-3 text-sm font-semibold text-ink-line bizro-btn-press"
            >
              Back to officer review
            </Link>
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex min-h-touch items-center gap-2 rounded-button border-[3px] border-ink-line bg-fill-green px-4 text-sm font-semibold text-paper bizro-btn-press hover:bg-ink-green-hover"
            >
              <IconPrint className="h-5 w-5" />
              Print this pack
            </button>
          </div>
        }
      />

      {!loaded && <p className="px-1 py-6 text-center text-sm text-ink-line opacity-75">Preparing the pack…</p>}

      {loaded && !report && (
        <p role="alert" className="bizro-card px-4 py-3 text-sm font-semibold text-ledger-red">
          No report is available for this merchant — the pack cannot be printed without one.
        </p>
      )}

      {report && (
        <article
          aria-label="Credit committee pack"
          className="bizro-card bizro-print-keep flex flex-col gap-5 px-5 py-5 sm:px-7 sm:py-6"
        >
          {/* Masthead */}
          <header className="bizro-rule-h flex flex-wrap items-start justify-between gap-x-4 gap-y-2 pb-4">
            <div className="flex items-center gap-3">
              <img src="/brand/wordmark-96.png" alt="Bizro" className="h-8 w-auto" />
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-line opacity-75">
                Credit committee pack · Mawakhat review
              </p>
            </div>
            <div className="text-right text-xs text-ink-line opacity-75">
              <p className="font-numerals text-base font-bold text-ink-line">{name}</p>
              <p>
                Generated {report.generated_at_display ?? new Date(report.generated_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
              {report.mock && (
                <p className="mt-1 inline-block rounded-chip border-2 border-dashed border-ink-line bg-fill-gold px-1.5 py-0.5 text-xs font-bold uppercase tracking-wide text-ink-line">
                  Demo fixture — no real merchant
                </p>
              )}
            </div>
          </header>

          {/* Identity — captured ON the visit. Empty dashed placeholders by
              design: this pack never fabricates identity data. */}
          <section className="bizro-print-keep" aria-labelledby="c-identity">
            <h2 id="c-identity" className="mb-2 font-numerals text-lg font-semibold text-ink-line">
              Identity — capture on visit
            </h2>
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <IdentityPlaceholder icon={<IconCustomer className="h-6 w-6 text-ink-green" />} label="CNIC photo" />
              <IdentityPlaceholder icon={<IconPhoto className="h-6 w-6 text-ink-green" />} label="Shop photo" />
              <li className="flex items-center gap-2 text-sm text-ink-line">
                <span className="font-semibold">CNIC number</span>
                <span className="ml-2 h-8 flex-1 border-b-2 border-dashed border-ink-line" aria-hidden="true" />
                <span className="sr-only">to be filled in by hand on the visit</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-ink-line">
                <span className="font-semibold">Merchant phone</span>
                <span className="ml-2 h-8 flex-1 border-b-2 border-dashed border-ink-line" aria-hidden="true" />
                <span className="sr-only">to be filled in by hand on the visit</span>
              </li>
            </ul>
          </section>

          {/* Verdict + corroboration + integrity */}
          <section className="bizro-print-keep flex flex-col gap-4 sm:flex-row sm:items-center" aria-label="Readiness verdict">
            <SealGauge
              score={report.readiness.score_0_100}
              label={`Readiness score ${report.readiness.score_0_100} of 100 — ${level ? READINESS_WORDS[level] : 'unknown'}`}
              className="h-24 w-24 shrink-0"
            />
            <div className="min-w-0 flex-1">
              <p className="font-numerals text-2xl font-bold text-ink-green">
                {level ? READINESS_WORDS[level] : 'No band'}
              </p>
              {corroboration !== null && (
                <p className="mt-1 flex items-center gap-2 text-sm text-ink-line">
                  <SealMark variant={corroboration >= 50 ? 'verified' : 'pending'} />
                  Corroboration <span className="font-numerals font-semibold">{corroboration}%</span>
                  <span className="opacity-75">— entries with outside confirmation</span>
                </p>
              )}
              <p className="mt-2 flex items-start gap-2 text-xs text-ink-line">
                <IconRadar className="mt-0.5 h-4 w-4 shrink-0 text-ink-green" />
                <span>
                  <span className="font-semibold">Ledger integrity:</span> {integrityLine}
                </span>
              </p>
            </div>
          </section>

          {/* Top metrics */}
          <section className="bizro-print-keep" aria-labelledby="c-metrics">
            <h2 id="c-metrics" className="mb-2 font-numerals text-lg font-semibold text-ink-line">
              Top metrics
            </h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <Metric label="Months of records" value={`${report.consistency.months_active}`} />
              <Metric label="Entries / week" value={`${report.consistency.avg_entries_per_week}`} />
              <Metric label="Longest gap" value={`${report.consistency.longest_gap_days} days`} />
              <Metric label="AI-sourced" value={`${Math.round(report.sourcing.ai_share * 100)}%`} />
              <Metric label="Red flags" value={`${redFlags ?? 0}`} />
              {udharOutstanding !== null && (
                <Metric label="Udhar outstanding" value={formatPkr(udharOutstanding)} />
              )}
              {collection !== null && <Metric label="Collection rate" value={`${collection}%`} />}
            </dl>
          </section>

          {/* Aging + weekly activity */}
          {(aging.length > 0 || weekly.length > 0) && (
            <section className="bizro-print-keep grid gap-5 sm:grid-cols-2" aria-label="Udhar aging and activity">
              {aging.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h2 className="flex items-center gap-2 font-numerals text-lg font-semibold text-ink-line">
                    <IconUdharGiven className="h-5 w-5 text-ledger-red" /> Aging
                  </h2>
                  <OfficerAgingBars aging={aging} />
                </div>
              )}
              {weekly.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h2 className="font-numerals text-lg font-semibold text-ink-line">Entries per week</h2>
                  <WeeklyActivityBars points={weekly} label="Entries per week, oldest to newest" />
                </div>
              )}
            </section>
          )}

          {/* Flags */}
          <section className="bizro-print-keep" aria-labelledby="c-flags">
            <h2 id="c-flags" className="mb-2 font-numerals text-lg font-semibold text-ink-line">
              Flags to probe on the visit
            </h2>
            {report.flags.length === 0 ? (
              <p className="text-sm text-ink-line">No flags in this period.</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {report.flags.map((f) => (
                  <li key={f.flag} className="flex items-center gap-2 text-sm text-ink-line">
                    <IconFlag className="h-5 w-5 shrink-0 text-ledger-red" />
                    <span>
                      <span className="font-semibold">{f.flag.replace(/_/g, ' ')}</span> × {f.count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Limitations — the pack's own honesty line. Server-provided when
              present; otherwise the standing §9 house disclosure, labeled. */}
          <section className="bizro-print-keep bizro-rule-h pb-4" aria-labelledby="c-limits">
            <h2 id="c-limits" className="mb-2 font-numerals text-lg font-semibold text-ink-line">
              Limitations
            </h2>
            <ul className="flex flex-col gap-1.5 text-sm text-ink-line">
              {(limitations ?? HOUSE_LIMITATIONS).map((l, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span aria-hidden="true" className="mt-0.5 font-semibold text-ink-green">—</span>
                  <span>
                    {l}
                    {!limitations && i === 0 && (
                      <span className="ml-1 text-xs opacity-75">(standing disclosure — the report payload carried none)</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </article>
      )}
    </div>
  );
}

function IdentityPlaceholder({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <li className="flex min-h-16 items-center gap-2.5 rounded-chip border-2 border-dashed border-ink-line bg-paper px-3 py-2 text-sm text-ink-line">
      {icon}
      <span className="font-semibold">{label}</span>
      <span className="ml-auto text-xs uppercase tracking-wide opacity-75">capture on visit</span>
    </li>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">{label}</dt>
      <dd className="font-numerals text-lg font-semibold text-ink-line">{value}</dd>
    </div>
  );
}
