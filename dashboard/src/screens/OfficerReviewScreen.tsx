/* Officer Review — /officer (design.md §6 screen 4's portfolio view): the loan
   officer sees EVERY applicant as one card — band, corroboration, red flags,
   udhar outstanding, weekly activity, and a verify-on-visit checklist — and
   clicks through to the per-merchant credit screen or the committee print pack.

   Data: explicit-merchant fetchers (fetchMerchantReport/fetchMerchantTransactions,
   client.ts) — the module-singleton merchant key stays untouched until the
   officer actually opens a merchant. Any per-merchant failure renders that
   card's honest "unavailable" state; it never flips the app to mock fixtures.

   MOCK RULE (D0-3): when the reports themselves are fixtures, the screen says
   so in a stamped line — demo fixtures, no real merchants. */

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { currentMerchantId, fetchMerchantReport, fetchMerchantTransactions, listMerchants } from '../api/client';
import { deriveUdhar } from '../api/mockData';
import type { CreditReportPreview, ReadinessLevel, Transaction } from '../types/schema';
import { toPct, WeeklyActivityBars } from '../components/OfficerPack';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealMark } from '../components/TrustSealBadge';
import { EmptyState } from '../components/EmptyState';
import { Button } from '../components/Button';
import {
  IconCustomer,
  IconFlag,
  IconPhoto,
  IconPrint,
  IconRadar,
  IconReport,
  IconUdharGiven,
} from '../components/icons';
import { formatPkr } from '../lib/format';
import { useMerchant } from '../merchant';

const READINESS_WORDS: Record<ReadinessLevel, string> = {
  ready: 'Loan-ready',
  almost: 'Almost ready',
  not_yet: 'Not yet ready',
};

/** Verify-on-visit checklist (owner-specified items) — the officer's field
    protocol, ticked in person. Persisted per merchant in localStorage. */
const VISIT_CHECKLIST: { key: string; label: string; icon: typeof IconPhoto }[] = [
  { key: 'cnic', label: 'CNIC sighted & photographed', icon: IconCustomer },
  { key: 'shop', label: 'Shop photo (front + stock)', icon: IconPhoto },
  { key: 'stock', label: 'Stock check vs ledger', icon: IconRadar },
  { key: 'debtor', label: 'Talk to the top debtor', icon: IconFlag },
];

const CHECKLIST_STORAGE_PREFIX = 'bizro.officer.visit.';

