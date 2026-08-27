/* /dev/components — the component gallery (bizro-frontend-agent SKILL.md: Storybook
   is overkill; this route renders every library component in its states). Also the
   fastest place to re-check the token law and the a11y pairs (icon+word, color
   never alone, 48px targets) before qa-agent does. */

import { useMemo, useState } from 'react';
import type { Transaction } from '../types/schema';
import { AmountText } from '../components/AmountText';
import { AuditTrail } from '../components/AuditTrail';
import { Button } from '../components/Button';
import { CashflowChart } from '../components/CashflowChart';
import { EditTransactionForm } from '../components/EditTransactionForm';
import { EmptyState } from '../components/EmptyState';
import { HeroStat } from '../components/HeroStat';
import { LedgerRow } from '../components/LedgerRow';
import { ReceiptCard } from '../components/ReceiptCard';
import { ScreenHeader } from '../components/ScreenHeader';
import { SealGauge } from '../components/SealGauge';
import { StatusPill } from '../components/StatusPill';
import { StreakChip } from '../components/StreakChip';
import { TrendSparkline } from '../components/TrendSparkline';
import { TrustSealBadge, SealMark } from '../components/TrustSealBadge';
import { UdharRadar } from '../components/UdharRadar';
import { IconExpense, IconLedger, IconReport, IconSale } from '../components/icons';
import { MOCK_TRANSACTIONS, deriveUdhar } from '../api/mockData';

const TOKENS: { name: string; hex: string; note: string }[] = [
  { name: 'ink-green', hex: '#0B5D3B', note: 'brand · primary actions · headers' },
  { name: 'paper-cream', hex: '#F7F2E7', note: 'background — ledger paper' },
  { name: 'ledger-red', hex: '#A6332B', note: 'debit / udhar / expenses' },
  { name: 'seal-gold', hex: '#C98A2C', note: 'AI-verified seal · fills only, never text on cream' },
  { name: 'settled-teal', hex: '#1F7A6C', note: 'paid / settled' },
  { name: 'ink-black', hex: '#211E1A', note: 'body text' },
  { name: 'rule-line', hex: '#DCD3BE', note: 'ledger rules · card borders' },
];

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-numerals text-xl font-semibold text-ink-black">{title}</h2>
      {note && <p className="text-sm text-ink-black opacity-75">{note}</p>}
      {children}
    </section>
  );
}

