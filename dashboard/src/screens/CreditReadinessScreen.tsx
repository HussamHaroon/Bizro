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
  SourceType,
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
  IconWhatsApp,
} from '../components/icons';
import { formatConfidence, formatMonth, formatPkr } from '../lib/format';
import { isDemoRow } from '../lib/demo';
import { useMerchant } from '../merchant';

const READINESS_WORDS: Record<ReadinessLevel, string> = {
  ready: 'Loan-ready',
  almost: 'Almost ready',
  not_yet: 'Not yet ready',
};

const FLAG_WORDS: Record<Exclude<TransactionFlag, 'none'>, string> = {
  price_anomaly: 'Price anomalies',
  total_mismatch: 'Total mismatches',
  duplicate_suspect: 'Possible duplicates',
  low_confidence: 'Low-confidence entries',
};

const SOURCE_ROWS: { key: SourceType; icon: typeof IconVoice; label: string }[] = [
  { key: 'voice', icon: IconVoice, label: 'Voice notes' },
  { key: 'photo', icon: IconPhoto, label: 'Receipt photos' },
  { key: 'text', icon: IconWhatsApp, label: 'Typed notes' },
  { key: 'manual', icon: IconManual, label: 'Manual entries' },
];

/* --- Truthful labels + ONE coverage computation (red-team audit 2026-09-04) ---
   Defect 3: every user-visible date on this screen is formatted here — never a
   raw ISO string — in Asia/Karachi (PKT), matching the printable HTML render
   (credit-agent formatting.py) so screen and paper cannot disagree.
   Defect 1: the month count, the header range, the headline sentence and the
   bar set ALL derive from ONE computation over the loaded transactions'
   occurred_at values (computeCoverage), so they can never contradict. */

const PKT_TIME_ZONE = 'Asia/Karachi';
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DATE_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: PKT_TIME_ZONE,
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});
const DATETIME_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: PKT_TIME_ZONE,
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

/** "Jun 6, 2026" — bare YYYY-MM-DD strings are labeled from their parts (no
    timezone shift); instants are converted to PKT. */
function formatDateLabel(value: string | Date): string {
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-').map(Number);
    return `${MONTHS_SHORT[m - 1]} ${d}, ${y}`;
  }
  const dt = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return DATE_FMT.format(dt);
}

/** "Sep 3, 2026, 7:51 pm" (PKT). */
function formatDateTimeLabel(value: string | Date): string {
  const dt = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return DATETIME_FMT.format(dt).replace(/ AM/i, ' am').replace(/ PM/i, ' pm');
}

/** "Jun 6, 2026 - Sep 1, 2026". */
function formatRangeLabel(start: string | Date, end: string | Date): string {
  return `${formatDateLabel(start)} - ${formatDateLabel(end)}`;
}

interface Coverage {
  /** Distinct 'YYYY-MM' of occurred_at (same rule as the report adapter),
      sorted — the ONE month set behind count, range and bars. */
  months: string[];
  start: Date;
  end: Date;
  pending: number;
}

function computeCoverage(rows: Transaction[]): Coverage | null {
  const active = rows.filter((t) => t.status !== 'rejected');
  if (active.length === 0) return null;
  const times = active
    .map((t) => Date.parse(t.occurred_at))
    .filter((n) => Number.isFinite(n));
  if (times.length === 0) return null;
  return {
    months: [...new Set(active.map((t) => t.occurred_at.slice(0, 7)))].sort(),
    start: new Date(Math.min(...times)),
    end: new Date(Math.max(...times)),
    pending: active.filter((t) => t.status === 'pending').length,
  };
}