function loadChecklist(merchantId: string): Set<string> {
  try {
    const raw = localStorage.getItem(CHECKLIST_STORAGE_PREFIX + merchantId);
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch {
    /* storage disabled — checklist just resets, never fatal */
  }
  return new Set();
}

function saveChecklist(merchantId: string, keys: Set<string>): void {
  try {
    localStorage.setItem(CHECKLIST_STORAGE_PREFIX + merchantId, JSON.stringify([...keys]));
  } catch {
    /* best-effort */
  }
}

/** Entries per ISO week (Mon-keyed, PKT), oldest→newest, last 8 weeks — the
    SAME week rule as deriveStreak (schema.md §7.3). */
function weeklyActivity(rows: Transaction[], weeks = 8): number[] {
  const PKT_OFFSET_MS = 5 * 3_600_000;
  const WEEK_MS = 7 * 86_400_000;
  const weekKey = (iso: string): number => {
    const pkt = new Date(new Date(iso).getTime() + PKT_OFFSET_MS);
    const day = pkt.getUTCDay();
    return Date.UTC(pkt.getUTCFullYear(), pkt.getUTCMonth(), pkt.getUTCDate() - ((day + 6) % 7));
  };
  const counts = new Map<number, number>();
  for (const t of rows) {
    if (t.status === 'rejected') continue;
    const k = weekKey(t.occurred_at);
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  const thisWeek = weekKey(new Date().toISOString());
  const out: number[] = [];
  for (let i = weeks - 1; i >= 0; i--) {
    out.push(counts.get(thisWeek - i * WEEK_MS) ?? 0);
  }
  return out;
}

interface MerchantCardData {
  id: string;
  report: CreditReportPreview | null;
  transactions: Transaction[] | null;
}

export function OfficerReviewScreen() {
  const { setMerchant } = useMerchant();
  const navigate = useNavigate();
  const [cards, setCards] = useState<MerchantCardData[] | null>(null);

  useEffect(() => {
    let alive = true;
    setCards(null);
    listMerchants().then((list) => {
      // ≤1 known merchant (single-merchant demo, or the picker source failed):
      // the officer still reviews the active merchant — honestly scoped.
      const ids = list.length > 0 ? list.map((m) => m.id) : [currentMerchantId()];
      return Promise.all(
        ids.map(async (id): Promise<MerchantCardData> => {
          const [report, transactions] = await Promise.all([
            fetchMerchantReport(id),
            fetchMerchantTransactions(id),
          ]);
          return { id, report, transactions };
        }),
      );
    }).then((data) => {
      if (alive) setCards(data);
    });
    return () => {
      alive = false;
    };
  }, []);

  const summary = useMemo(() => {
    const reports = (cards ?? []).map((c) => c.report).filter((r): r is CreditReportPreview => !!r);
    const scores = reports.map((r) => r.readiness.score_0_100).filter((n) => Number.isFinite(n));
    const corroborations = reports
      .map((r) => toPct(r.trust?.corroboration_pct))
      .filter((n): n is number => n !== null);
    return {
      applicants: cards?.length ?? 0,
      avgReadiness:
        scores.length > 0 ? Math.round(scores.reduce((s, n) => s + n, 0) / scores.length) : null,
      avgCorroboration:
        corroborations.length > 0
          ? Math.round(corroborations.reduce((s, n) => s + n, 0) / corroborations.length)
          : null,
      allMock: reports.length > 0 && reports.every((r) => r.mock),
    };
  }, [cards]);

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconCustomer className="h-9 w-9 text-ink-green" />}
        title="Officer Review"
        purpose="Applicants at a glance"
      />

      {summary.allMock && (
        <p className="flex flex-wrap items-center gap-2 rounded-chip border-2 border-dashed border-ink-line bg-fill-gold px-3 py-2 text-xs font-bold uppercase tracking-wide text-ink-line">
          Demo fixtures — deterministic example merchants, no real applicants behind this page
        </p>
      )}

      {/* Summary strip */}
      <section aria-label="Portfolio summary" className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <SummaryStat label="Applicants" value={`${summary.applicants}`} />
        <SummaryStat
          label="Avg readiness"
          value={summary.avgReadiness !== null ? `${summary.avgReadiness} / 100` : null}
          absentNote="No reports yet"
        />
        <SummaryStat
          label="Avg corroboration"
          value={summary.avgCorroboration !== null ? `${summary.avgCorroboration}%` : null}
          absentNote="Not in these reports yet"
        />
      </section>

      {cards === null && <p className="px-1 py-6 text-center text-sm text-ink-line opacity-75">Loading applicants…</p>}

      {cards !== null && cards.length === 0 && (
        <EmptyState
          icon={<IconCustomer className="h-12 w-12" />}
          title="No applicants to review"
          hint="Merchant accounts appear here as the server learns about them."
        />
      )}

      <ul className="flex flex-col gap-6">
        {(cards ?? []).map((card) => (
          <OfficerCard
            key={card.id}
            card={card}
            onOpenCredit={() => {
              setMerchant(card.id);
              navigate('/credit');
            }}
            onOpenCommittee={() => {
              setMerchant(card.id);
              navigate(`/committee/${encodeURIComponent(card.id)}`);
            }}
          />
        ))}
      </ul>
    </div>
  );
}

function SummaryStat({ label, value, absentNote }: { label: string; value: string | null; absentNote?: string }) {
  return (
    <div className="bizro-card px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-green">{label}</p>
      {value !== null ? (
        <p className="font-numerals text-2xl font-bold text-ink-line">{value}</p>
      ) : (
        <p className="pt-1 text-sm text-ink-line opacity-75">{absentNote}</p>
      )}
    </div>
  );
}