export function ComponentsGallery() {
  const [txs, setTxs] = useState<Transaction[]>(() => MOCK_TRANSACTIONS.map((t) => ({ ...t })));
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [stampKey, setStampKey] = useState(0);

  const samples = useMemo(() => {
    const byKind = (k: Transaction['kind']) => txs.find((t) => t.kind === k && t.status === 'confirmed')!;
    const pending = txs.find((t) => t.status === 'pending') ?? null;
    const flagged = txs.find((t) => t.flag !== 'none' && t.status !== 'pending') ?? null;
    const voiceTx =
      txs.find((t) => t.source.type === 'voice' && t.source.raw_output?.transcript) ?? null;
    const ocrTx = txs.find((t) => t.item_lines.length > 0) ?? null;
    return { byKind, pending, flagged, voiceTx, ocrTx };
  }, [txs]);

  const udhar = useMemo(() => deriveUdhar(txs), [txs]);

  return (
    <div className="flex flex-col gap-8">
      <ScreenHeader
        icon={<IconReport className="h-9 w-9 text-ink-green" />}
        title="Component Gallery"
        titleUr="اجزاء کی نمائش"
        purpose="Every part, every state"
      />

      <Section title="1 · Color tokens" note="Locked set from design-tokens/tokens.css — nothing outside this palette ships.">
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {TOKENS.map((t) => (
            <li key={t.name} className="bizro-card flex items-center gap-3 px-3 py-2">
              <span
                className="h-10 w-10 shrink-0 rounded-card border border-rule-line"
                style={{ backgroundColor: t.hex }}
                aria-hidden="true"
              />
              <span className="text-sm text-ink-black">
                <span className="font-semibold">{t.name}</span>{' '}
                <span className="font-mono text-xs opacity-75">{t.hex}</span>
                <br />
                <span className="opacity-75">{t.note}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="2 · Type tokens" note="Body IBM Plex Sans · numerals/headers Zilla Slab · Urdu UI Noto Sans · Nastaliq display only.">
        <div className="bizro-card flex flex-col gap-2 px-4 py-4 text-ink-black">
          <p className="text-base">Body · The ledger remembers so you don't have to.</p>
          <p className="font-numerals text-2xl font-semibold">Numerals · Rs 12,450</p>
          <p className="bizro-urdu text-base" lang="ur">اردو UI متن · ادھار اور وصولی</p>
          <p className="bizro-display-ur text-2xl" lang="ur">بزرو</p>
        </div>
      </Section>

      <Section title="3 · Button" note="48px targets · one primary per screen · solid ink-green.">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Confirm <span className="bizro-urdu font-normal" lang="ur">تصدیق</span></Button>
          <Button variant="secondary">Back <span className="bizro-urdu font-normal" lang="ur">واپس</span></Button>
          <Button variant="danger">Remove <span className="bizro-urdu font-normal" lang="ur">ہٹائیں</span></Button>
          <Button disabled>Disabled</Button>
        </div>
      </Section>

      <Section title="4 · StatusPill" note="Icon + word (EN + UR) — color is never the only signal.">
        <div className="flex flex-wrap gap-3">
          <StatusPill status="pending" />
          <StatusPill status="confirmed" />
          <StatusPill status="edited" />
          <StatusPill status="rejected" />
        </div>
      </Section>

      <Section title="5 · AmountText" note="Slab numerals; tone = direction (in teal / out red) paired with icons and words at usage sites.">
        <div className="bizro-card flex flex-wrap items-end gap-6 px-4 py-4">
          <AmountText value={4500} tone="in" size="sm" />
          <AmountText value={7450} tone="out" />
          <AmountText value={12800} tone="in" size="lg" />
          <AmountText value={3500} tone="out" size="xl" />
          <AmountText value={2000} tone="out" showWords />
        </div>
      </Section>

      <Section title="6 · TrustSealBadge + stamp thud" note="Always-visible edit affordance (design.md §7.2). Replay fires the 300ms ease-out stamp animation.">
        <div className="bizro-card flex flex-col gap-4 px-4 py-4">
          <TrustSealBadge
            key={`v-${stampKey}`}
            model="qwen3.5-omni-plus"
            confidence={0.88}
            stampIn
            onEdit={() => setStampKey((k) => k + 1)}
          />
          <TrustSealBadge
            key={`p-${stampKey}`}
            variant="pending"
            model="qwen3.5-ocr"
            confidence={0.68}
            onEdit={() => setStampKey((k) => k + 1)}
          />
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={() => setStampKey((k) => k + 1)}>
              Replay stamp <span className="bizro-urdu font-normal" lang="ur">دوبارہ دکھائیں</span>
            </Button>
            <SealMark variant="verified" size="md" />
            <SealMark variant="pending" size="md" />
          </div>
        </div>
      </Section>

      <Section title="7 · ReceiptCard" note="Perforated top via inline SVG · rule-line border · no shadow.">
        <ReceiptCard title="Month summary — Demo" titleUr="ماہانہ خلاصہ" meta="31 entries · 27 AI-verified">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-black">
              Net position · <span className="bizro-urdu" lang="ur">خالص</span>
            </p>
            <AmountText value={9350} tone="in" size="lg" />
          </div>
        </ReceiptCard>
      </Section>

      <Section title="8 · LedgerRow" note="Horizontal rules, never floating cards. Kind = icon + word + position + color. Pending row: Confirm fires the seal thud; every AI row carries Edit.">
        <ul className="border-t border-rule-line">
          {(['sale', 'expense', 'udhar_given', 'udhar_settlement'] as const).map((k) => {
            const t = samples.byKind(k);
            return (
              <LedgerRow
                key={t.id}
                transaction={t}
                expanded={expandedId === t.id}
                onToggleDetails={() => setExpandedId((cur) => (cur === t.id ? null : t.id))}
                onEdit={(x) => {
                  setExpandedId(x.id);
                  setEditingId(x.id);
                }}
                onConfirm={(x) =>
                  setTxs((cur) => cur.map((y) => (y.id === x.id ? { ...y, status: 'confirmed' } : y)))
                }
              />
            );
          })}
          {samples.pending && (
            <LedgerRow
              transaction={samples.pending}
              expanded={expandedId === samples.pending.id}
              onToggleDetails={() =>
                setExpandedId((cur) => (cur === samples.pending!.id ? null : samples.pending!.id))
              }
              onEdit={(x) => {
                setExpandedId(x.id);
                setEditingId(x.id);
              }}
              onConfirm={(x) =>
                setTxs((cur) => cur.map((y) => (y.id === x.id ? { ...y, status: 'confirmed' } : y)))
              }
            />
          )}
          {expandedId && editingId === expandedId && (
            <li className="bizro-rule-h">
              <div className="bizro-card my-2 mx-1">
                <EditTransactionForm
                  transaction={txs.find((t) => t.id === editingId)!}
                  onSaved={(t) => {
                    setTxs((cur) => cur.map((y) => (y.id === t.id ? t : y)));
                    setEditingId(null);
                  }}
                  onCancel={() => setEditingId(null)}
                />
              </div>
            </li>
          )}
        </ul>
      </Section>

      <Section title="9 · UdharRadar" note="Design.md §7.1 — money owed TO the shop, derived per schema.md §3.">
        <UdharRadar items={udhar} />
      </Section>

      <Section title="10 · AuditTrail" note="Voice sample (with transcript) and OCR sample (with item lines).">
        <div className="flex flex-col gap-4">
          {samples.voiceTx && (
            <AuditTrail
              transaction={samples.voiceTx}
              onEdit={() => setStampKey((k) => k + 1)}
              onConfirm={() =>
                setTxs((cur) =>
                  cur.map((y) => (y.id === samples.voiceTx!.id ? { ...y, status: 'confirmed' } : y)),
                )
              }
            />
          )}
          {samples.ocrTx && <AuditTrail transaction={samples.ocrTx} onEdit={() => setStampKey((k) => k + 1)} />}
        </div>
      </Section>

      <Section title="11 · EmptyState">
        <EmptyState
          icon={<IconLedger className="h-12 w-12" />}
          title="No entries yet"
          titleUr="ابھی کچھ نہیں"
          hint="Send a WhatsApp voice note and it lands here."
          actionLabel="See how it works"
          actionLabelUr="طریقہ دیکھیں"
          onAction={() => setStampKey((k) => k + 1)}
        />
      </Section>

      <Section title="12 · Elevation (D1-1)" note="Cards pair the rule-line border with the shadow ramp ('stamped paper'); ledger rows stay pure rule-lines ('book').">
        <p className="bizro-card px-5 py-4 text-sm text-ink-black">
          Cards: cream-raised surface, 1px rule-line border, box-shadow shadow-card, hover lifts to
          shadow-raise (200ms ease-out). Ledger rows: horizontal rules only, never floating shadow
          cards.
        </p>
      </Section>

      <Section title="13 · D1-1 hero stat, seal gauge, cash-flow chart" note="Hero numbers count up (300ms, reduced-motion safe); the gauge is the credit verdict; bars show values on hover/focus.">
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <HeroStat en="Money in" ur="آمدنی" value={45300} tone="in" icon={<IconSale className="h-6 w-6 text-settled-teal" />} />
            <HeroStat en="Money out" ur="خرچ" value={28950} tone="out" icon={<IconExpense className="h-6 w-6 text-ledger-red" />} />
            <HeroStat en="Net kept" ur="خالص بچت" value={16350} tone="in" icon={<IconLedger className="h-6 w-6 text-ink-green" />} />
          </div>
          <div className="bizro-card flex flex-wrap items-center gap-6 px-5 py-5">
            <SealGauge score={78} label="Readiness score 78 of 100 — demo" />
            <p className="text-sm text-ink-black">SealGauge — 140px gold ring, tick marks, Zilla Slab score.</p>
          </div>
          <div className="bizro-card px-5 py-5">
            <CashflowChart
              months={[
                { month: '2026-06', inflow_pkd: 5730, outflow_pkd: 13300, net_pkd: -7570, entries: 8 },
                { month: '2026-07', inflow_pkd: 5810, outflow_pkd: 17450, net_pkd: -11640, entries: 9 },
                { month: '2026-08', inflow_pkd: 7820, outflow_pkd: 19770, net_pkd: -11950, entries: 14 },
              ]}
            />
          </div>
        </div>
      </Section>

      <Section
        title="14 · D3 trend sparkline + streak chip"
        note="Readiness-over-time (GET /report/history, schema.md §7.2) and savings streak (GET /streak, §7.3). Both render nothing when the endpoint/data is absent."
      >
        <div className="flex flex-wrap items-center gap-6">
          <div className="bizro-card flex flex-wrap items-center gap-5 px-5 py-5">
            <SealGauge score={78} label="Readiness score 78 of 100 — demo" className="h-[104px] w-[104px] md:h-[140px] md:w-[140px]" />
            <TrendSparkline
              points={[
                { generated_at: '2026-07-01T21:00:00+05:00', score: 52, band: 'not_yet' },
                { generated_at: '2026-07-15T21:00:00+05:00', score: 61, band: 'almost' },
                { generated_at: '2026-08-01T21:00:00+05:00', score: 70, band: 'almost' },
                { generated_at: '2026-08-21T21:00:00+05:00', score: 78, band: 'almost' },
              ]}
            />
          </div>
          <StreakChip streak={{ streak_weeks: 3, best_streak_weeks: 5, current_week_positive: true }} />
        </div>
      </Section>
    </div>
  );
}
