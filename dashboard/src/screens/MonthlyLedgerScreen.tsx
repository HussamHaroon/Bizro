/* Merchant monthly ledger — design.md §6 screen 3: "Dashboard — merchant monthly
   ledger view with settled/udhar split" + the Udhar Radar widget (§7.1) + the
   300ms seal-stamp micro-animation when a pending entry gets confirmed (§4.6).
   Data: GET /api/merchants/{id}/transactions + /udhar (schema.md §4), mock-labeled
   fixtures until VITE_API_BASE_URL is set. */

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, fetchStreak } from '../api/client';
import type { SavingsStreak, Transaction, TransactionKind, UdharOutstanding } from '../types/schema';
import { AmountText } from '../components/AmountText';
import { EditTransactionForm } from '../components/EditTransactionForm';
import { EmptyState } from '../components/EmptyState';
import { HeroStat } from '../components/HeroStat';
import { LedgerDayHeader, LedgerRow } from '../components/LedgerRow';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealMark } from '../components/TrustSealBadge';
import { StreakChip } from '../components/StreakChip';
import { UdharRadar } from '../components/UdharRadar';
import {
  IconChevronLeft,
  IconChevronRight,
  IconExpense,
  IconLedger,
  IconSale,
  IconUdharGiven,
  IconUdharSettled,
} from '../components/icons';
import { formatDay, formatMonth, monthOf, shiftMonth, urduMonth } from '../lib/format';
import { T, useT } from '../i18n';
import { useMerchant } from '../merchant';

type Filter = 'all' | 'sale' | 'expense' | 'udhar';

const FILTERS: { key: Filter; en: string; ur: string }[] = [
  { key: 'all', en: 'All', ur: 'سب' },
  { key: 'sale', en: 'Sales', ur: 'فروخت' },
  { key: 'expense', en: 'Expenses', ur: 'خرچ' },
  { key: 'udhar', en: 'Udhar', ur: 'ادھار' },
];

function monthBounds(ym: string): { from: string; to: string } {
  const [y, m] = ym.split('-').map(Number);
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return { from: `${ym}-01`, to: `${ym}-${String(last).padStart(2, '0')}` };
}

function sumKind(items: Transaction[], kinds: TransactionKind[]): number {
  return items
    .filter((t) => kinds.includes(t.kind) && t.status !== 'rejected')
    .reduce((s, t) => s + t.amount_pkd, 0);
}