export function CreditReadinessScreen() {
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

  /** Defect 1: ONE computation over the loaded transactions' occurred_at
      values feeds the month count, the header range, the headline sentence
      and the bar set — they can never contradict each other again. */
  const coverage = useMemo(() => computeCoverage([...byId.values()]), [byId]);

  /** Bars aligned to the same single month set: a month in the record always
      has a bar, and no bar exists without real entries behind it. */
  const bars = useMemo(() => {
    if (!report) return [];
    if (!coverage) return report.monthly_cashflow;
    return coverage.months.flatMap((m) => {
      const b = report.monthly_cashflow.find((x) => x.month === m);
      return b ? [b] : [];
    });
  }, [report, coverage]);

  /** Defect 2: traceable refs per flag — derived from the loaded entries the
      officer can drill into when the payload itself carries no ids. */
  const flagRefs = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const t of byId.values()) {
      if (t.status === 'rejected' || t.flag === 'none') continue;
      map.set(t.flag, [...(map.get(t.flag) ?? []), t.id]);
    }
    return map;
  }, [byId]);

  if (error) {
    return (
      <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-ink-green" />}
          title="Credit Readiness"
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
      <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
        <ScreenHeader
          icon={<IconReport className="h-9 w-9 text-ink-green" />}
          title="Credit Readiness"
          purpose="Loan-ready proof"
        />
        <p className="px-1 py-6 text-center text-sm text-ink-line opacity-75">
          Preparing the report…
        </p>
      </div>
    );
  }

  const levelWord = READINESS_WORDS[readiness.level];

  /** Defects 1+3: the header range is the formatted min/max of the SAME
      computation that feeds the month count and the bars — never raw ISO.
      An empty record honestly says so instead of showing a sentinel range. */
  const periodLabel = coverage
    ? formatRangeLabel(coverage.start, coverage.end)
    : report.monthly_cashflow.length === 0
      ? 'No records yet'
      : formatRangeLabel(report.period.start, report.period.end);

  const monthsCount = coverage ? coverage.months.length : report.consistency.months_active;

  /** Defect 1: the headline sentence states the month count DERIVED from the
      actual records — never a canned "three months" that can contradict the
      consistency card or the bars. Simple English, like the rest of the screen.

      The ledger can span more months than the score was computed over (the
      report window is the last 30 days), so when the two differ the sentence
      names the scored window as well — otherwise a five-month chart sits beside
      a two-month score and reads as a single claim. */
  const scoredRangeLabel = formatRangeLabel(report.period.start, report.period.end);
  const coverageOutrunsScore =
    coverage !== null && formatRangeLabel(coverage.start, coverage.end) !== scoredRangeLabel;

  const summaryLine = coverage
    ? `Records cover ${coverage.months.length} ${coverage.months.length === 1 ? 'month' : 'months'}, from ${formatDateLabel(coverage.start)} to ${formatDateLabel(coverage.end)}.` +
      (coverageOutrunsScore ? ` The score uses ${scoredRangeLabel}.` : '') +
      (coverage.pending > 0
        ? ` ${coverage.pending} ${coverage.pending === 1 ? 'entry' : 'entries'} still need confirmation.`
        : '')
    : readiness.summary_en;

  /** Defect 4: attribution names the model ACTUALLY used and the provider
      derived at runtime server-side (canonical `model_provider`, from the
      DASHSCOPE_BASE_URL host) — never a hardcoded brand. If the payload
      carries no provider, NO provider is claimed (honest absence). */
  const modelProvider = (report as { model_provider?: string | null }).model_provider ?? null;
  const generatedLabel =
    (report as { generated_at_display?: string | null }).generated_at_display ||
    formatDateTimeLabel(report.generated_at);

  return (
    <div className="flex flex-col gap-7 sm:gap-9 md:gap-8">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-ink-green" />}
        title="Credit Readiness"
        purpose="Loan-ready proof"
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-right text-sm text-ink-line">
              <span className="font-semibold">{report.merchant.display_name}</span>
              <br />
              <span className="opacity-75">
                {periodLabel} · Mawakhat-style review · criteria pending
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
                Print / PDF
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
        className="bizro-card bizro-card-hero bizro-card-hover flex flex-col-reverse items-center gap-x-8 gap-y-5 px-5 py-6 text-center md:flex-row md:px-6 md:text-left"
        aria-label="Readiness verdict"
      >
        {/* Gauge + trend group (D3-3): the sparkline sits beside the seal gauge
            at every width; on phones the whole group lands below the verdict
            words via the section's col-reverse. */}
        <div className="flex shrink-0 items-center gap-4">
          <SealGauge
            score={readiness.score_0_100}
            label={`Readiness score ${readiness.score_0_100} of 100 — ${levelWord}`}
            className="h-[104px] w-[104px] md:h-[140px] md:w-[140px]"
          />
          {history && <TrendSparkline points={history} />}
        </div>
        <div className="min-w-0 flex-1 md:min-w-64">
          <h2 className="flex flex-wrap items-baseline justify-center gap-x-4 gap-y-1 md:justify-start">
            <span className="font-numerals text-[2rem] font-bold leading-tight text-ink-green md:text-4xl">
              {levelWord}
            </span>
          </h2>
          <p className="mt-2 text-sm text-ink-line">{summaryLine}</p>
          <p className="mt-2 flex flex-wrap items-center justify-center gap-2 text-xs text-ink-line opacity-75 md:justify-start">
            <SealMark variant={readiness.level === 'ready' ? 'verified' : 'pending'} />
            Readiness score · Mawakhat-style review
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
          className="w-full"
          icon={<IconPrint className="h-5 w-5" />}
          onClick={() => window.print()}
        >
          Print / PDF
        </Button>
      </div>

      {/* Report narrative — server-provided report content (schema.md §4), kept
          as data; the English summary above carries the same verdict. */}
      {report.narrative_ur && (
        <section className="bizro-card px-5 py-5" aria-label="Report narrative">
          <p className="bizro-urdu text-base text-ink-line" lang="ur">
            {report.narrative_ur}
          </p>
        </section>
      )}

      {/* Cash-flow stability over months (D1-1 §3) — SVG grouped bars primary,
          exact numbers preserved in the visually-hidden table for SR users. */}
      <section className="bizro-card px-5 py-5" aria-labelledby="cashflow-title">
        <h2 id="cashflow-title" className="mb-4 flex flex-wrap items-baseline gap-x-2">
          <span className="font-numerals text-lg font-semibold text-ink-line">Cash-flow by month</span>
        </h2>
        <CashflowChart months={bars} />
        {/* sr-only goes on a WRAPPER, never on the table: a <table> cannot shrink
            below its min-content width, so sr-only's width:1px was ignored and the
            nowrap cells gave this clipped table a real 473px box — enough to scroll
            the whole page sideways at a 390px viewport. A block wrapper does honour
            1px + overflow:hidden, and the table's text stays exposed to AT. */}
        <div className="sr-only">
          <table className="w-full border-collapse text-sm">
            <caption className="text-left">Monthly cash-flow, exact figures</caption>
            <thead>
              <tr className="text-left">
                <th className="py-2 pr-2 font-semibold">Month</th>
                <th className="py-2 pr-2 text-right font-semibold">In</th>
                <th className="py-2 pr-2 text-right font-semibold">Out</th>
                <th className="py-2 pr-2 text-right font-semibold">Net</th>
                <th className="py-2 text-right font-semibold">Entries</th>
              </tr>
            </thead>
            <tbody>
              {bars.map((m) => (
                <tr key={m.month}>
                  <th scope="row" className="py-2.5 pr-2 text-left font-semibold text-ink-line">
                    {formatMonth(m.month)}
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
        </div>
      </section>

      {/* Consistency + AI sourcing — the seal earns its place here. D4r fix 2:
          stacked card-to-card margin 20→24px below sm (hard shadows clear). */}
      <div className="grid gap-6 sm:grid-cols-2">
        <section className="bizro-card px-5 py-5" aria-labelledby="consistency-title">
          <h2 id="consistency-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-xl font-semibold text-ink-line">Record consistency</span>
          </h2>
          <dl className="flex flex-col gap-2 text-sm text-ink-line">
            <StatRow label="Months of records" value={`${monthsCount}`} />
            <StatRow
              label="Entries per week (avg)"
              value={`${report.consistency.avg_entries_per_week}`}
            />
            <StatRow
              label="Longest gap"
              value={`${report.consistency.longest_gap_days} ${
                report.consistency.longest_gap_days === 1 ? 'day' : 'days'
              }`}
            />
          </dl>
        </section>

        <section className="bizro-card px-5 py-5" aria-labelledby="sourcing-title">
          <h2 id="sourcing-title" className="mb-3 flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-xl font-semibold text-ink-line">AI sourcing</span>
          </h2>
          <div className="mb-3 flex items-center gap-3">
            <SealMark variant="verified" />
            <p className="text-sm text-ink-line">
              <span className="font-numerals text-2xl font-semibold">{aiSharePct}%</span>{' '}
              of entries AI-parsed &amp; confirmed
              <br />
              <span className="text-xs opacity-75">
                avg confidence {formatConfidence(report.sourcing.avg_confidence)} across{' '}
                {report.sourcing.ai_entries}/{report.sourcing.total_entries} entries
              </span>
            </p>
          </div>
          <ul className="flex flex-col gap-2 text-sm text-ink-line">
            {SOURCE_ROWS.map(({ key, icon: Icon, label }) => {
              const s = report.sourcing.by_source[key];
              return (
                <li key={key} className="flex items-center gap-2">
                  <Icon className="h-6 w-6 text-ink-green" />
                  <span className="flex-1">{label}</span>
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
          <span className="font-numerals text-lg font-semibold text-ink-line">Flags to review</span>
        </h2>
        {report.flags.length === 0 ? (
          <p className="text-sm text-ink-line">No flags in this period.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {report.flags.map((f) => {
              // Defect 2: every flag links to the entries it flags — payload
              // ids when present, else the same-flag entries from the loaded
              // transactions; a genuine absence gets an honest short reason
              // instead of the untraceable "0 refs".
              const payloadRefs = f.transaction_ids ?? [];
              const refs = payloadRefs.length > 0 ? payloadRefs : (flagRefs.get(f.flag) ?? []);
              const count = payloadRefs.length > 0 ? f.count : (refs.length || f.count);
              return (
                <li key={f.flag} className="flex items-center gap-3 text-sm">
                  <IconFlag className="h-7 w-7 text-ledger-red" />
                  <span className="flex-1 text-ink-line">
                    <span className="font-semibold">
                      {FLAG_WORDS[f.flag]} × {count}
                    </span>
                  </span>
                  <span
                    className="font-mono text-xs text-ink-line opacity-70"
                    title={refs.length > 0 ? `Flagged entries: ${refs.join(', ')}` : undefined}
                  >
                    {refs.length > 0
                      ? `${refs.length} ${refs.length === 1 ? 'ref' : 'refs'}`
                      : (f.reason ?? 'entry ids not listed in this report')}
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
          <span className="font-numerals text-lg font-semibold text-ink-line">
            Sourced line items — tap for audit trail
          </span>
        </h2>
        <ul className="border-t-[1.5px] border-ink-line">
          {report.line_items.map((li) => {
            const t = byId.get(li.transaction_id);
            const ai = li.audit.source_type !== 'manual';
            // Seeded demo rows ran no model — no seal, no model/confidence claim.
            const demo = t ? isDemoRow(t) : false;
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
                  className="flex min-h-14 w-full flex-wrap items-center gap-x-3 gap-y-1 px-1 py-[7px] text-left transition-colors duration-200 ease-out hover:bg-paper"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-ink-line">{li.label}</span>
                      {ai && !demo && <SealMark variant={li.audit.status === 'pending' ? 'pending' : 'verified'} />}
                      {demo && (
                        <span className="inline-flex items-center rounded-chip border-2 border-dashed border-ink-line bg-fill-gold px-1.5 text-xs font-bold uppercase tracking-wide text-ink-line">
                          demo
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-ink-line opacity-75">
                      {formatMonth(li.month)} ·{' '}
                      {demo
                        ? 'demo entry — no model ran'
                        : ai
                          ? `${li.audit.model} · conf ${formatConfidence(li.audit.confidence)}`
                          : 'manual entry'}
                    </span>
                  </span>
                  <AmountText
                    value={li.amount_pkr}
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
      <footer className="px-1 pb-2 text-xs text-ink-line opacity-75">
        {report.mock ? (
          <p>
            <span className="font-semibold">Demo report</span>{' '}
            — deterministic fixture derived from demo transactions; no model was run. Live mode shows the generating model here.
          </p>
        ) : (
          <p>
            Generated by{' '}
            <span className="font-semibold">{report.model ?? 'the reporting model'}</span>
            {modelProvider ? ` via ${modelProvider}` : ''} · {generatedLabel}
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

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="bizro-rule-h flex items-baseline justify-between gap-3 pb-1.5 last:border-b-0">
      <dt>{label}</dt>
      <dd className="font-numerals text-base font-semibold">{value}</dd>
    </div>
  );
}