function OfficerCard({
  card,
  onOpenCredit,
  onOpenCommittee,
}: {
  card: MerchantCardData;
  onOpenCredit: () => void;
  onOpenCommittee: () => void;
}) {
  const { report, transactions } = card;
  const [checked, setChecked] = useState<Set<string>>(() => loadChecklist(card.id));
  useEffect(() => {
    setChecked(loadChecklist(card.id)); // re-read when the merchant id changes
  }, [card.id]);

  function toggle(key: string) {
    setChecked((cur) => {
      const next = new Set(cur);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      saveChecklist(card.id, next);
      return next;
    });
  }

  const name = report?.merchant.display_name ?? card.id;
  const level: ReadinessLevel | null = report ? report.readiness.level : null;
  const score = report?.readiness.score_0_100 ?? null;
  const corroboration = toPct(report?.trust?.corroboration_pct);
  const entries = transactions ? transactions.filter((t) => t.status !== 'rejected').length : null;
  const redFlags = report ? report.flags.reduce((s, f) => s + f.count, 0) : null;
  const udharOutstanding = useMemo(
    () => (transactions ? deriveUdhar(transactions).reduce((s, u) => s + u.outstanding_pkd, 0) : null),
    [transactions],
  );
  const weekly = useMemo(() => (transactions ? weeklyActivity(transactions) : []), [transactions]);

  return (
    <li className="bizro-card px-5 py-5">
      {/* Name + band */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
        <h3 className="font-numerals text-xl font-bold text-ink-line">{name}</h3>
        {level && (
          <p className="flex items-center gap-2 text-sm font-semibold text-ink-line">
            <SealMark variant={level === 'ready' ? 'verified' : 'pending'} />
            {READINESS_WORDS[level]}
            {score !== null && <span className="font-numerals">· {score}/100</span>}
          </p>
        )}
      </div>
      {report === null && (
        <p role="alert" className="mt-2 text-sm font-semibold text-ledger-red">
          Report unavailable for this merchant — the server did not answer.
        </p>
      )}

      {/* Metric cells */}
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
        {corroboration !== null && (
          <MetricCell label="Corroboration" value={`${corroboration}%`} />
        )}
        {entries !== null && <MetricCell label="Entries" value={`${entries}`} />}
        {redFlags !== null && (
          <div className="flex flex-col">
            <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-green">
              <IconFlag className="h-4 w-4 text-ledger-red" /> Red flags
            </dt>
            <dd className={`font-numerals text-lg font-semibold ${redFlags > 0 ? 'text-ledger-red' : 'text-ink-line'}`}>
              {redFlags}
            </dd>
          </div>
        )}
        {udharOutstanding !== null && (
          <div className="flex flex-col">
            <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-green">
              <IconUdharGiven className="h-4 w-4 text-ledger-red" /> Udhar out
            </dt>
            <dd className="font-numerals text-lg font-semibold text-ink-line">
              {formatPkr(udharOutstanding)}
            </dd>
          </div>
        )}
      </dl>

      {/* Weekly activity (last 8 weeks, oldest → newest) */}
      {weekly.length > 0 && (
        <div className="mt-4 flex flex-col gap-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-green">
            Activity · last 8 weeks
          </p>
          <WeeklyActivityBars points={weekly.map((entries, i) => ({ week: `W${8 - i}`, entries }))} label="Entries per week, last 8 weeks" />
        </div>
      )}

      {/* Verify on visit */}
      <fieldset className="mt-5">
        <legend className="text-xs font-semibold uppercase tracking-wide text-ink-green">
          Verify on visit
        </legend>
        <ul className="mt-1.5 grid grid-cols-1 gap-1 sm:grid-cols-2">
          {VISIT_CHECKLIST.map(({ key, label, icon: Icon }) => (
            <li key={key}>
              <label className="flex min-h-touch cursor-pointer items-center gap-2.5 rounded-button px-1 py-1 text-sm text-ink-line transition-colors duration-200 ease-out hover:bg-paper">
                <input
                  type="checkbox"
                  checked={checked.has(key)}
                  onChange={() => toggle(key)}
                  className="h-6 w-6 shrink-0"
                  style={{ accentColor: 'var(--bizro-ink-green)' }}
                />
                <Icon className="h-5 w-5 shrink-0 text-ink-green" aria-hidden="true" />
                {label}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      {/* Actions */}
      <div className="mt-5 flex flex-wrap gap-3">
        <Button icon={<IconReport className="h-5 w-5" />} onClick={onOpenCredit}>
          Credit review
        </Button>
        <Button
          variant="secondary"
          icon={<IconPrint className="h-5 w-5" />}
          onClick={onOpenCommittee}
        >
          Committee pack
        </Button>
      </div>
    </li>
  );
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-green">{label}</dt>
      <dd className="font-numerals text-lg font-semibold text-ink-line">{value}</dd>
    </div>
  );
}
