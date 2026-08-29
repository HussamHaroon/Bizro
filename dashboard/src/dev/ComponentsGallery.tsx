/* /dev/components — the component gallery (bizro-frontend-agent SKILL.md: Storybook
   is overkill; this route renders every library component in its states). Also the
   fastest place to re-check the token law and the a11y pairs (icon+word, color
   never alone, 48px targets) before qa-agent does. D4-1: shows the
   stamped-ledger language — hard shadow ramp, semantic fills, the rubber stamp. */

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
  { name: 'paper', hex: '#F5F1E6', note: 'page canvas — warm ledger cream (D4-1)' },
  { name: 'paper-raised', hex: '#FCF9F0', note: 'cards, stickers, raised surfaces (D4-1)' },
  { name: 'ink-line', hex: '#1F1B16', note: 'ALL borders + type baseline (D4-1)' },
  { name: 'ink-green', hex: '#0B5D3B', note: 'brand · primary actions (= green-fill)' },
  { name: 'ledger-red', hex: '#A6332B', note: 'debit / udhar / expenses (= red-fill)' },
  { name: 'seal-gold', hex: '#C98A2C', note: 'seal/stamp accent — fills only, never text on cream' },
  { name: 'settled-teal', hex: '#1F7A6C', note: 'paid / settled (= teal-fill)' },
  { name: 'teal-ink', hex: '#176156', note: 'AA text on teal tints' },
  { name: 'gold-fill', hex: '#E9A93D', note: 'punchy gold fill — ink text (D4-1)' },
  { name: 'paper-cream', hex: '#F7F2E7', note: 'EXTERNAL anchor — invoice/report renderers only' },
  { name: 'rule-line', hex: '#DCD3BE', note: 'EXTERNAL anchor — invoice/report renderers only' },
];

