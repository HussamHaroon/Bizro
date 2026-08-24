/* MOCK FIXTURES — shaped EXACTLY like server/schema.md §1 (canonical transaction JSON).
   Every object these factories emit satisfies the `Transaction` interface verbatim.
   Per STATUS.md D0-3 (MOCK_MODE convention): mock data is clearly labeled and never
   pretends to be real model output. Swap to the live API by setting VITE_API_BASE_URL
   (a base-URL change only — bizro-frontend-agent SKILL.md deliverable 4).

   Scenario: "Bismillah Karyana Store", Karachi — June–Aug 2026, enough history for the
   Credit Readiness report (design.md §6 screen 4). Includes every kind, all three
   source types, all flags, all statuses, a below-threshold confidence (0.68 < 0.75 →
   status=pending per schema.md §1), and one merchant-edited entry (PATCH audit path). */

import type {
  CreditReportPreview,
  ReadinessLevel,
  Transaction,
  TransactionKind,
  TransactionSource,
  TransactionStatus,
  TransactionFlag,
  UdharOutstanding,
} from '../types/schema';

const VOICE = 'qwen3.5-omni-plus';
const OCR_VL = 'qwen-vl-ocr';
const OCR_NEW = 'qwen3.5-ocr';

let seq = 0;
function tx(
  kind: TransactionKind,
  amount_pkd: number,
  occurred_at: string,
  source: TransactionSource,
  p: {
    counterparty?: { name: string; phone?: string | null } | null;
    description?: string | null;
    item_lines?: Transaction['item_lines'];
    flag?: TransactionFlag;
    status?: TransactionStatus;
    confirmation_ur?: string | null;
    raw_output?: TransactionSource['raw_output'];
  } = {},
): Transaction {
  seq += 1;
  return {
    id: `mock-tx-${String(seq).padStart(3, '0')}`,
    kind,
    amount_pkd,
    currency: 'PKR',
    counterparty: p.counterparty
      ? { name: p.counterparty.name, phone: p.counterparty.phone ?? null }
      : null,
    description: p.description ?? null,
    item_lines: p.item_lines ?? [],
    occurred_at,
    source,
    flag: p.flag ?? 'none',
    status: p.status ?? 'confirmed',
    confirmation_ur:
      p.confirmation_ur !== undefined ? p.confirmation_ur : defaultConfirmationUr(kind, amount_pkd, p.counterparty?.name),
  };
}

function defaultConfirmationUr(kind: TransactionKind, amount: number, who?: string): string {
  const name = who ?? '';
  switch (kind) {
    case 'sale':
      return `فروخت ${amount} روپے۔ کیا یہ درست ہے؟`;
    case 'expense':
      return `خرچ ${amount} روپے۔ کیا یہ درست ہے؟`;
    case 'udhar_given':
      return `${name} کو ${amount} روپے ادھار دیے۔ کیا یہ درست ہے؟`;
    case 'udhar_settlement':
      return `${name} نے ${amount} روپے واپس کیے۔ کیا یہ درست ہے؟`;
  }
}

const v = (confidence: number, mediaId: string, transcript?: string): TransactionSource => ({
  type: 'voice',
  media_id: mediaId,
  model: VOICE,
  confidence,
  raw_output: transcript ? { transcript } : {},
});
const o = (model: string, confidence: number, mediaId: string): TransactionSource => ({
  type: 'photo',
  media_id: mediaId,
  model,
  confidence,
  raw_output: {},
});
const m = (): TransactionSource => ({ type: 'manual', media_id: null, model: null, confidence: null });

const AHMAD = { name: 'Ahmad Rasheed', phone: '+92 300 1234567' };
const SANA = { name: 'Sana Boutique', phone: '+92 321 9876543' };
const BILAL = { name: 'Bilal', phone: null };
const YUSUF = { name: 'Chacha Yusuf', phone: '+92 333 5550123' };
const HINA = { name: 'Hina Bibi', phone: null };
const ALMADINA = { name: 'Al-Madina Distributors', phone: null };

export const MOCK_MERCHANT = { id: 'mock-merchant-1', display_name: 'Bismillah Karyana Store' };

