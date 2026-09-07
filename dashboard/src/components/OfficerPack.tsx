/* OfficerPack — the loan-officer block of the credit report (schema.md v0.7
   addendum, credit-agent in flight): aging buckets, collection rate, top-debtor
   concentration, weekly activity, activity-drop alert — plus the trust block's
   corroboration %.

   DEFENSIVE-CONTRACT RULE (owner directive): the credit agent is shipping these
   fields in parallel. Every renderer here takes the possibly-absent field,
   normalizes it, and renders NOTHING when it's missing — a section that isn't
   in the payload is a missing feature, never an error, never a fabricated
   number. Wire spellings accepted:
     officer.aging                 [{bucket, amount_pkr, count?}]
     officer.collection_rate       0..1 fraction OR 0..100 (≤1 → ×100)
     officer.collection_rate_pct   0..100 (wins over collection_rate)
     officer.top_debtor_concentration_pct  0..100 — WARN > 40
     officer.weekly_activity       number[] | [{week?, entries}] (oldest→newest)
     officer.activity_drop_pct     number — banner when present
     trust.corroboration_pct       0..100
   Tokens only: rule-line bars (no shadows), tint chips, slab numerals. */

import type { CreditReportPreview, OfficerAgingBucket, OfficerPackBlock, OfficerWeekPoint } from '../types/schema';
import { formatPkr } from '../lib/format';
import { IconFlag, IconRadar, IconUdharGiven, IconUdharSettled } from './icons';

/** number | 0..1-fraction → 0..100, or null when unusable. */
export function toPct(v: unknown): number | null {
  if (typeof v !== 'number' || !Number.isFinite(v)) return null;
  return Math.round(v <= 1 ? v * 100 : v);
}

/** Unknown wire shape → usable bucket list (drops malformed rows). */
export function normalizeAging(raw: unknown): OfficerAgingBucket[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (b): b is OfficerAgingBucket =>
        !!b &&
        typeof (b as OfficerAgingBucket).bucket === 'string' &&
        typeof (b as OfficerAgingBucket).amount_pkr === 'number' &&
        Number.isFinite((b as OfficerAgingBucket).amount_pkr),
    )
    .map((b) => ({ bucket: b.bucket, amount_pkr: b.amount_pkr, count: b.count ?? null }));
}

/** number[] or {week?, entries|count}[] → points oldest→newest. */
export function normalizeWeekly(raw: unknown): OfficerWeekPoint[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((p): OfficerWeekPoint | null => {
      if (typeof p === 'number' && Number.isFinite(p)) return { week: null, entries: p };
      if (!!p && typeof p === 'object') {
        const o = p as { week?: unknown; entries?: unknown; count?: unknown };
        const entries = typeof o.entries === 'number' ? o.entries : typeof o.count === 'number' ? o.count : null;
        if (entries !== null && Number.isFinite(entries)) {
          return { week: typeof o.week === 'string' ? o.week : null, entries };
        }
      }
      return null;
    })
    .filter((p): p is OfficerWeekPoint => p !== null);
}

/** Does the payload carry ANY officer-pack content? (gates the whole section) */
export function officerPackHasContent(o: OfficerPackBlock | null | undefined): boolean {
  if (!o) return false;
  return (
    normalizeAging(o.aging).length > 0 ||
    toPct(o.collection_rate_pct ?? o.collection_rate) !== null ||
    toPct(o.top_debtor_concentration_pct) !== null ||
    normalizeWeekly(o.weekly_activity).length > 0 ||
    toPct(o.activity_drop_pct) !== null
  );
}

/** Concentration warning threshold (owner directive): > 40% is a probe-this
    flag, stated in words next to the number — never color alone. */
export const CONCENTRATION_WARN_PCT = 40;

/* ---- Weekly activity mini bars — flat rule-line bars, used by the officer
   cards and the pack. Pure CSS, token colors, value in the label. ------------- */

export function WeeklyActivityBars({
  points,
  label,
}: {
  points: OfficerWeekPoint[];
  label: string;
}) {
  if (points.length === 0) return null;
  const max = Math.max(...points.map((p) => p.entries), 1);
  return (
    <div
      role="img"
      aria-label={`${label}: ${points
        .map((p, i) => `week ${i + 1} ${p.entries}`)
        .join(', ')}`}
      className="flex h-10 items-end gap-1"
      title={points.map((p) => p.entries).join(' · ')}
    >
      {points.map((p, i) => (
        <span
          key={i}
          className={`w-2.5 border-2 border-ink-line ${
            p.entries > 0 ? 'bg-fill-gold' : 'bg-paper'
          }`}
          style={{ height: `${Math.max((p.entries / max) * 100, p.entries > 0 ? 12 : 6)}%` }}
        />
      ))}
    </div>
  );
}

/* ---- Aging buckets as CSS bar rows — rule-line tracks, gold fill, the
   exact figure beside every bar (print survives without hover). --------------- */

