/* UdharRadar — design.md §7.1, the top differentiator widget: money owed TO the
   shopkeeper, per customer (schema.md §3 derived view). D1-1 §4 art direction:
   proportional horizontal bars — ink-green fill on a rule-line track, rounded
   caps — for the TOP-3 customers; name + Rs amount + Urdu word form on every
   row. Total stays ledger-red slab numerals with the Urdu word form. The bar is
   only a proportional glance; number + name always carry the signal (§4.7).

   One-tap REMIND (merchant-delight): every row carries a small chip button that
   asks the server to DRAFT — never send — a short, polite Urdu WhatsApp
   reminder for that customer (POST /transactions/{id}/reminder-draft). The
   merchant reviews the draft in a small modal, copies it, and sends it
   themselves. AI failure is an inline retry — never alert(), never fake text. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, draftReminder } from '../api/client';
import type { ReminderDraft } from '../api/client';
import type { UdharOutstanding } from '../types/schema';
import { AmountText } from './AmountText';
import { Button } from './Button';
import { IconCheck, IconCustomer, IconRadar, IconWhatsApp } from './icons';
import { formatPkr } from '../lib/format';

export interface UdharRadarProps {
  items: UdharOutstanding[];
  className?: string;
}

export function UdharRadar({ items, className = '' }: UdharRadarProps) {
  const total = items.reduce((s, u) => s + u.outstanding_pkd, 0);
  const top3 = items.slice(0, 3);
  const max = top3.length ? top3[0].outstanding_pkd : 0;
  /** Customer getting a reminder drafted right now — one modal at a time. */
  const [remindFor, setRemindFor] = useState<UdharOutstanding | null>(null);

  return (
    <section className={`bizro-card bizro-card-hero bizro-card-hover px-5 py-5 ${className}`} aria-labelledby="udhar-radar-title">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <IconRadar className="h-9 w-9 text-ledger-red" />
        <div className="min-w-0">
          <h2 id="udhar-radar-title" className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-numerals text-[22px] font-semibold text-ink-line">Udhar Radar</span>
          </h2>
          <p className="text-xs text-ink-line opacity-75">Who owes you</p>
        </div>
        {total > 0 && (
          <div className="ml-auto text-right">
            <AmountText value={total} tone="out" size="lg" />
          </div>
        )}
      </header>

      {items.length === 0 ? (
        <p className="px-1 py-3 text-sm text-ink-line">
          No udhar outstanding — everyone has paid up.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {top3.map((u) => (
            <li key={u.customer_id} className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <span className="flex min-w-0 items-center gap-2">
                  <IconCustomer className="h-6 w-6 shrink-0 text-ink-green" />
                  <span className="truncate font-semibold text-ink-line">{u.name}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-right">
                    <span className="font-numerals text-lg font-semibold tabular-nums text-ledger-red">
                      {formatPkr(u.outstanding_pkd)}
                    </span>
                  </span>
                  {/* One-tap polite reminder — icon + word (§4.7), 48px touch. */}
                  <button
                    type="button"
                    onClick={() => setRemindFor(u)}
                    aria-label={`Remind ${u.name} politely`}
                    className="bizro-btn-press inline-flex min-h-touch items-center gap-1.5 rounded-chip border-[3px] border-ink-line bg-paper-raised px-3 text-sm font-semibold text-ink-line hover:bg-paper"
                  >
                    <IconWhatsApp className="h-5 w-5 shrink-0 text-ink-green" />
                    Remind
                  </button>
                </span>
              </div>
              {/* Proportional bar (D4-1: flat red-fill + 2px ink-line border,
                  square caps, 20%-ink track) — the number + name carry the
                  meaning, the bar is a glance. */}
              <div
                className="h-3.5 w-full rounded-chip bg-gridline"
                role="img"
                aria-label={`${u.name}: ${formatPkr(u.outstanding_pkd)} outstanding`}
              >
                <div
                  className="h-full rounded-chip border-2 border-ink-line bg-fill-red transition-[width] duration-200 ease-out motion-reduce:transition-none"
                  style={{
                    width: `${Math.max(4, Math.round((u.outstanding_pkd / max) * 100))}%`,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {remindFor && <ReminderModal item={remindFor} onClose={() => setRemindFor(null)} />}
    </section>
  );
}

type ReminderPhase = 'drafting' | 'ready' | 'error';

/** Draft-review modal: shows the server-drafted polite Urdu reminder with
    Copy (clipboard + "Copied ✓") and Regenerate; drafting and errors are
    inline states — no alert(), and a 502 becomes a Retry, never fake text.
    The draft TEXT itself is server content aimed at the customer's WhatsApp,
    so it stays Urdu; every chrome word around it is English. */
function ReminderModal({ item, onClose }: { item: UdharOutstanding; onClose: () => void }) {
  const [phase, setPhase] = useState<ReminderPhase>('drafting');
  const [draft, setDraft] = useState<ReminderDraft | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  /** The customer's udhar entry, resolved ONCE and reused by Regenerate: the
      radar view is per-customer (schema.md §3) while the draft endpoint keys
      on a transaction, so we pick the customer's most recent live udhar_given
      entry (server re-validates kind + outstanding anyway). */
  const txIdRef = useRef<string | null>(null);
  const copyTimer = useRef<number | undefined>(undefined);
  const cardRef = useRef<HTMLDivElement | null>(null);

  const run = useCallback(async () => {
    setPhase('drafting');
    setErrorDetail(null);
    setCopied(false);
    try {
      if (!txIdRef.current) {
        const { data } = await api.listTransactions({ kind: 'udhar_given' });
        const needle = item.name.trim().toLowerCase();
        const mine = data
          .filter(
            (t) =>
              t.status !== 'rejected' &&
              (t.counterparty?.name ?? '').trim().toLowerCase() === needle,
          )
          .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
        if (mine.length === 0) throw new Error('no udhar entry found for this customer');
        txIdRef.current = mine[0].id;
      }
      setDraft(await draftReminder(txIdRef.current));
      setPhase('ready');
    } catch (e) {
      setErrorDetail(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
  }, [item.name]);

  useEffect(() => {
    void run();
    return () => {
      if (copyTimer.current !== undefined) window.clearTimeout(copyTimer.current);
    };
  }, [run]);

  useEffect(() => {
    cardRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const copyDraft = useCallback(async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(draft.reminder);
    } catch {
      // Clipboard API can be unavailable (permissions / non-secure origin) —
      // fall back to the classic hidden-textarea copy.
      const ta = document.createElement('textarea');
      ta.value = draft.reminder;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
      } catch {
        /* copy refused — the merchant can still long-press the text */
      }
      document.body.removeChild(ta);
    }
    setCopied(true);
    copyTimer.current = window.setTimeout(() => setCopied(false), 2000);
  }, [draft]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Scrim — click to dismiss; keyboard users have Escape + Close. */}
      <div className="absolute inset-0 bg-ink-line/60" aria-hidden="true" onClick={onClose} />
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="reminder-draft-title"
        aria-busy={phase === 'drafting'}
        tabIndex={-1}
        className="bizro-card relative flex w-full max-w-md flex-col gap-3 px-5 py-5 outline-none"
      >
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 id="reminder-draft-title" className="text-lg font-semibold text-ink-line">
              Polite reminder
            </h3>
            <p className="truncate text-xs text-ink-line opacity-75">
              for {item.name}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="bizro-btn-press inline-flex min-h-touch min-w-touch items-center justify-center rounded-chip border-[3px] border-ink-line bg-paper-raised pb-1 text-xl font-semibold leading-none text-ink-line hover:bg-paper"
          >
            ×
          </button>
        </header>

        {phase === 'drafting' && (
          <p className="animate-pulse py-4 text-center text-sm text-ink-line">
            Drafting a polite reminder…
          </p>
        )}

        {phase === 'error' && (
          <div className="flex flex-col gap-3">
            <p role="alert" className="text-sm font-semibold text-ledger-red">
              The reminder could not be drafted — the AI service did not answer. Please try again.
            </p>
            {errorDetail && <p className="text-xs text-ink-line opacity-70">{errorDetail}</p>}
            <div className="flex flex-wrap gap-2.5">
              <Button variant="primary" icon={<IconRadar className="h-5 w-5" />} onClick={() => void run()}>
                Retry
              </Button>
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        )}

        {phase === 'ready' && draft && (
          <>
            {/* Model output is data, not markup — rendered as text inside a
                dir=rtl Urdu run (bizro-ui-design bidi rule). */}
            <p
              className="bizro-urdu whitespace-pre-line border-2 border-ink-line bg-paper px-3 py-3 text-base leading-relaxed text-ink-line"
              lang="ur"
              dir="rtl"
            >
              {draft.reminder}
            </p>
            {draft.mock && (
              <p className="text-xs text-ink-line opacity-70">
                Sample template (offline demo) — not an AI draft.
              </p>
            )}
            <p className="text-xs text-ink-line opacity-75">
              Copy it into WhatsApp and send it yourself.
            </p>
            <div className="flex flex-wrap items-center gap-2.5">
              <Button
                variant="primary"
                icon={copied ? <IconCheck className="h-5 w-5" /> : undefined}
                onClick={() => void copyDraft()}
              >
                {copied ? 'Copied ✓' : 'Copy'}
              </Button>
              <Button variant="secondary" icon={<IconRadar className="h-5 w-5" />} onClick={() => void run()}>
                Regenerate
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