export const MOCK_TRANSACTIONS: Transaction[] = [
  // ---- June 2026 (history for the credit report) ------------------------------
  tx('sale', 1450, '2026-06-05T10:12:00+05:00', v(0.95, 'm-0601'), { counterparty: HINA }),
  tx('expense', 6800, '2026-06-09T18:40:00+05:00', o(OCR_VL, 0.91, 'm-0602'), {
    counterparty: ALMADINA,
    description: 'Monthly stock — rice, ghee, sugar',
    item_lines: [
      { item: 'basmati rice 5kg bag', qty: 6, unit: 'bag', unit_price: 950, line_total: 5700 },
      { item: 'sugar 1kg', qty: 10, unit: 'kg', unit_price: 110, line_total: 1100 },
    ],
  }),
  tx('udhar_given', 1200, '2026-06-12T16:05:00+05:00', v(0.88, 'm-0603'), { counterparty: BILAL }),
  tx('sale', 980, '2026-06-15T11:22:00+05:00', v(0.93, 'm-0604'), { counterparty: HINA }),
  tx('expense', 1200, '2026-06-18T19:15:00+05:00', m(), { description: 'Shop electricity bill' }),
  tx('udhar_settlement', 1200, '2026-06-22T17:30:00+05:00', v(0.9, 'm-0605'), { counterparty: BILAL }),
  tx('sale', 2100, '2026-06-26T12:00:00+05:00', v(0.96, 'm-0606'), { counterparty: AHMAD }),
  tx('expense', 5300, '2026-06-29T18:05:00+05:00', o(OCR_VL, 0.9, 'm-0607'), {
    counterparty: ALMADINA,
    description: 'Fortnight restock — flour, tea',
    item_lines: [
      { item: 'chai patti 950g', qty: 4, unit: 'packet', unit_price: 850, line_total: 3400 },
      { item: 'atta 10kg bag', qty: 6, unit: 'bag', unit_price: 320, line_total: 1920 },
    ],
  }),

  // ---- July 2026 ---------------------------------------------------------------
  tx('sale', 1650, '2026-07-03T10:30:00+05:00', v(0.94, 'm-0701'), { counterparty: SANA }),
  tx('udhar_given', 2800, '2026-07-07T15:45:00+05:00', v(0.87, 'm-0702'), { counterparty: SANA }),
  tx('expense', 7200, '2026-07-11T18:50:00+05:00', o(OCR_VL, 0.92, 'm-0703'), {
    counterparty: ALMADINA,
    description: 'Monthly stock — cooking oil, dal',
    item_lines: [
      { item: 'cooking oil 5L', qty: 4, unit: 'tin', unit_price: 1250, line_total: 5000 },
      { item: 'dal masoor 1kg', qty: 8, unit: 'kg', unit_price: 275, line_total: 2200 },
    ],
  }),
  tx('sale', 760, '2026-07-14T11:05:00+05:00', m(), { counterparty: HINA }),
  tx('udhar_settlement', 1500, '2026-07-17T17:20:00+05:00', v(0.89, 'm-0704'), { counterparty: AHMAD }),
  tx('expense', 450, '2026-07-19T19:00:00+05:00', o(OCR_NEW, 0.85, 'm-0705'), {
    description: 'Tea & biscuits for shop',
    item_lines: [{ item: 'tapal chai 200g', qty: 2, unit: 'packet', unit_price: 225, line_total: 450 }],
  }),
  tx('sale', 1900, '2026-07-21T12:40:00+05:00', v(0.95, 'm-0706'), { counterparty: SANA }),
  tx('udhar_given', 900, '2026-07-24T16:10:00+05:00', v(0.82, 'm-0707'), { counterparty: YUSUF }),
  tx('expense', 6100, '2026-07-28T18:35:00+05:00', o(OCR_VL, 0.91, 'm-0708'), {
    counterparty: ALMADINA,
    description: 'Eid stock — dates, milk powder',
    item_lines: [
      { item: 'dates 1kg box', qty: 6, unit: 'box', unit_price: 750, line_total: 4500 },
      { item: 'milk powder 400g', qty: 8, unit: 'tin', unit_price: 200, line_total: 1600 },
    ],
  }),

  // ---- August 2026 (current month — ledger screen) -----------------------------
  tx('sale', 350, '2026-08-01T10:05:00+05:00', v(0.94, 'm-0801'), { counterparty: HINA }),
  tx('udhar_given', 2000, '2026-08-03T16:30:00+05:00', v(0.88, 'm-0802'), {
    counterparty: AHMAD,
    raw_output: { transcript: 'احمد کو دو ہزار روپے ادھار دیے ہیں' },
  }),
  tx('expense', 7450, '2026-08-05T18:45:00+05:00', o(OCR_VL, 0.91, 'm-0803'), {
    counterparty: ALMADINA,
    description: 'Monthly stock — rice, ghee, sugar',
    item_lines: [
      { item: 'basmati rice 5kg bag', qty: 7, unit: 'bag', unit_price: 950, line_total: 6650 },
      { item: 'sugar 1kg', qty: 8, unit: 'kg', unit_price: 100, line_total: 800 },
    ],
  }),
  tx('sale', 1250, '2026-08-07T11:15:00+05:00', v(0.97, 'm-0804'), { counterparty: SANA }),
  tx('udhar_settlement', 1000, '2026-08-09T17:05:00+05:00', v(0.9, 'm-0805'), { counterparty: AHMAD }),
  // Below the 0.75 CONFIDENCE_CONFIRM_THRESHOLD → stored pending until confirmed.
  tx('expense', 620, '2026-08-11T19:20:00+05:00', o(OCR_NEW, 0.68, 'm-0806'), {
    description: 'Blurred receipt — chai patti',
    item_lines: [{ item: 'chai patti 950g', qty: 1, unit: 'packet', unit_price: 620, line_total: 620 }],
    flag: 'low_confidence',
    status: 'pending',
    confirmation_ur: 'رسید صاف نہیں پڑھی جا سکی۔ کیا خرچ 620 روپے ہے؟',
  }),
  tx('sale', 480, '2026-08-13T10:50:00+05:00', m(), { counterparty: HINA }),
  tx('udhar_given', 3500, '2026-08-15T15:35:00+05:00', v(0.86, 'm-0807'), { counterparty: SANA }),
  // Price anomaly caught by the Vision Audit sanity check; merchant EDITED it.
  tx('expense', 2800, '2026-08-17T18:55:00+05:00', o(OCR_VL, 0.83, 'm-0808'), {
    description: 'Snacks restock (qty corrected by merchant)',
    item_lines: [{ item: 'bisconni party pack', qty: 4, unit: 'carton', unit_price: 700, line_total: 2800 }],
    flag: 'price_anomaly',
    status: 'edited',
  }),
  tx('sale', 2100, '2026-08-19T12:25:00+05:00', v(0.95, 'm-0809'), { counterparty: AHMAD }),
  tx('udhar_settlement', 2000, '2026-08-20T16:45:00+05:00', v(0.89, 'm-0810'), { counterparty: SANA }),
  tx('sale', 640, '2026-08-20T11:10:00+05:00', v(0.92, 'm-0811'), { counterparty: HINA }),
  tx('udhar_given', 1500, '2026-08-21T15:05:00+05:00', v(0.79, 'm-0812'), { counterparty: BILAL }),
  tx('expense', 5400, '2026-08-21T18:30:00+05:00', o(OCR_VL, 0.9, 'm-0813'), {
    counterparty: ALMADINA,
    description: 'Weekly restock — flour, oil',
    item_lines: [
      { item: 'atta 10kg bag', qty: 8, unit: 'bag', unit_price: 420, line_total: 3360 },
      { item: 'cooking oil 5L', qty: 2, unit: 'tin', unit_price: 1020, line_total: 2040 },
    ],
  }),
  // Voice parse too uncertain → pending with a clarification question (schema.md §1:
  // "the pipeline must NOT guess").
  tx('udhar_given', 800, '2026-08-21T16:40:00+05:00', v(0.71, 'm-0814'), {
    counterparty: YUSUF,
    flag: 'low_confidence',
    status: 'pending',
    confirmation_ur: 'آواز صاف نہیں تھی۔ کیا چاچا یوسف کو 800 روپے ادھار دیے؟',
  }),
];

