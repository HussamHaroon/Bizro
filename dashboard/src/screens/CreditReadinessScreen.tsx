/* Loan-officer Credit Readiness screen — design.md §6 screen 4, the highest
   judge-facing artifact: Mawakhat-style report sections, seal treatment on
   sourced line items, and the audit-trail drill-down (tap a line → source voice
   note / receipt reference + confidence + edit-if-wrong, design.md §7.2).
   Data: GET /api/merchants/{id}/report/preview (schema.md §4). In mock mode the
   report is a DETERMINISTIC fixture — the screen says so and never presents it
   as model output (STATUS.md D0-3; qa-agent enforces). */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type {
  CreditReportPreview,
  ReadinessLevel,
  Transaction,
  TransactionFlag,
} from '../types/schema';
import { AmountText, toneForKind, type AmountTone } from '../components/AmountText';
import { AuditTrail } from '../components/AuditTrail';
import { EditTransactionForm } from '../components/EditTransactionForm';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealMark } from '../components/TrustSealBadge';
import {
  IconFlag,
  IconManual,
  IconPhoto,
  IconReport,
  IconVoice,
} from '../components/icons';
import { formatConfidence, formatMonth, urduMonth } from '../lib/format';

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
  const [report, setReport] = useState<CreditReportPreview | null>(null);
  const [byId, setById] = useState<Map<string, Transaction>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.reportPreview(), api.listTransactions()])
      .then(([rep, txs]) => {
        if (!alive) return;
        setReport(rep.data);
        setById(new Map(txs.data.map((t) => [t.id, t])));
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : 'Could not load the report');
      });
    return () => {
      alive = false;
    };
  }, []);

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
      <div className="flex flex-col gap-5">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-paper-cream" />}
          title="Credit Readiness"
          titleUr="کریڈٹ رپورٹ"
          purpose="Loan-ready proof"
        />
        <p role="alert" className="bizro-card px-4 py-3 text-sm font-semibold text-ledger-red">
          {error}
        </p>
      </div>
    );
  }

  if (!report || !readiness) {
    return (
      <div className="flex flex-col gap-5">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-paper-cream" />}
          title="Credit Readiness"
          titleUr="کریڈٹ رپورٹ"
          purpose="Loan-ready proof"
        />
        <p className="px-1 py-6 text-center text-sm text-ink-black opacity-75">
          Preparing the report… <span className="bizro-urdu" lang="ur">رپورٹ بن رہی ہے</span>
        </p>
      </div>
    );
  }

  const levelWord = READINESS_WORDS[readiness.level];

  return (
    <div className="flex flex-col gap-5">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-paper-cream" />}
        title="Credit Readiness"
        titleUr="کریڈٹ رپورٹ"
        purpose="Loan-ready proof"
        actions={
          <p className="text-right text-sm text-paper-cream">
            {report.merchant.display_name}
            <br />
            <span className="opacity-85">
              {report.period.start} → {report.period.end} · for Alkhidmat Mawakhat review
            </span>
          </p>
        }
      />

      {/* Verdict — seal treatment; shape + word carry the level, not color alone. */}
      <section className="bizro-card flex flex-wrap items-center gap-5 px-5 py-5" aria-label="Readiness verdict">
        <SealMark variant={readiness.level === 'ready' ? 'verified' : 'pending'} size="lg" />
        <div className="min-w-56 flex-1">
          <h2 className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-numerals text-2xl font-semibold text-ink-black">{levelWord.en}</span>
            <span className="bizro-urdu text-xl text-ink-black" lang="ur">{levelWord.ur}</span>
          </h2>
          <p className="mt-1 text-sm text-ink-black">{readiness.summary_en}</p>
          <p className="bizro-urdu mt-1 text-sm text-ink-black" lang="ur">
            {readiness.summary_ur}
          </p>
        </div>
        <div className="min-w-48">
          <p className="font-numerals text-4xl font-semibold text-ink-black">
            {readiness.score_0_100}
            <span className="text-xl opacity-70">/100</span>
          </p>
          <div
            className="mt-2 h-2 w-full overflow-hidden rounded-card bg-paper-cream"
            role="img"
            aria-label={`Readiness score ${readiness.score_0_100} of 100`}
          >
            <div className="h-full rounded-card bg-seal-gold" style={{ width: `${readiness.score_0_100}%` }} />
          </div>
          <p className="mt-1 text-xs text-ink-black opacity-75">
            Readiness score · <span className="bizro-urdu" lang="ur">تیاری کا اسکور</span>
          </p>
        </div>
      </section>

      {/* Urdu narrative — dense text uses Noto Sans Urdu, NOT Nastaliq (design.md §4.2). */}
      {report.narrative_ur && (
        <section className="bizro-card px-5 py-4" aria-label="Report narrative · رپورٹ کا خلاصہ">
          <p className="bizro-urdu text-base text-ink-black" lang="ur">
            {report.narrative_ur}
          </p>
        </section>
      )}

      {/* Cash-flow stability over months — the first thing a Mawakhat officer reads. */}
      <section className="bizro-card px-5 py-4" aria-labelledby="cashflow-title">
        <h2 id="cashflow-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
          <span className="font-numerals text-lg font-semibold text-ink-black">Cash-flow by month</span>
          <span className="bizro-urdu text-base text-ink-black" lang="ur">ماہانہ نقد رواں</span>
        </h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bizro-rule-h text-left text-xs uppercase tracking-wide text-ink-black opacity-70">
              <th className="py-2 pr-2 font-semibold">Month · مہینہ</th>
              <th className="py-2 pr-2 text-right font-semibold">In · آمدنی</th>
              <th className="py-2 pr-2 text-right font-semibold">Out · خرچ</th>
              <th className="py-2 pr-2 text-right font-semibold">Net · باقی</th>
              <th className="py-2 text-right font-semibold">Entries</th>
            </tr>
          </thead>
          <tbody>
            {report.monthly_cashflow.map((m) => (
              <tr key={m.month} className="bizro-rule-h">
                <th scope="row" className="py-2.5 pr-2 text-left font-semibold text-ink-black">
                  {formatMonth(m.month)}{' '}
                  <span className="bizro-urdu text-sm font-normal" lang="ur">{urduMonth(m.month)}</span>
                </th>
                <td className="py-2.5 pr-2 text-right"><AmountText value={m.inflow_pkd} tone="in" size="sm" /></td>
                <td className="py-2.5 pr-2 text-right"><AmountText value={m.outflow_pkd} tone="out" size="sm" /></td>
                <td className="py-2.5 pr-2 text-right">
                  <AmountText value={Math.abs(m.net_pkd)} tone={m.net_pkd >= 0 ? 'in' : 'out'} size="sm" />
                </td>
                <td className="py-2.5 text-right font-numerals text-ink-black">{m.entries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Consistency + AI sourcing — the seal earns its place here. */}
      <div className="grid gap-5 sm:grid-cols-2">
        <section className="bizro-card px-5 py-4" aria-labelledby="consistency-title">
          <h2 id="consistency-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-lg font-semibold text-ink-black">Record consistency</span>
            <span className="bizro-urdu text-base text-ink-black" lang="ur">ریکارڈ کی تسلسل</span>
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
              value={`${report.consistency.longest_gap_days} ${report.consistency.longest_gap_days === 1 ? 'day' : 'days'}`}
            />
          </dl>
        </section>

        <section className="bizro-card px-5 py-4" aria-labelledby="sourcing-title">
          <h2 id="sourcing-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-lg font-semibold text-ink-black">AI sourcing</span>
            <span className="bizro-urdu text-base text-ink-black" lang="ur">اے آئی ذرائع</span>
          </h2>
          <div className="mb-3 flex items-center gap-3">
            <SealMark variant="verified" />
            <p className="text-sm text-ink-black">
              <span className="font-numerals text-lg font-semibold">{aiSharePct}%</span> of entries
              AI-verified ·{' '}
              <span className="bizro-urdu" lang="ur">تصدیق شدہ</span>
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
                    {en} <span className="bizro-urdu" lang="ur">{ur}</span>
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
      <section className="bizro-card px-5 py-4" aria-labelledby="flags-title">
        <h2 id="flags-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
          <span className="font-numerals text-lg font-semibold text-ink-black">Flags to review</span>
          <span className="bizro-urdu text-base text-ink-black" lang="ur">خطرے کے نشانات</span>
        </h2>
        {report.flags.length === 0 ? (
          <p className="text-sm text-ink-black">
            No flags in this period. <span className="bizro-urdu" lang="ur">کوئی خطرہ نہیں</span>
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
          <span className="font-numerals text-lg font-semibold text-ink-black">
            Sourced line items — tap for audit trail
          </span>
          <span className="bizro-urdu text-base text-ink-black" lang="ur">تفصیل دیکھنے کے لیے ٹیپ کریں</span>
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
                  className="flex min-h-touch w-full flex-wrap items-center gap-x-3 gap-y-1 px-1 py-1.5 text-left transition-colors duration-200 ease-out hover:bg-paper-cream"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-ink-black">{li.label}</span>
                      <span className="bizro-urdu text-sm font-normal text-ink-black" lang="ur">
                        {li.label_ur}
                      </span>
                      {ai && <SealMark variant={li.audit.status === 'pending' ? 'pending' : 'verified'} />}
                    </span>
                    <span className="text-xs text-ink-black opacity-75">
                      {formatMonth(li.month)} · {ai ? `${li.audit.model} · conf ${formatConfidence(li.audit.confidence)}` : 'manual entry'}
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
            <span className="font-semibold">Demo report</span> — deterministic fixture derived from demo
            transactions; no model was run. Live mode shows the generating model here.
          </p>
        ) : (
          <p>
            Generated by <span className="font-semibold">{report.model ?? 'the reporting model'}</span> via
            Alibaba Cloud Model Studio · {report.generated_at}
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
        {en} <span className="bizro-urdu text-sm" lang="ur">{ur}</span>
      </dt>
      <dd className="font-numerals text-base font-semibold">{value}</dd>
    </div>
  );
}
