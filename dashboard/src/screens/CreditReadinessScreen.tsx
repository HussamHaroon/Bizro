/* Loan-officer Credit Readiness screen — design.md §6 screen 4, the highest
   judge-facing artifact: Mawakhat-style report sections, seal treatment on
   sourced line items, and the audit-trail drill-down (tap a line → source voice
   note / receipt reference + confidence + edit-if-wrong, design.md §7.2).
   Data: GET /api/merchants/{id}/report/preview (schema.md §4). In mock mode the
   report is a DETERMINISTIC fixture — the screen says so and never presents it
   as model output (STATUS.md D0-3; qa-agent enforces). */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, fetchReportHistory } from '../api/client';
import type {
  CreditReportPreview,
  ReadinessHistoryPoint,
  ReadinessLevel,
  Transaction,
  TransactionFlag,
} from '../types/schema';
import { AmountText, toneForKind, type AmountTone } from '../components/AmountText';
import { AuditTrail } from '../components/AuditTrail';
import { Button } from '../components/Button';
import { CashflowChart } from '../components/CashflowChart';
import { EditTransactionForm } from '../components/EditTransactionForm';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealGauge } from '../components/SealGauge';
import { SealMark } from '../components/TrustSealBadge';
import { TrendSparkline } from '../components/TrendSparkline';
import {
  IconFlag,
  IconManual,
  IconPhoto,
  IconPrint,
  IconReport,
  IconVoice,
} from '../components/icons';
import { formatConfidence, formatMonth, formatPkr, urduMonth } from '../lib/format';
import { T, useT } from '../i18n';
import { useMerchant } from '../merchant';

const READINESS_WORDS: Record<ReadinessLevel, { en: string; ur: string }> = {
  ready: { en: 'Loan-ready', ur: 'قرض کے لیے تیار' },
  almost: { en: 'Almost ready', ur: 'تقریباً تیار' },
  not_yet: { en: 'Not yet ready', ur: 'ابھی تیار نہیں' },
};

const FLAG_WORDS: Record<Exclude<TransactionFlag, 'none'>, { en: string; ur: string }> = {
  price_anomaly: { en: 'Price anomalies', ur: 'قیمت میں فرق' },
  total_mismatch: { en: 'Total mismatches', ur: 'کل میں فرق' },
  duplicate_suspect: { en: 'Possible duplicates', ur: 'ممکنہ نقل' },
  low_confidence: { en: 'Low-confidence entries', ur: 'کم اعتماد انٹریاں' },
};

const SOURCE_ROWS: { key: 'voice' | 'photo' | 'manual'; icon: typeof IconVoice; en: string; ur: string }[] = [
  { key: 'voice', icon: IconVoice, en: 'Voice notes', ur: 'آواز' },
  { key: 'photo', icon: IconPhoto, en: 'Receipt photos', ur: 'تصویریں' },
  { key: 'manual', icon: IconManual, en: 'Manual entries', ur: 'دستی' },
];