/** Customer ids for the derived Udhar view (schema.md §3 groups by customer_id). */
const CUSTOMER_IDS: Record<string, string> = {
  'Ahmad Rasheed': 'mock-cust-ahmad',
  'Sana Boutique': 'mock-cust-sana',
  Bilal: 'mock-cust-bilal',
  'Chacha Yusuf': 'mock-cust-yusuf',
  'Hina Bibi': 'mock-cust-hina',
};

/** schema.md §3 — outstanding = Σ(udhar_given) − Σ(udhar_settlement) over
    confirmed+pending, grouped by customer. Derived from the SAME mock transactions
    so widget and ledger can never disagree. */
export function deriveUdhar(items: Transaction[]): UdharOutstanding[] {
  const byCust = new Map<string, UdharOutstanding>();
  for (const t of items) {
    if (t.kind !== 'udhar_given' && t.kind !== 'udhar_settlement') continue;
    if (t.status === 'rejected') continue;
    const name = t.counterparty?.name;
    if (!name) continue;
    const id = CUSTOMER_IDS[name] ?? `mock-cust-${name.toLowerCase().replace(/\s+/g, '-')}`;
    const cur =
      byCust.get(id) ?? { customer_id: id, name, phone: t.counterparty?.phone ?? null, outstanding_pkd: 0 };
    cur.outstanding_pkd += t.kind === 'udhar_given' ? t.amount_pkd : -t.amount_pkd;
    byCust.set(id, cur);
  }
  return [...byCust.values()]
    .filter((u) => u.outstanding_pkd > 0)
    .sort((a, b) => b.outstanding_pkd - a.outstanding_pkd);
}