export function MonthlyLedgerScreen() {
  const { pick } = useT();
  const { merchantId } = useMerchant(); // re-key all data on merchant switch (D3-2)
  const currentMonth = monthOf(new Date().toISOString());
  const [month, setMonth] = useState(currentMonth);
  const [filter, setFilter] = useState<Filter>('all');
  const [txs, setTxs] = useState<Transaction[] | null>(null);
  const [udhar, setUdhar] = useState<UdharOutstanding[] | null>(null);
  /** Savings streak (D3-3, schema.md §7.3). Optional endpoint: null = no chip. */
  const [streak, setStreak] = useState<SavingsStreak | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  /** Fires the seal "thud" on the row that was just confirmed (300ms ease-out). */
  const [justConfirmedId, setJustConfirmedId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setTxs(null);
    setError(null);
    const { from, to } = monthBounds(month);
    Promise.all([api.listTransactions({ from, to }), api.listUdhar()])
      .then(([txRes, udharRes]) => {
        if (!alive) return;
        setTxs(txRes.data);
        setUdhar(udharRes.data);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : 'Could not load the ledger');
      });
    // Streak is fetched apart from the month data: it is week-scoped, and a
    // missing endpoint must hide the chip, never break the ledger.
    fetchStreak().then((s) => {
      if (alive) setStreak(s);
    });
    return () => {
      alive = false;
    };
  }, [month, merchantId]);

  const flashStamp = useCallback((id: string) => {
    setJustConfirmedId(id);
    setTimeout(() => setJustConfirmedId((cur) => (cur === id ? null : cur)), 1200);
  }, []);

  const handleConfirm = useCallback(
    async (t: Transaction) => {
      try {
        const { data } = await api.confirmTransaction(t.id);
        setTxs((cur) => cur?.map((x) => (x.id === data.id ? data : x)) ?? cur);
        flashStamp(data.id); // the ONE animation (design.md §4.6)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not confirm');
      }
    },
    [flashStamp],
  );

  const handleEdit = useCallback((t: Transaction) => {
    setExpandedId(t.id);
    setEditingId(t.id);
  }, []);

  const handleSaved = useCallback(
    (t: Transaction) => {
      setTxs((cur) => cur?.map((x) => (x.id === t.id ? t : x)) ?? cur);
      setEditingId(null);
      flashStamp(t.id);
    },
    [flashStamp],
  );

  const filtered = useMemo(() => {
    if (!txs) return null;
    switch (filter) {
      case 'sale':
        return txs.filter((t) => t.kind === 'sale');
      case 'expense':
        return txs.filter((t) => t.kind === 'expense');
      case 'udhar':
        return txs.filter((t) => t.kind === 'udhar_given' || t.kind === 'udhar_settlement');
      default:
        return txs;
    }
  }, [txs, filter]);

  const groups = useMemo(() => {
    if (!filtered) return [];
    const byDay = new Map<string, Transaction[]>();
    for (const t of filtered) {
      const day = t.occurred_at.slice(0, 10);
      byDay.set(day, [...(byDay.get(day) ?? []), t]);
    }
    return [...byDay.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  }, [filtered]);

  const stats = useMemo(() => {
    if (!txs) return null;
    const active = txs.filter((t) => t.status !== 'rejected');
    return {
      sales: sumKind(txs, ['sale']),
      expenses: sumKind(txs, ['expense']),
      udharGiven: sumKind(txs, ['udhar_given']),
      collected: sumKind(txs, ['udhar_settlement']),
      entries: active.length,
      aiEntries: active.filter((t) => t.source.type !== 'manual').length,
    };
  }, [txs]);

  return (
    <div className="flex flex-col gap-6 sm:gap-8">
      <ScreenHeader
        icon={<IconLedger className="h-9 w-9 text-ink-green" />}
        title="Monthly Ledger"
        titleUr="ماہانہ کھاتہ"
        purpose="This month's money"
        purposeUr="اس ماہ کا پیسہ"
        actions={
          <div className="flex items-center gap-2" role="group" aria-label={pick('Choose month', 'مہینہ چنیں')}>
            <button
              type="button"
              onClick={() => setMonth((m) => shiftMonth(m, -1))}
              className="bizro-btn-press inline-flex min-h-touch min-w-touch items-center justify-center rounded-button border-[3px] border-ink-line bg-paper-raised text-ink-line"
              aria-label={pick(
                `Previous month (${formatMonth(shiftMonth(month, -1))})`,
                `پچھلا مہینہ (${urduMonth(shiftMonth(month, -1))})`,
              )}
            >
              <IconChevronLeft className="h-6 w-6" />
            </button>
            <p className="min-w-28 text-center">
              <span className="block font-numerals text-lg font-semibold text-ink-green">
                {formatMonth(month)}
              </span>
              <span className="bizro-urdu block text-sm font-semibold text-ink-line" lang="ur">
                {urduMonth(month)} {month.slice(0, 4)}
              </span>
            </p>
            <button
              type="button"
              onClick={() => setMonth((m) => shiftMonth(m, 1))}
              disabled={month >= currentMonth}
              className="bizro-btn-press inline-flex min-h-touch min-w-touch items-center justify-center rounded-button border-[3px] border-ink-line bg-paper-raised text-ink-line disabled:cursor-not-allowed disabled:text-ink-green-disabled disabled:shadow-none"
              aria-label={pick(
                `Next month (${formatMonth(shiftMonth(month, 1))})`,
                `اگلا مہینہ (${urduMonth(shiftMonth(month, 1))})`,
              )}
            >
              <IconChevronRight className="h-6 w-6" />
            </button>
          </div>
        }
      />

      {error && (
        <p role="alert" className="bizro-card px-4 py-3 text-sm font-semibold text-ledger-red">
          {error}
        </p>
      )}

      {/* Hero numbers (D1-1 §2) — the month summary as large-format stats on
          raised cream cards; counts up on mount, remounts per month. */}
      {stats && stats.entries > 0 && (
        <section
          key={month}
          aria-label={pick('Month summary', 'ماہانہ خلاصہ')}
          className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 md:gap-5"
        >
          {/* Savings streak chip (D3-3) — lives in the hero, spans the grid;
              renders nothing until the streak endpoint reports ≥1 week. */}
          {streak && streak.streak_weeks >= 1 && (
            <div className="col-span-2 flex md:col-span-3">
              <StreakChip streak={streak} />
            </div>
          )}
          <HeroStat
            en="Money in"
            ur="آمدنی"
            value={stats.sales + stats.collected}
            tone="in"
            icon={<IconSale className="h-6 w-6 text-settled-teal" />}
          />
          <HeroStat
            en="Money out"
            ur="خرچ"
            value={stats.expenses + stats.udharGiven}
            tone="out"
            icon={<IconExpense className="h-6 w-6 text-ledger-red" />}
          />
          <HeroStat
            en="Net kept"
            ur="خالص بچت"
            value={Math.abs(stats.sales + stats.collected - stats.expenses - stats.udharGiven)}
            tone={stats.sales + stats.collected >= stats.expenses + stats.udharGiven ? 'in' : 'out'}
            icon={<IconUdharSettled className="h-6 w-6 text-ink-green" />}
          />
        </section>
      )}

      {/* Settled / udhar split — four glanceable cells: icon + word + amount. */}
      {stats && stats.entries > 0 && (
        <section
          aria-label={pick('Month split', 'ماہ کا خلاصہ')}
          className="bizro-card grid grid-cols-2 sm:grid-cols-4 sm:divide-x sm:divide-ink-line [&>*:nth-child(-n+2)]:border-b [&>*:nth-child(-n+2)]:border-ink-line [&>*:nth-child(odd)]:border-r [&>*:nth-child(odd)]:border-ink-line sm:[&>*:nth-child(-n+2)]:border-b-0 sm:[&>*:nth-child(odd)]:border-r-0"
        >
          <SplitCell icon={<IconSale className="h-7 w-7 text-settled-teal" />} en="Sales" ur="فروخت" amount={stats.sales} tone="in" />
          <SplitCell icon={<IconExpense className="h-7 w-7 text-ledger-red" />} en="Expenses" ur="خرچ" amount={stats.expenses} tone="out" />
          <SplitCell icon={<IconUdharGiven className="h-7 w-7 text-ledger-red" />} en="Udhar given" ur="ادھار" amount={stats.udharGiven} tone="out" />
          <SplitCell icon={<IconUdharSettled className="h-7 w-7 text-settled-teal" />} en="Collected" ur="وصولی" amount={stats.collected} tone="in" />
          <p className="col-span-2 flex flex-wrap items-center gap-2 border-t-2 border-ink-line px-4 py-3 text-sm text-ink-line sm:col-span-4">
            <SealMark variant="verified" />
            <span className="font-numerals font-semibold">
              {Math.round((stats.aiEntries / stats.entries) * 100)}%
            </span>{' '}
            <T en="of entries stamped from voice or photos" ur="انٹریاں آواز یا تصویر سے درج" />
          </p>
        </section>
      )}

      {udhar && <UdharRadar items={udhar} />}

      {/* Kind filter — every chip is word-paired (EN + UR), never icon-only.
          D4-1: square sticker chips; active = green-fill with paper text. */}
      <div role="group" aria-label={pick('Filter entries', 'انٹریاں چھانیں')} className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={`inline-flex min-h-touch items-center gap-2 rounded-chip border-[3px] px-4 text-sm font-semibold transition-colors duration-200 ease-out ${
              filter === f.key
                ? 'border-ink-line bg-fill-green text-paper shadow-hard-sm'
                : 'border-ink-line bg-paper-raised text-ink-line hover:bg-paper'
            }`}
          >
            <T en={f.en} ur={f.ur} />
          </button>
        ))}
      </div>

      {filtered === null && !error && (
        <p className="px-1 py-6 text-center text-sm text-ink-line opacity-75">
          <T en="Reading the khata…" ur="کھاتہ کھل رہا ہے" />
        </p>
      )}

      {filtered && filtered.length === 0 && (
        <EmptyState
          icon={<IconLedger className="h-12 w-12" />}
          title="No entries this month"
          titleUr="اس ماہ کوئی انٹری نہیں"
          hint="Voice notes and receipt photos will appear here as ledger rows."
          hintUr="آواز اور رسید کی تصویریں یہاں کھاتہ کی صفوں میں نظر آئیں گی۔"
          actionLabel="Back to this month"
          actionLabelUr="اس ماہ پر جائیں"
          onAction={() => {
            setMonth(currentMonth);
            setFilter('all');
          }}
        />
      )}

      {groups.length > 0 && (
        <section aria-label={pick('Entries', 'انٹریاں')} className="border-t-2 border-ink-line">
          {groups.map(([day, rows]) => (
            <ul key={day} aria-label={formatDay(day)}>
              <LedgerDayHeader>
                {formatDay(day)}{' '}
                <span className="font-normal text-ink-line opacity-70">
                  · {rows.length}{' '}
                  {pick(
                    rows.length === 1 ? 'entry' : 'entries',
                    rows.length === 1 ? 'انٹری' : 'انٹریاں',
                  )}
                </span>
              </LedgerDayHeader>
              {rows.map((t) => (
                <Fragment key={t.id}>
                  <LedgerRow
                    transaction={t}
                    expanded={expandedId === t.id}
                    onToggleDetails={() => setExpandedId((cur) => (cur === t.id ? null : t.id))}
                    onEdit={handleEdit}
                    onConfirm={handleConfirm}
                    justConfirmed={justConfirmedId === t.id}
                  />
                  {editingId === t.id && (
                    <li className="bizro-rule-h">
                      <div className="bizro-card my-2 mx-1">
                        <EditTransactionForm
                          transaction={t}
                          onSaved={handleSaved}
                          onCancel={() => setEditingId(null)}
                        />
                      </div>
                    </li>
                  )}
                </Fragment>
              ))}
            </ul>
          ))}
        </section>
      )}
    </div>
  );
}

function SplitCell({
  icon,
  en,
  ur,
  amount,
  tone,
}: {
  icon: ReactNode;
  en: string;
  ur: string;
  amount: number;
  tone: 'in' | 'out';
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      {icon}
      <div className="flex min-w-0 flex-col">
        <span className="flex flex-wrap items-baseline gap-x-1.5 text-sm font-semibold text-ink-line">
          <T en={en} ur={ur} />
        </span>
        <AmountText value={amount} tone={tone} />
      </div>
    </div>
  );
}