const FILLS: { name: string; cls: string }[] = [
  { name: 'green-fill', cls: 'bg-fill-green text-paper' },
  { name: 'red-fill', cls: 'bg-fill-red text-paper' },
  { name: 'gold-fill', cls: 'bg-fill-gold text-ink-line' },
  { name: 'teal-fill', cls: 'bg-fill-teal text-paper' },
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
      <h2 className="font-numerals text-xl font-semibold text-ink-line">{title}</h2>
      {note && <p className="text-sm text-ink-line opacity-75">{note}</p>}
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

      <Section title="1 · Color tokens" note="Locked set from design-tokens/tokens.css — nothing outside this palette ships. paper-cream/rule-line stay ONLY as external-renderer anchors.">
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {TOKENS.map((t) => (
            <li key={t.name} className="bizro-card flex items-center gap-3 px-3 py-2">
              <span
                className="h-10 w-10 shrink-0 rounded-chip border-[3px] border-ink-line"
                style={{ backgroundColor: t.hex }}
                aria-hidden="true"
              />
              <span className="text-sm text-ink-line">
                <span className="font-semibold">{t.name}</span>{' '}
                <span className="font-mono text-xs opacity-75">{t.hex}</span>
                <br />
                <span className="opacity-75">{t.note}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="2 · Stamp system (D4-1)" note="Hard offset shadows, zero blur, ink-line color · 3px card borders · square (radius-0) chips · semantic fills with fixed AA text pairs · one rotated sticker per screen (the seal).">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <span className="bizro-card rounded-chip px-4 py-2 text-sm font-semibold text-ink-line">card · shadow-hard-md</span>
            <span className="bizro-card bizro-card-hero rounded-chip px-4 py-2 text-sm font-semibold text-ink-line">hero card · shadow-hard-lg</span>
            <span className="rounded-chip border-[3px] border-ink-line bg-paper-raised px-4 py-2 text-sm font-semibold text-ink-line shadow-hard-sm">raised · shadow-hard-sm</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {FILLS.map((f) => (
              <span key={f.name} className={`rounded-chip border-[3px] border-ink-line px-3 py-2 text-sm font-semibold ${f.cls}`}>
                {f.name}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-chip border-2 border-ink-line bizro-tint-teal px-2.5 py-1 text-xs font-semibold text-teal-ink">tint-teal sticker chip</span>
            <span className="rounded-chip border-2 border-ink-line bizro-tint-red px-2.5 py-1 text-xs font-semibold text-ledger-red">tint-red sticker chip</span>
            <span className="rounded-chip border-2 border-ink-line bizro-tint-gold px-2.5 py-1 text-xs font-semibold text-ink-line">tint-gold sticker chip</span>
            <span className="rounded-chip border-2 border-ink-line bizro-tint-neutral px-2.5 py-1 text-xs font-semibold text-ink-line">tint-neutral sticker chip</span>
          </div>
        </div>
      </Section>

      <Section title="3 · Type tokens" note="Body IBM Plex Sans · numerals/headers Zilla Slab · Urdu UI Noto Sans · Nastaliq display only. Type scale: body 15px, meta 13px.">
        <div className="bizro-card flex flex-col gap-2 px-4 py-4 text-ink-line">
          <p className="text-base">Body · The ledger remembers so you don't have to.</p>
          <p className="font-numerals text-2xl font-semibold">Numerals · Rs 12,450</p>
          <p className="bizro-urdu text-base" lang="ur">اردو UI متن · ادھار اور وصولی</p>
          <p className="bizro-display-ur text-2xl" lang="ur">بزرو</p>
        </div>
      </Section>

      <Section title="4 · Button" note="48px targets · one primary per screen · solid fill + 3px ink border + hard-sm shadow · ACTIVE presses down (translate 2px,2px, shadow gone).">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Confirm <span className="bizro-urdu font-normal" lang="ur">تصدیق</span></Button>
          <Button variant="secondary">Back <span className="bizro-urdu font-normal" lang="ur">واپس</span></Button>
          <Button variant="danger">Remove <span className="bizro-urdu font-normal" lang="ur">ہٹائیں</span></Button>
          <Button disabled>Disabled</Button>
        </div>
      </Section>

      <Section title="5 · StatusPill" note="Square sticker chips: tinted bg (10–14% alpha) + 2px ink border + radius 0. Icon + word (EN + UR) — color is never the only signal.">
        <div className="flex flex-wrap gap-3">
          <StatusPill status="pending" />
          <StatusPill status="confirmed" />
          <StatusPill status="edited" />
          <StatusPill status="rejected" />
        </div>
      </Section>

      <Section title="6 · AmountText" note="Slab numerals; tone = direction (in teal / out red) paired with icons and words at usage sites.">
        <div className="bizro-card flex flex-wrap items-end gap-6 px-4 py-4">
          <AmountText value={4500} tone="in" size="sm" />
          <AmountText value={7450} tone="out" />
          <AmountText value={12800} tone="in" size="lg" />
          <AmountText value={3500} tone="out" size="xl" />
          <AmountText value={2000} tone="out" showWords />
        </div>
      </Section>

      <Section title="7 · Rubber stamp + stamp thud" note="TrustSealBadge IS a rubber stamp now: 2px dashed ink border, uppercase, rotate(-4deg), green ink (verified) / red ink (pending). Replay fires the 300ms ease-out stamp animation. The always-visible edit affordance stays (design.md §7.2).">
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

      <Section title="8 · ReceiptCard" note="3px ink-line border + hard-md shadow · 2px radius · no perforation, no gradients.">
        <ReceiptCard title="Month summary — Demo" titleUr="ماہانہ خلاصہ" meta="31 entries · 27 AI-verified">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-line">
              Net position · <span className="bizro-urdu" lang="ur">خالص</span>
            </p>
            <AmountText value={9350} tone="in" size="lg" />
          </div>
        </ReceiptCard>
      </Section>

      <Section title="9 · LedgerRow" note="2px ink-line horizontal rules (the book, bolder). Kind = icon + word + position + color. Pending row: Confirm fires the seal thud; every AI row carries Edit.">
        <ul className="border-t-2 border-ink-line">
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

      <Section title="10 · UdharRadar" note="Design.md §7.1 — money owed TO the shop, derived per schema.md §3. Flat red-fill bars with 2px ink borders on a 20%-ink track.">
        <UdharRadar items={udhar} />
      </Section>

      <Section title="11 · AuditTrail" note="Voice sample (with transcript) and OCR sample (with item lines) on the hard card.">
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

      <Section title="12 · EmptyState">
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

      <Section title="13 · Elevation (D4-1)" note="Zero-blur hard offset shadows in ink-line: sm 3px · md 5px · lg 8px. Cards hover-lift translate(-2px,-2px) into hard-lg; ledger rows ride 2px rules, never shadows.">
        <div className="flex flex-wrap items-center gap-5">
          <p className="rounded-chip border-[3px] border-ink-line bg-paper-raised px-4 py-3 text-sm font-semibold text-ink-line shadow-hard-sm">hard-sm</p>
          <p className="bizro-card rounded-chip px-4 py-3 text-sm font-semibold text-ink-line">hard-md</p>
          <p className="bizro-card bizro-card-hover rounded-chip px-4 py-3 text-sm font-semibold text-ink-line">hard-lg (hover me)</p>
        </div>
      </Section>

      <Section title="14 · Hero stat, seal gauge, cash-flow chart" note="Hero numerals slab-black clamp(2.5→4.5rem) and count up; the gauge is a flat chunky ring on a tilted sticker card; bars are flat fills with ink strokes and tilted sticker value chips on hover/focus.">
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <HeroStat en="Money in" ur="آمدنی" value={45300} tone="in" icon={<IconSale className="h-6 w-6 text-settled-teal" />} />
            <HeroStat en="Money out" ur="خرچ" value={28950} tone="out" icon={<IconExpense className="h-6 w-6 text-ledger-red" />} />
            <HeroStat en="Net kept" ur="خالص بچت" value={16350} tone="in" icon={<IconLedger className="h-6 w-6 text-ink-green" />} />
          </div>
          <div className="bizro-card flex flex-wrap items-center gap-6 px-5 py-5">
            <SealGauge score={78} label="Readiness score 78 of 100 — demo" />
            <p className="text-sm text-ink-line">SealGauge — 10px ink track, flat gold-fill arc, slab score, sticker card rotated -2°.</p>
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
        title="15 · Trend sparkline + streak chip"
        note="Flat gold-fill stroke over an ink underlay (≥3:1 non-text contrast), square endpoint; streak chip is a square gold sticker. Both render nothing when the endpoint/data is absent."
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