/* ---- Credit Readiness preview (DRAFT shape — see types/schema.ts header) -----
   Derived transparently from the mock transactions. The real endpoint will run
   Qwen3.7-Plus (schema.md §4 GET /api/merchants/{id}/report/preview); the scoring
   heuristic below is a stand-in for demo mode and is labeled as such on-screen. */

function monthKey(iso: string): string {
  return iso.slice(0, 7);
}

export function deriveReportPreview(items: Transaction[]): CreditReportPreview {
  const sorted = [...items].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
  if (sorted.length === 0) {
    return {
      mock: true,
      merchant: MOCK_MERCHANT,
      period: { start: '1970-01-01', end: '1970-01-01' },
      generated_at: new Date().toISOString(),
      model: null,
      readiness: { level: 'not_yet', score_0_100: 0, summary_en: 'No records yet.', summary_ur: 'ابھی کوئی ریکارڈ نہیں۔' },
      monthly_cashflow: [],
      consistency: { months_active: 0, avg_entries_per_week: 0, longest_gap_days: 0 },
      flags: [],
      sourcing: {
        total_entries: 0,
        ai_entries: 0,
        ai_share: 0,
        avg_confidence: null,
        by_source: { voice: { entries: 0, avg_confidence: null }, photo: { entries: 0, avg_confidence: null }, manual: { entries: 0, avg_confidence: null } },
      },
      narrative_ur: null,
      line_items: [],
    };
  }
  const months = [...new Set(sorted.map((t) => monthKey(t.occurred_at)))];

  const monthly_cashflow = months.map((month) => {
    const rows = sorted.filter((t) => monthKey(t.occurred_at) === month && t.status !== 'rejected');
    const inflow = rows
      .filter((t) => t.kind === 'sale' || t.kind === 'udhar_settlement')
      .reduce((s, t) => s + t.amount_pkd, 0);
    const outflow = rows
      .filter((t) => t.kind === 'expense' || t.kind === 'udhar_given')
      .reduce((s, t) => s + t.amount_pkd, 0);
    return { month, inflow_pkd: inflow, outflow_pkd: outflow, net_pkd: inflow - outflow, entries: rows.length };
  });

  const active = sorted.filter((t) => t.status !== 'rejected');
  const aiEntries = active.filter((t) => t.source.type !== 'manual');
  const confidences = aiEntries.map((t) => t.source.confidence).filter((c): c is number => c !== null);
  const avgConfidence = confidences.length ? confidences.reduce((s, c) => s + c, 0) / confidences.length : null;
  const spanDays = Math.max(
    1,
    Math.round(
      (Date.parse(sorted[sorted.length - 1].occurred_at) - Date.parse(sorted[0].occurred_at)) / 86_400_000,
    ),
  );

  let longestGap = 0;
  for (let i = 1; i < sorted.length; i++) {
    longestGap = Math.max(
      longestGap,
      Math.round((Date.parse(sorted[i].occurred_at) - Date.parse(sorted[i - 1].occurred_at)) / 86_400_000),
    );
  }

  const flagMap = new Map<Exclude<TransactionFlag, 'none'>, string[]>();
  for (const t of active) {
    if (t.flag === 'none') continue;
    flagMap.set(t.flag, [...(flagMap.get(t.flag) ?? []), t.id]);
  }

  const bySource = (type: 'voice' | 'photo' | 'manual') => {
    const rows = active.filter((t) => t.source.type === type);
    const cs = rows.map((t) => t.source.confidence).filter((c): c is number => c !== null);
    return {
      entries: rows.length,
      avg_confidence: cs.length ? cs.reduce((s, c) => s + c, 0) / cs.length : null,
    };
  };

  const aiShare = active.length ? aiEntries.length / active.length : 0;
  const perWeek = (active.length / spanDays) * 7;
  const score = Math.round(
    100 * (0.4 * aiShare + 0.3 * Math.min(perWeek / 6, 1) + 0.3 * (avgConfidence ?? 0)),
  );
  const level: ReadinessLevel = score >= 75 ? 'ready' : score >= 50 ? 'almost' : 'not_yet';

  // Line items: the month's headline flows + every flagged entry, each carrying its
  // audit snapshot from the referenced transaction (design.md §7.2).
  const line_items = active
    .filter(
      (t) =>
        t.flag !== 'none' ||
        t.amount_pkd >= 5000 ||
        t.kind === 'udhar_settlement',
    )
    .slice(-14)
    .map((t) => ({
      transaction_id: t.id,
      label: lineLabel(t),
      label_ur: lineLabelUr(t),
      month: monthKey(t.occurred_at),
      amount_pkd: t.amount_pkd,
      audit: {
        source_type: t.source.type,
        media_id: t.source.media_id,
        model: t.source.model,
        confidence: t.source.confidence,
        status: t.status,
        flag: t.flag,
      },
    }));

  return {
    mock: true,
    merchant: MOCK_MERCHANT,
    period: {
      start: sorted[0].occurred_at.slice(0, 10),
      end: sorted[sorted.length - 1].occurred_at.slice(0, 10),
    },
    generated_at: '2026-08-21T21:00:00+05:00',
    model: null, // mock — real preview names the reasoning model (qwen3.7-plus)
    readiness: {
      level,
      score_0_100: score,
      summary_en:
        level === 'ready'
          ? 'Records are consistent, AI-sourced, and cover three months.'
          : 'Records look healthy; a few entries still need confirmation.',
      summary_ur:
        'ریکارڈ مستقل ہے، تین ماہ کا کھاتہ موجود ہے، اور بیشتر انٹریاں آواز یا تصویر سے خودکار درج ہوئی ہیں۔',
    },
    monthly_cashflow,
    consistency: {
      months_active: months.length,
      avg_entries_per_week: Math.round(perWeek * 10) / 10,
      longest_gap_days: longestGap,
    },
    flags: [...flagMap.entries()].map(([flag, ids]) => ({ flag, count: ids.length, transaction_ids: ids })),
    sourcing: {
      total_entries: active.length,
      ai_entries: aiEntries.length,
      ai_share: aiShare,
      avg_confidence: avgConfidence,
      by_source: { voice: bySource('voice'), photo: bySource('photo'), manual: bySource('manual') },
    },
    narrative_ur:
      'بسم اللہ کرانہ اسٹور کا تین ماہ کا ریکارڈ مستقل ہے۔ ماہانہ فروخت اور وصولیاں درج ہیں، ادھار کی رقم محدود ہے، اور ہر انٹری کی اصل آواز یا رسید محفوظ ہے۔ قرض کے لیے رپورٹ تیار ہے۔',
    line_items,
  };
}

function lineLabel(t: Transaction): string {
  const who = t.counterparty?.name ? ` — ${t.counterparty.name}` : '';
  switch (t.kind) {
    case 'sale': return `Sale${who}`;
    case 'expense': return `Supplier expense${who}`;
    case 'udhar_given': return `Udhar given${who}`;
    case 'udhar_settlement': return `Udhar repaid${who}`;
  }
}
function lineLabelUr(t: Transaction): string {
  const who = t.counterparty?.name ?? '';
  switch (t.kind) {
    case 'sale': return 'فروخت';
    case 'expense': return 'سپلائر خرچ';
    case 'udhar_given': return `${who} کو ادھار`;
    case 'udhar_settlement': return `${who} سے وصولی`;
  }
}