export function OfficerAgingBars({ aging }: { aging: OfficerAgingBucket[] }) {
  if (aging.length === 0) return null;
  const max = Math.max(...aging.map((b) => b.amount_pkr), 1);
  return (
    <ul className="flex flex-col gap-2">
      {aging.map((b) => (
        <li key={b.bucket} className="flex items-center gap-3 text-sm">
          <span className="w-16 shrink-0 font-numerals font-semibold text-ink-line">{b.bucket}</span>
          <span
            className="h-4 flex-1 border-2 border-ink-line bg-paper"
            role="img"
            aria-label={`${b.bucket} days: ${formatPkr(b.amount_pkr)}`}
          >
            <span
              className="block h-full bg-fill-gold"
              style={{ width: `${Math.max((b.amount_pkr / max) * 100, b.amount_pkr > 0 ? 4 : 0)}%` }}
            />
          </span>
          <span className="w-24 shrink-0 text-right font-numerals font-semibold text-ink-line">
            {formatPkr(b.amount_pkr)}
            {typeof b.count === 'number' && Number.isFinite(b.count) && (
              <span className="block text-xs font-normal opacity-75">
                {b.count} {b.count === 1 ? 'customer' : 'customers'}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ---- The whole pack — mounts on /credit and in the committee print view ----- */

export function OfficerPack({ report }: { report: CreditReportPreview }) {
  const o = report.officer ?? null;
  if (!officerPackHasContent(o)) return null; // graceful absence — no empty card
  const o2 = o as OfficerPackBlock;

  const corroboration = toPct(report.trust?.corroboration_pct);
  const collection = toPct(o2.collection_rate_pct ?? o2.collection_rate);
  const concentration = toPct(o2.top_debtor_concentration_pct);
  const drop = toPct(o2.activity_drop_pct);
  const aging = normalizeAging(o2.aging);
  const weekly = normalizeWeekly(o2.weekly_activity);
  const concentrationHigh = concentration !== null && concentration > CONCENTRATION_WARN_PCT;

  return (
    <section className="bizro-card px-5 py-5" aria-labelledby="officer-title">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="officer-title" className="font-numerals text-xl font-semibold text-ink-line">
          Officer pack
        </h2>
        {corroboration !== null && (
          <p className="text-sm text-ink-line">
            Corroboration{' '}
            <span className="font-numerals text-base font-semibold">{corroboration}%</span>
            <span className="text-xs opacity-75"> — entries with outside confirmation</span>
          </p>
        )}
      </div>

      {drop !== null && (
        <p
          role="alert"
          className="mb-4 flex items-center gap-2 rounded-chip border-2 border-ink-line bizro-tint-red px-3 py-2 text-sm font-semibold text-ledger-red"
        >
          <IconFlag className="h-6 w-6" />
          Activity dropped {drop}% against the recent baseline — probe this visit.
        </p>
      )}

      <dl className="grid gap-x-8 gap-y-3 text-sm text-ink-line sm:grid-cols-2">
        {collection !== null && (
          <div className="flex items-center gap-2">
            <IconUdharSettled className="h-6 w-6 shrink-0 text-settled-teal" />
            <dt className="flex-1">Collection rate</dt>
            <dd className="font-numerals text-base font-semibold">{collection}%</dd>
          </div>
        )}
        {concentration !== null && (
          <div className="flex items-center gap-2">
            <IconRadar className={`h-6 w-6 shrink-0 ${concentrationHigh ? 'text-ledger-red' : 'text-ink-green'}`} />
            <dt className="flex-1">
              Top-debtor share{' '}
              {concentrationHigh && (
                <span className="ml-1 inline-block rounded-chip border-2 border-ink-line bizro-tint-red px-1.5 text-xs font-bold uppercase text-ledger-red">
                  high
                </span>
              )}
            </dt>
            <dd className="font-numerals text-base font-semibold">{concentration}%</dd>
          </div>
        )}
      </dl>
      {concentrationHigh && (
        <p className="mt-2 text-xs text-ledger-red">
          One debtor holds over {CONCENTRATION_WARN_PCT}% of outstanding udhar — talk to them on the
          visit before any approval.
        </p>
      )}

      {aging.length > 0 && (
        <div className="mt-5 flex flex-col gap-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-green">
            <IconUdharGiven className="h-5 w-5" /> Outstanding by age
          </h3>
          <OfficerAgingBars aging={aging} />
        </div>
      )}

      {weekly.length > 0 && (
        <div className="mt-5 flex flex-col gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-green">
            Entries per week (oldest → newest)
          </h3>
          <WeeklyActivityBars points={weekly} label="Entries per week" />
          <p className="text-xs text-ink-line opacity-75">
            {weekly.reduce((s, p) => s + p.entries, 0)} entries across {weekly.length} weeks.
          </p>
        </div>
      )}
    </section>
  );
}