export function CreditReadinessScreen() {
  const { pick } = useT();
  const { merchants, merchantId } = useMerchant(); // re-key all data on switch (D3-2)
  const [report, setReport] = useState<CreditReportPreview | null>(null);
  const [byId, setById] = useState<Map<string, Transaction>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  /** Readiness trend (D3-3, schema.md §7.2). Optional endpoint: null = no
      sparkline — fetched separately so a 404 can never break the report. */
  const [history, setHistory] = useState<ReadinessHistoryPoint[] | null>(null);

  useEffect(() => {
    let alive = true;
    setReport(null); // merchant switch → fresh report, never a stale one
    setById(new Map());
    setError(null);
    setHistory(null);
    Promise.all([api.reportPreview(), api.listTransactions()])
      .then(([rep, txs]) => {
        if (!alive) return;
        setReport(rep.data);
        setById(new Map(txs.data.map((t) => [t.id, t])));
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : 'Could not load the report');
      });
    fetchReportHistory().then((h) => {
      if (alive) setHistory(h);
    });
    return () => {
      alive = false;
    };
  }, [merchantId]);

  const handleSaved = useCallback((t: Transaction) => {
    setById((cur) => {
      const next = new Map(cur);
      next.set(t.id, t);
      return next;
    });
    setEditingId(null);
  }, []);

  const readiness = report?.readiness;

  const aiSharePct = useMemo(
    () => (report ? Math.round(report.sourcing.ai_share * 100) : 0),
    [report],
  );

  if (error) {
    return (
      <div className="flex flex-col gap-6 sm:gap-8">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-ink-green" />}
          title="Credit Readiness"
          titleUr="کریڈٹ رپورٹ"
          purpose="Loan-ready proof"
          purposeUr="قرض کے لیے ثبوت"
        />
        <p role="alert" className="bizro-card px-4 py-3 text-sm font-semibold text-ledger-red">
          {error}
        </p>
      </div>
    );
  }

  if (!report || !readiness) {
    return (
      <div className="flex flex-col gap-6 sm:gap-8">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-ink-green" />}
          title="Credit Readiness"
          titleUr="کریڈٹ رپورٹ"
          purpose="Loan-ready proof"
          purposeUr="قرض کے لیے ثبوت"
        />
        <p className="px-1 py-6 text-center text-sm text-ink-black opacity-75">
          <T en="Preparing the report…" ur="رپورٹ بن رہی ہے" />
        </p>
      </div>
    );
  }

  const levelWord = READINESS_WORDS[readiness.level];

  return (
    <div className="flex flex-col gap-6 sm:gap-8">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-ink-green" />}
        title="Credit Readiness"
        titleUr="کریڈٹ رپورٹ"
        purpose="Loan-ready proof"
        purposeUr="قرض کے لیے ثبوت"
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-right text-sm text-ink-black">
              <span className="font-semibold">{report.merchant.display_name}</span>
              <br />
              <span className="opacity-75">
                {report.period.start} → {report.period.end} ·{' '}
                <T en="Mawakhat-style review · criteria pending" ur="مواکات اندازِ جائزہ · معیارات متوقع" />
              </span>
            </p>
            {/* ONE primary action per screen (§4.4): print the report as the
                PDF artifact. Hidden in print itself; on phones the sticky
                print bar below the verdict takes over (D3). */}
            <span className="bizro-no-print hidden md:block">
              <Button
                icon={<IconPrint className="h-5 w-5" />}
                onClick={() => window.print()}
              >
                <T en="Print / PDF" ur="پرنٹ / پی ڈی ایف" />
              </Button>
            </span>
          </div>
        }
      />

      {/* Verdict (D1-1 §5) — the judge screenshot. D3 mobile-first: on phones the
          verdict text wraps ABOVE the (104px) gauge, text centered; ≥md it is the
          desktop 140px gauge left of the words. Shape + word carry the level, not
          color. */}
      <section
        className="bizro-card bizro-card-hover flex flex-col-reverse items-center gap-x-8 gap-y-5 px-5 py-6 text-center md:flex-row md:px-6 md:text-left"
        aria-label={pick('Readiness verdict', 'قرض کی تیاری')}
      >
        {/* Gauge + trend group (D3-3): the sparkline sits beside the seal gauge
            at every width; on phones the whole group lands below the verdict
            words via the section's col-reverse. */}
        <div className="flex shrink-0 items-center gap-4">
          <SealGauge
            score={readiness.score_0_100}
            label={pick(
              `Readiness score ${readiness.score_0_100} of 100 — ${levelWord.en}`,
              `تیاری کا اسکور ${readiness.score_0_100} از 100 — ${levelWord.ur}`,
            )}
            className="h-[104px] w-[104px] md:h-[140px] md:w-[140px]"
          />
          {history && <TrendSparkline points={history} />}
        </div>
        <div className="min-w-0 flex-1 md:min-w-64">
          <h2 className="flex flex-wrap items-baseline justify-center gap-x-4 gap-y-1 md:justify-start">
            <span className="font-numerals text-3xl font-bold text-ink-green">{levelWord.en}</span>
            <span className="bizro-urdu text-2xl font-semibold text-ink-green" lang="ur">
              {levelWord.ur}
            </span>
          </h2>
          <p className="mt-2 text-sm text-ink-black">
            <T en={readiness.summary_en} ur={readiness.summary_ur} />
          </p>
          <p className="mt-2 flex flex-wrap items-center justify-center gap-2 text-xs text-ink-black opacity-75 md:justify-start">
            <SealMark variant={readiness.level === 'ready' ? 'verified' : 'pending'} />
            <T en="Readiness score · Mawakhat-style review" ur="تیاری کا اسکور · مواکات اندازِ جائزہ" />
          </p>
        </div>
      </section>

      {/* Mobile-only sticky print (D3): the ONE primary action stays reachable
          while scrolling on phones — it floats just above the bottom tab bar
          (and its merchant-picker row on multi-merchant servers). Desktop uses
          the header button; both hide themselves in print. */}
      <div
        className={`bizro-no-print sticky z-30 md:hidden ${
          merchants.length > 1
            ? 'bottom-[calc(140px+env(safe-area-inset-bottom))]'
            : 'bottom-[calc(76px+env(safe-area-inset-bottom))]'
        }`}
      >
        <Button
          className="w-full shadow-raise"
          icon={<IconPrint className="h-5 w-5" />}
          onClick={() => window.print()}
        >
          <T en="Print / PDF" ur="پرنٹ / پی ڈی ایف" />
        </Button>
      </div>

      {/* Urdu narrative — dense text uses Noto Sans Urdu, NOT Nastaliq (design.md §4.2). */}
      {report.narrative_ur && (
        <section className="bizro-card px-5 py-5" aria-label={pick('Report narrative', 'رپورٹ کا خلاصہ')}>
          <p className="bizro-urdu text-base text-ink-black" lang="ur">
            {report.narrative_ur}
          </p>
        </section>
      )}

      {/* Cash-flow stability over months (D1-1 §3) — SVG grouped bars primary,
          exact numbers preserved in the visually-hidden table for SR users. */}
      <section className="bizro-card px-5 py-5" aria-labelledby="cashflow-title">
        <h2 id="cashflow-title" className="mb-4 flex flex-wrap items-baseline gap-x-2">
          <T
            en="Cash-flow by month"
            ur="ماہانہ نقد رواں"
            className="font-numerals text-lg font-semibold text-ink-black"
            urClassName="text-base font-semibold text-ink-black"
          />
        </h2>
        <CashflowChart months={report.monthly_cashflow} />
        <table className="sr-only w-full border-collapse text-sm">
          <caption className="text-left">
            <T en="Monthly cash-flow, exact figures" ur="ماہانہ نقد رواں، درست اعداد" />
          </caption>
          <thead>
            <tr className="text-left">
              <th className="py-2 pr-2 font-semibold"><T en="Month" ur="مہینہ" /></th>
              <th className="py-2 pr-2 text-right font-semibold"><T en="In" ur="آمدنی" /></th>
              <th className="py-2 pr-2 text-right font-semibold"><T en="Out" ur="خرچ" /></th>
              <th className="py-2 pr-2 text-right font-semibold"><T en="Net" ur="باقی" /></th>
              <th className="py-2 text-right font-semibold"><T en="Entries" ur="انٹریاں" /></th>
            </tr>
          </thead>
          <tbody>
            {report.monthly_cashflow.map((m) => (
              <tr key={m.month}>
                <th scope="row" className="py-2.5 pr-2 text-left font-semibold text-ink-black">
                  {formatMonth(m.month)} · {urduMonth(m.month)}
                </th>
                <td className="py-2.5 pr-2 text-right">{formatPkr(m.inflow_pkd)}</td>
                <td className="py-2.5 pr-2 text-right">{formatPkr(m.outflow_pkd)}</td>
                <td className="py-2.5 pr-2 text-right">
                  {formatPkr(Math.abs(m.net_pkd))}
                  {m.net_pkd < 0 ? ' −' : ''}
                </td>
                <td className="py-2.5 text-right">{m.entries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Consistency + AI sourcing — the seal earns its place here. */}
      <div className="grid gap-5 sm:grid-cols-2">
        <section className="bizro-card px-5 py-5" aria-labelledby="consistency-title">
          <h2 id="consistency-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <T
              en="Record consistency"
              ur="ریکارڈ کی تسلسل"
              className="font-numerals text-lg font-semibold text-ink-black"
              urClassName="text-base font-semibold text-ink-black"
            />
          </h2>
          <dl className="flex flex-col gap-2 text-sm text-ink-black">
            <StatRow en="Months of records" ur="مہینوں کا ریکارڈ" value={`${report.consistency.months_active}`} />
            <StatRow
              en="Entries per week (avg)"
              ur="ہفتہ وار انٹریاں"
              value={`${report.consistency.avg_entries_per_week}`}
            />
            <StatRow
              en="Longest gap"
              ur="سب سے لمبا وقفہ"
              value={`${report.consistency.longest_gap_days} ${pick(
                report.consistency.longest_gap_days === 1 ? 'day' : 'days',
                report.consistency.longest_gap_days === 1 ? 'دن' : 'دن',
              )}`}
            />
          </dl>
        </section>

        <section className="bizro-card px-5 py-5" aria-labelledby="sourcing-title">
          <h2 id="sourcing-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <T
              en="AI sourcing"
              ur="اے آئی ذرائع"
              className="font-numerals text-lg font-semibold text-ink-black"
              urClassName="text-base font-semibold text-ink-black"
            />
          </h2>
          <div className="mb-3 flex items-center gap-3">
            <SealMark variant="verified" />
            <p className="text-sm text-ink-black">
              <span className="font-numerals text-lg font-semibold">{aiSharePct}%</span>{' '}
              <T en="of entries AI-parsed & confirmed" ur="انٹریاں اے آئی سے درج و تصدیق شدہ" />
              <br />
              <span className="text-xs opacity-75">
                avg confidence {formatConfidence(report.sourcing.avg_confidence)} across{' '}
                {report.sourcing.ai_entries}/{report.sourcing.total_entries} entries
              </span>
            </p>
          </div>
          <ul className="flex flex-col gap-2 text-sm text-ink-black">
            {SOURCE_ROWS.map(({ key, icon: Icon, en, ur }) => {
              const s = report.sourcing.by_source[key];
              return (
                <li key={key} className="flex items-center gap-2">
                  <Icon className="h-6 w-6 text-ink-green" />
                  <span className="flex-1">
                    <T en={en} ur={ur} />
                  </span>
                  <span className="font-numerals font-semibold">{s?.entries ?? 0}</span>
                  <span className="w-20 text-right text-xs opacity-75">
                    conf {formatConfidence(s?.avg_confidence ?? null)}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      {/* Red flags — honest about what an officer would probe. */}
      <section className="bizro-card px-5 py-5" aria-labelledby="flags-title">
        <h2 id="flags-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
          <T
            en="Flags to review"
            ur="خطرے کے نشانات"
            className="font-numerals text-lg font-semibold text-ink-black"
            urClassName="text-base font-semibold text-ink-black"
          />
        </h2>
        {report.flags.length === 0 ? (
          <p className="text-sm text-ink-black">
            <T en="No flags in this period." ur="کوئی خطرہ نہیں" />
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {report.flags.map((f) => {
              const words = FLAG_WORDS[f.flag];
              return (
                <li key={f.flag} className="flex items-center gap-3 text-sm">
                  <IconFlag className="h-7 w-7 text-ledger-red" />
                  <span className="flex-1 text-ink-black">
                    <span className="font-semibold">
                      {words.en} × {f.count}
                    </span>{' '}
                    <span className="bizro-urdu" lang="ur">{words.ur}</span>
                  </span>
                  <span className="font-mono text-xs text-ink-black opacity-70">
                    {f.transaction_ids.length} refs
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Sourced line items with the audit-trail drill-down (design.md §7.2). */}
      <section aria-labelledby="lineitems-title">
        <h2 id="lineitems-title" className="mb-2 flex flex-wrap items-baseline gap-x-2 px-1">
          <T
            en="Sourced line items — tap for audit trail"
            ur="تفصیل دیکھنے کے لیے ٹیپ کریں"
            className="font-numerals text-lg font-semibold text-ink-black"
            urClassName="text-base font-semibold text-ink-black"
          />
        </h2>
        <ul className="border-t border-rule-line">
          {report.line_items.map((li) => {
            const t = byId.get(li.transaction_id);
            const ai = li.audit.source_type !== 'manual';
            const expanded = expandedId === li.transaction_id;
            return (
              <li key={li.transaction_id} className="bizro-rule-h">
                <button
                  type="button"
                  onClick={() => {
                    setExpandedId((cur) => (cur === li.transaction_id ? null : li.transaction_id));
                    setEditingId(null);
                  }}
                  aria-expanded={expanded}
                  className="flex min-h-14 w-full flex-wrap items-center gap-x-3 gap-y-1 px-1 py-1.5 text-left transition-colors duration-200 ease-out hover:bg-paper-cream"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-ink-black">
                        <T en={li.label} ur={li.label_ur} />
                      </span>
                      {ai && <SealMark variant={li.audit.status === 'pending' ? 'pending' : 'verified'} />}
                    </span>
                    <span className="text-xs text-ink-black opacity-75">
                      {formatMonth(li.month)} · {ai ? `${li.audit.model} · conf ${formatConfidence(li.audit.confidence)}` : pick('manual entry', 'دستی اندراج')}
                    </span>
                  </span>
                  <AmountText
                    value={li.amount_pkd}
                    tone={toneForTransaction(li.transaction_id, byId)}
                  />
                </button>
                {expanded && t && (
                  <div className="flex flex-col gap-3 pb-3">
                    <AuditTrail
                      transaction={t}
                      onEdit={() => setEditingId(li.transaction_id)}
                    />
                    {editingId === li.transaction_id && (
                      <div className="bizro-card">
                        <EditTransactionForm
                          transaction={t}
                          onSaved={handleSaved}
                          onCancel={() => setEditingId(null)}
                        />
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {/* Attribution — never fabricate model claims (qa-agent checks this). */}
      <footer className="px-1 pb-2 text-xs text-ink-black opacity-75">
        {report.mock ? (
          <p>
            <span className="font-semibold"><T en="Demo report" ur="نمائشی رپورٹ" /></span>{' '}
            <T
              en="— deterministic fixture derived from demo transactions; no model was run. Live mode shows the generating model here."
              ur="— ڈیمو لین دین سے بنائی گئی مستقل رپورٹ؛ کوئی ماڈل نہیں چلا۔ لائیو موڈ میں ماڈل کا نام یہاں نظر آئے گا۔"
            />
          </p>
        ) : (
          <p>
            <T en="Generated by" ur="تیار کردہ" />{' '}
            <span className="font-semibold">{report.model ?? 'the reporting model'}</span>{' '}
            <T en="via Alibaba Cloud Model Studio" ur="علی بابا کلاؤڈ ماڈل اسٹوڈیو سے" /> · {report.generated_at}
          </p>
        )}
      </footer>
    </div>
  );
}

function toneForTransaction(id: string, byId: Map<string, Transaction>): AmountTone {
  const t = byId.get(id);
  return t ? toneForKind(t.kind) : 'neutral';
}

function StatRow({ en, ur, value }: { en: string; ur: string; value: string }) {
  return (
    <div className="bizro-rule-h flex items-baseline justify-between gap-3 pb-1.5 last:border-b-0">
      <dt>
        <T en={en} ur={ur} />
      </dt>
      <dd className="font-numerals text-base font-semibold">{value}</dd>
    </div>
  );
}
