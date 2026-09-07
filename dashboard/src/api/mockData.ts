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
  DemandTimingRow,
  InventoryItem,
  InventoryView,
  LedgerVerifyResult,
  MerchantInsights,
  MerchantSummary,
  PriceTrendRow,
  ReadinessLevel,
  RestockRow,
  SavingsStreak,
  SourceType,
  Transaction,
  TransactionKind,
  TransactionSource,
  TransactionStatus,
  TransactionFlag,
  TrustTier,
  UdharOutstanding,
} from '../types/schema';

/* Fixture model labels (audit KILL 2): NO model ran for these rows, so they
   must not carry a real production model id — the audit drill-down and the
   report line items print this string, and a Qwen name here would claim a
   parse that never happened. */
const VOICE = 'demo-fixture (voice row, no model ran)';
const OCR_VL = 'demo-fixture (photo row, no model ran)';
const OCR_NEW = 'demo-fixture (photo row, no model ran)';

let seq = 0;
function tx(
  kind: TransactionKind,
  amount_pkr: number,
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
    /** §11 trust tier — see the ladder on the type. Default derives from the
        row: pending or manual = self_reported, otherwise customer_confirmed
        (the merchant's own confirmation is the entry's only backing unless a
        handshake says otherwise). */
    trust_tier?: TrustTier;
  } = {},
): Transaction {
  seq += 1;
  const status = p.status ?? 'confirmed';
  const tier: TrustTier =
    p.trust_tier ?? (status === 'pending' || source.type === 'manual' ? 'self_reported' : 'customer_confirmed');
  return {
    id: `mock-tx-${String(seq).padStart(3, '0')}`,
    kind,
    amount_pkr,
    currency: 'PKR',
    counterparty: p.counterparty
      ? { name: p.counterparty.name, phone: p.counterparty.phone ?? null }
      : null,
    description: p.description ?? null,
    item_lines: p.item_lines ?? [],
    occurred_at,
    source,
    flag: p.flag ?? 'none',
    status,
    confirmation_ur:
      p.confirmation_ur !== undefined ? p.confirmation_ur : defaultConfirmationUr(kind, amount_pkr, p.counterparty?.name),
    // §11 fixture chain: labeled pseudo-hashes in insertion order (the UI never
    // renders raw hashes; the verify chip works off deriveLedgerVerify below).
    entry_hash: `mock-seal-${String(seq).padStart(3, '0')}`,
    prev_entry_hash: seq === 1 ? null : `mock-seal-${String(seq - 1).padStart(3, '0')}`,
    trust_tier: tier,
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
  // mock marker (D0-3): fixture rows are demo data — the ledger chip and the
  // audit drill-down read this and never present them as real parses.
  raw_output: transcript ? { transcript, mock: true } : { mock: true },
});
const o = (model: string, confidence: number, mediaId: string): TransactionSource => ({
  type: 'photo',
  media_id: mediaId,
  model,
  confidence,
  raw_output: { mock: true },
});
const m = (): TransactionSource => ({
  type: 'manual',
  media_id: null,
  model: null,
  confidence: null,
  raw_output: { mock: true },
});

const AHMAD = { name: 'Ahmad Rasheed', phone: '+92 300 1234567' };
const SANA = { name: 'Sana Boutique', phone: '+92 321 9876543' };
const BILAL = { name: 'Bilal', phone: null };
const YUSUF = { name: 'Chacha Yusuf', phone: '+92 333 5550123' };
const HINA = { name: 'Hina Bibi', phone: null };
const ALMADINA = { name: 'Al-Madina Distributors', phone: null };

export const MOCK_MERCHANT: MerchantSummary = {
  id: 'mock-merchant-1',
  display_name: 'Bismillah Karyana Store',
  wa_id: '923001234567',
};

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
  // INSIGHTS FIXTURE (labeled): a second oil receipt at the SAME price — with
  // the July one it gives cooking oil 5L two first-half price observations,
  // so the price-trends row below is a real median comparison, not a flip.
  tx('expense', 1250, '2026-06-26T18:10:00+05:00', o(OCR_VL, 0.9, 'm-0608'), {
    counterparty: ALMADINA,
    description: 'Oil top-up — same price',
    item_lines: [{ item: 'cooking oil 5L', qty: 1, unit: 'tin', unit_price: 1250, line_total: 1250 }],
  }),
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
  // INSIGHTS FIXTURES (labeled): flour and chai receipts that (a) give atta
  // 10kg bag a second first-half price observation (330 vs the June 320 and
  // the August 420 → a real "up" median move) and (b) stock the chai patti
  // the August chai sales below sell — 4+3+1 bought vs 7 sold leaves the fast
  // seller at in_stock 1 (low), which the restock list then ranks by demand.
  tx('expense', 1320, '2026-07-24T18:20:00+05:00', o(OCR_VL, 0.9, 'm-0709'), {
    counterparty: ALMADINA,
    description: 'Flour top-up — price watch',
    item_lines: [
      { item: 'atta 10kg bag', qty: 2, unit: 'bag', unit_price: 330, line_total: 660 },
      { item: 'atta 10kg bag', qty: 2, unit: 'bag', unit_price: 330, line_total: 660 },
    ],
  }),
  tx('expense', 1800, '2026-07-25T17:50:00+05:00', o(OCR_VL, 0.91, 'm-0710'), {
    counterparty: ALMADINA,
    description: 'Chai patti restock',
    item_lines: [{ item: 'chai patti 950g', qty: 3, unit: 'packet', unit_price: 600, line_total: 1800 }],
  }),
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
  // INSIGHTS FIXTURES (labeled): chai patti voice sales WITH item lines, so
  // the demand card has a real pattern to read — three Saturday evenings vs a
  // Friday morning (best_day Saturday, best_window evening). Saturday 1 Aug
  // 2026 anchors the fixture week; most voice sales here still carry NO lines
  // (the real undercount the inventory card discloses).
  tx('sale', 1360, '2026-08-07T10:30:00+05:00', v(0.93, 'm-0804b'), {
    counterparty: HINA,
    item_lines: [{ item: 'chai patti 950g', qty: 2, unit: 'packet', unit_price: 680, line_total: 1360 }],
  }),
  tx('sale', 1250, '2026-08-07T11:15:00+05:00', v(0.97, 'm-0804'), {
    counterparty: SANA,
    // INVENTORY FIXTURE (labeled): a voice sale WITH item lines — the pipeline
    // can return them; most voice sales in this fixture carry none (the real
    // undercount the inventory card discloses).
    item_lines: [{ item: 'sugar 1kg', qty: 12, unit: 'kg', unit_price: 100, line_total: 1200 }],
  }),
  tx('sale', 1360, '2026-08-08T18:30:00+05:00', v(0.94, 'm-0804c'), {
    counterparty: AHMAD,
    item_lines: [{ item: 'chai patti 950g', qty: 2, unit: 'packet', unit_price: 680, line_total: 1360 }],
  }),
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
  // INSIGHTS FIXTURE (labeled): second-half oil receipt at the LOWER price —
  // with 6/26+7/11 @1250 vs 8/12+8/21 @1020 the price card reads a real
  // median move (down ~18%), two observations per half.
  tx('expense', 1020, '2026-08-12T18:25:00+05:00', o(OCR_VL, 0.9, 'm-0815b'), {
    counterparty: ALMADINA,
    description: 'Oil restock — softer price',
    item_lines: [{ item: 'cooking oil 5L', qty: 1, unit: 'tin', unit_price: 1020, line_total: 1020 }],
  }),
  tx('udhar_given', 3500, '2026-08-15T15:35:00+05:00', v(0.86, 'm-0807'), { counterparty: SANA }),
  tx('sale', 1360, '2026-08-15T18:45:00+05:00', v(0.93, 'm-0807b'), {
    counterparty: SANA,
    item_lines: [{ item: 'chai patti 950g', qty: 2, unit: 'packet', unit_price: 680, line_total: 1360 }],
  }),
  // Price anomaly caught by the Vision Audit sanity check; merchant EDITED it.
  tx('expense', 2800, '2026-08-17T18:55:00+05:00', o(OCR_VL, 0.83, 'm-0808'), {
    description: 'Snacks restock (qty corrected by merchant)',
    item_lines: [{ item: 'bisconni party pack', qty: 4, unit: 'carton', unit_price: 700, line_total: 2800 }],
    flag: 'price_anomaly',
    status: 'edited',
  }),
  tx('sale', 2100, '2026-08-19T12:25:00+05:00', v(0.95, 'm-0809'), { counterparty: AHMAD }),
  tx('udhar_settlement', 2000, '2026-08-20T16:45:00+05:00', v(0.89, 'm-0810'), { counterparty: SANA }),
  tx('sale', 640, '2026-08-20T11:10:00+05:00', v(0.92, 'm-0811'), {
    counterparty: HINA,
    item_lines: [{ item: 'tapal chai 200g', qty: 2, unit: 'packet', unit_price: 320, line_total: 640 }],
  }),
  tx('udhar_given', 1500, '2026-08-21T15:05:00+05:00', v(0.79, 'm-0812'), {
    counterparty: BILAL,
    // INVENTORY FIXTURE (labeled): udhar_given is goods OUT for stock (the
    // goods left the shop on credit) — drives sugar negative in deriveInventory.
    item_lines: [{ item: 'sugar 1kg', qty: 8, unit: 'kg', unit_price: 100, line_total: 800 }],
  }),
  tx('expense', 5400, '2026-08-21T18:30:00+05:00', o(OCR_VL, 0.9, 'm-0813'), {
    counterparty: ALMADINA,
    description: 'Weekly restock — flour, oil',
    item_lines: [
      { item: 'atta 10kg bag', qty: 8, unit: 'bag', unit_price: 420, line_total: 3360 },
      { item: 'cooking oil 5L', qty: 2, unit: 'tin', unit_price: 1020, line_total: 2040 },
    ],
    // §10/§11: the distributor confirmed this purchase via the
    // verify-supplier WhatsApp handshake → the top of the trust ladder.
    trust_tier: 'third_party',
  }),
  // Voice parse too uncertain → pending with a clarification question (schema.md §1:
  // "the pipeline must NOT guess").
  tx('udhar_given', 800, '2026-08-21T16:40:00+05:00', v(0.71, 'm-0814'), {
    counterparty: YUSUF,
    flag: 'low_confidence',
    status: 'pending',
    confirmation_ur: 'آواز صاف نہیں تھی۔ کیا چاچا یوسف کو 800 روپے ادھار دیے؟',
  }),
  // INSIGHTS FIXTURE (labeled): the third Saturday-evening chai sale — the
  // newest entry of the fixture ledger (day 79 of the span).
  tx('sale', 680, '2026-08-22T18:15:00+05:00', v(0.94, 'm-0822'), {
    counterparty: HINA,
    item_lines: [{ item: 'chai patti 950g', qty: 1, unit: 'packet', unit_price: 680, line_total: 680 }],
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
    cur.outstanding_pkd += t.kind === 'udhar_given' ? t.amount_pkr : -t.amount_pkr;
    byCust.set(id, cur);
  }
  return [...byCust.values()]
    .filter((u) => u.outstanding_pkd > 0)
    .sort((a, b) => b.outstanding_pkd - a.outstanding_pkd);
}

/** schema.md §7.3 — savings streak, mirrored 1:1 for the mock path: consecutive
    Mon–Sun PKT weeks with net cash-flow > 0, counted backwards from the current
    week; zero-entry weeks break the streak. Derived from the SAME fixtures the
    ledger renders (an honest computation, not a fabricated number) — with the
    demo scenario's current week net-negative, this yields 0 and the chip simply
    doesn't render. */
export function deriveStreak(items: Transaction[]): SavingsStreak {
  const PKT_OFFSET_MS = 5 * 3_600_000; // PKT = UTC+5
  const WEEK_MS = 7 * 86_400_000;
  /** Monday 00:00 UTC of the week an ISO instant falls in (PKT calendar). */
  const weekKey = (iso: string): number => {
    const pkt = new Date(new Date(iso).getTime() + PKT_OFFSET_MS);
    const day = pkt.getUTCDay(); // 0 = Sunday
    const monday = Date.UTC(pkt.getUTCFullYear(), pkt.getUTCMonth(), pkt.getUTCDate() - ((day + 6) % 7));
    return monday;
  };
  const weeks = new Map<number, { net: number; entries: number }>();
  for (const t of items) {
    if (t.status === 'rejected') continue;
    const k = weekKey(t.occurred_at);
    const w = weeks.get(k) ?? { net: 0, entries: 0 };
    w.net += (t.kind === 'sale' || t.kind === 'udhar_settlement' ? 1 : -1) * t.amount_pkr;
    w.entries += 1;
    weeks.set(k, w);
  }
  const thisWeek = weekKey(new Date().toISOString());
  const current = weeks.get(thisWeek);
  let streak = 0;
  for (let k = thisWeek; ; k -= WEEK_MS) {
    const w = weeks.get(k);
    if (!w || w.entries === 0 || w.net <= 0) break;
    streak += 1;
  }
  const keys = [...weeks.keys()].sort((a, b) => a - b);
  let best = 0;
  let run = 0;
  for (let i = 0; i < keys.length; i++) {
    const w = weeks.get(keys[i])!;
    const positive = w.entries > 0 && w.net > 0;
    if (!positive) {
      run = 0;
      continue;
    }
    run = i > 0 && keys[i] - keys[i - 1] === WEEK_MS ? run + 1 : 1;
    best = Math.max(best, run);
  }
  return {
    streak_weeks: streak,
    best_streak_weeks: best,
    current_week_positive: (current?.net ?? 0) > 0,
  };
}

/** schema.md §11 — mock stand-in for GET /api/merchants/{id}/ledger/verify,
    DERIVED from the same fixtures the ledger renders (server/app/ledger.py
    verify_chain semantics): an entry whose status is 'edited' is exactly a row
    whose current fields differ from the sealed hash (amended after sealing);
    pending rows are the ones without a seal in the demo's insert path.
    Deliberately NOT all-green: the fixture story carries one merchant-edited
    entry so the chip can show its honest framing — amended ≠ hidden, it is
    the audit working, and `original_values` keeps the pre-edit snapshot. */
export function deriveLedgerVerify(items: Transaction[]): LedgerVerifyResult {
  const active = items.filter((t) => t.status !== 'rejected');
  const checked = active.filter((t) => t.entry_hash).length;
  const amended = active.filter((t) => t.status === 'edited').map((t) => t.id);
  const unsealed = active.filter((t) => !t.entry_hash).length;
  return {
    valid: amended.length === 0,
    checked,
    amended_after_sealing: amended,
    unsealed,
    broken_at: null,
    details: amended.map((id) => ({
      tx_id: id,
      problem: 'amended_after_sealing',
      note: 'fixture — the merchant edited this entry after sealing; original_values keeps the pre-edit snapshot',
    })),
  };
}

/* ---- Derived inventory (v0.9 addendum — inventory agent) ----------------------
   Mock stand-in for GET /api/merchants/{id}/inventory, DERIVED from the SAME
   fixtures the ledger renders (server/app/inventory.py semantics, mirrored
   1:1): bought = Σ qty over expense lines, sold = Σ qty over sale + udhar_given
   lines (udhar_settlement is money-only), rejected rows excluded, names merged
   case/whitespace-insensitively (credit_agent._norm_item idea). flag =
   "negative" when sold > bought (a shown data-quality disclosure, §9 spirit),
   "low" when in_stock ≤ max(2, 10% of bought). With these fixtures: sugar 1kg
   lands at in_stock −2 (18 bought vs 20 sold), chai patti 950g at 1 (8 bought
   vs 7 sold — the labeled insights fixtures sell it steadily) and tapal chai
   200g at 0 (low) — so the offline demo shows the disclosure states honestly. */

const INVENTORY_LOW_FLOOR = 2;
const INVENTORY_LOW_SHARE = 0.1;

/** Twin of credit_agent.data_quality._norm_item (NFC → casefold → Urdu-digit
    folding → whitespace collapse → punctuation strip). */
function normItem(name: string): string {
  const folded = (name ?? '').normalize('NFC').toLowerCase().replace(/[۰-۹]/g, (d) =>
    String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)),
  );
  return folded.replace(/\s+/g, ' ').replace(/[^\p{L}\p{N}\s]/gu, '').trim();
}

export function deriveInventory(items: Transaction[]): InventoryView {
  const bought = new Map<string, number>();
  const sold = new Map<string, number>();
  const units = new Map<string, string | null>();
  for (const t of items) {
    if (t.status === 'rejected') continue;
    if (t.kind !== 'expense' && t.kind !== 'sale' && t.kind !== 'udhar_given') continue;
    const bucket = t.kind === 'expense' ? bought : sold;
    for (const line of Array.isArray(t.item_lines) ? t.item_lines : []) {
      const name = normItem(String(line?.item ?? ''));
      const qty = Number(line?.qty ?? 0);
      if (!name || !Number.isFinite(qty) || qty <= 0) continue;
      bucket.set(name, (bucket.get(name) ?? 0) + qty);
      if (!units.has(name)) units.set(name, line?.unit ?? null);
    }
  }
  const severity = { negative: 0, low: 1, ok: 2 } as const;
  const rows: InventoryItem[] = [...new Set([...bought.keys(), ...sold.keys()])].map((name) => {
    const b = bought.get(name) ?? 0;
    const s = sold.get(name) ?? 0;
    const in_stock = Math.round((b - s) * 100) / 100;
    const flag: InventoryItem['flag'] =
      in_stock < 0 ? 'negative' : in_stock <= Math.max(INVENTORY_LOW_FLOOR, INVENTORY_LOW_SHARE * b) ? 'low' : 'ok';
    return { item: name, unit: units.get(name) ?? null, bought: b, sold: s, in_stock, flag };
  });
  rows.sort((a, b) => severity[a.flag] - severity[b.flag] || a.item.localeCompare(b.item));
  return {
    merchant_id: MOCK_MERCHANT.id,
    items: rows,
    note: 'Derived from logged item lines: receipts add stock, sales and udhar remove it. "negative" means more logged sold than bought — usually sales recorded without item lines, shown as a data-quality disclosure, not an accusation.',
  };
}

/* ---- Derived insights (v0.9 addendum — insights agent) ------------------------
   Mock stand-in for GET /api/merchants/{id}/insights, DERIVED from the SAME
   fixtures the ledger renders — a 1:1 mirror of credit_agent.insights
   (qa/reviews/2026-09-07-insights-findings.md §c; no new tables, no
   forecasting, no ML — patterns presented as patterns):

   - demand_timing: sale + udhar_given item_lines bucketed by PKT day-of-week
     and daypart (morning <12, afternoon 12-17, evening >=17) → best day +
     best window + a weekly unit RATE for the top items (≥3 units — below that
     a "best day" is noise).
   - restock_now: CONSUMES deriveInventory above (the SAME flagged rows the
     InventoryCard shows — the stock math is never duplicated here) ranked by
     demand over the trailing 28 days.
   - price_trends: expense item_lines, median unit price first half vs second
     half of the item's observations (≥2 per half), ±1% band reads "flat".

   Empty ledger → exactly three empty lists — the card shows its honest empty
   state, numbers are never invented. */

const INSIGHTS_DEMAND_KINDS: TransactionKind[] = ['sale', 'udhar_given'];
const INSIGHTS_DEMAND_TOP_ITEMS = 5;
const INSIGHTS_DEMAND_MIN_UNITS = 3;
const INSIGHTS_RECENT_DAYS = 28;
const INSIGHTS_RESTOCK_MAX = 8;
const INSIGHTS_PRICE_MIN_OBS = 2;
const INSIGHTS_PRICE_FLAT_PCT = 1;
const INSIGHTS_PRICE_MAX = 6;

const INSIGHT_DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const INSIGHT_PARTS = ['morning', 'afternoon', 'evening'] as const;

const INSIGHTS_PKT_OFFSET_MS = 5 * 3_600_000; // PKT = UTC+5

/** PKT calendar instant of an ISO timestamp (fixtures carry +05:00 offsets;
    naive strings read as UTC — the same convention as the server). */
function pktOf(iso: string): Date {
  const ms = Date.parse(iso);
  return new Date((Number.isNaN(ms) ? 0 : ms) + INSIGHTS_PKT_OFFSET_MS);
}

function insightMedian(xs: number[]): number {
  const ys = [...xs].sort((a, b) => a - b);
  const mid = ys.length >> 1;
  return ys.length % 2 ? ys[mid] : (ys[mid - 1] + ys[mid]) / 2;
}

export function deriveInsights(items: Transaction[]): MerchantInsights {
  const active = items.filter((t) => t.status !== 'rejected');
  if (active.length === 0) {
    return { demand_timing: [], restock_now: [], price_trends: [] };
  }
  const times = active.map((t) => Date.parse(t.occurred_at)).filter((ms) => !Number.isNaN(ms));
  const spanDays = times.length
    ? Math.max(1, Math.round((Math.max(...times) - Math.min(...times)) / 86_400_000) + 1)
    : 0;
  if (spanDays === 0) {
    return { demand_timing: [], restock_now: [], price_trends: [] };
  }
  const note = `Based on your last ${spanDays} days`;

  // --- demand timing -----------------------------------------------------------
  const demand = new Map<string, { dow: Map<number, number>; part: Map<string, number>; units: number }>();
  for (const t of active) {
    if (!INSIGHTS_DEMAND_KINDS.includes(t.kind)) continue;
    const pkt = pktOf(t.occurred_at);
    const dow = (pkt.getUTCDay() + 6) % 7; // Monday-first
    const hour = pkt.getUTCHours();
    const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
    for (const line of Array.isArray(t.item_lines) ? t.item_lines : []) {
      const name = normItem(String(line?.item ?? ''));
      const qty = Number(line?.qty ?? 0);
      if (!name || !Number.isFinite(qty) || qty <= 0) continue;
      const rec = demand.get(name) ?? { dow: new Map(), part: new Map(), units: 0 };
      rec.dow.set(dow, (rec.dow.get(dow) ?? 0) + qty);
      rec.part.set(part, (rec.part.get(part) ?? 0) + qty);
      rec.units += qty;
      demand.set(name, rec);
    }
  }
  const demand_timing: DemandTimingRow[] = [...demand.entries()]
    .sort((a, b) => b[1].units - a[1].units || a[0].localeCompare(b[0]))
    .slice(0, INSIGHTS_DEMAND_TOP_ITEMS)
    .filter(([, rec]) => rec.units >= INSIGHTS_DEMAND_MIN_UNITS)
    .map(([name, rec]) => {
      const bestDow = [...rec.dow.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
      const bestPart = [...rec.part.entries()].sort(
        (a, b) =>
          b[1] - a[1] ||
          INSIGHT_PARTS.indexOf(a[0] as (typeof INSIGHT_PARTS)[number]) -
            INSIGHT_PARTS.indexOf(b[0] as (typeof INSIGHT_PARTS)[number]),
      )[0][0];
      return {
        item: name,
        best_day: INSIGHT_DAY_NAMES[bestDow],
        best_window: bestPart as DemandTimingRow['best_window'],
        weekly_units: Math.round(((rec.units * 7) / spanDays) * 10) / 10,
        note,
      };
    });

  // --- restock (consumes deriveInventory — no duplicated stock math) -----------
  const maxMs = Math.max(...times);
  const cutoff = maxMs - INSIGHTS_RECENT_DAYS * 86_400_000;
  const recent = new Map<string, number>();
  for (const t of active) {
    if (!INSIGHTS_DEMAND_KINDS.includes(t.kind)) continue;
    const ms = Date.parse(t.occurred_at);
    if (Number.isNaN(ms) || ms < cutoff) continue;
    for (const line of Array.isArray(t.item_lines) ? t.item_lines : []) {
      const name = normItem(String(line?.item ?? ''));
      const qty = Number(line?.qty ?? 0);
      if (!name || !Number.isFinite(qty) || qty <= 0) continue;
      recent.set(name, (recent.get(name) ?? 0) + qty);
    }
  }
  const weeks = Math.max(1, Math.min(INSIGHTS_RECENT_DAYS, spanDays) / 7);
  const severity: Record<string, number> = { negative: 0, low: 1 };
  const restock_now: RestockRow[] = deriveInventory(items).items
    .filter((it) => it.flag === 'low' || it.flag === 'negative')
    .map((it) => ({
      item: it.item,
      unit: it.unit,
      in_stock: it.in_stock,
      flag: it.flag,
      weekly_demand: Math.round(((recent.get(it.item) ?? 0) / weeks) * 10) / 10,
      note,
    }))
    .sort((a, b) => b.weekly_demand - a.weekly_demand || severity[a.flag] - severity[b.flag] || a.item.localeCompare(b.item))
    .slice(0, INSIGHTS_RESTOCK_MAX);

  // --- price trends --------------------------------------------------------------
  const obs = new Map<string, { when: number; price: number; unit: string | null }[]>();
  for (const t of active) {
    if (t.kind !== 'expense') continue;
    const ms = Date.parse(t.occurred_at);
    if (Number.isNaN(ms)) continue;
    for (const line of Array.isArray(t.item_lines) ? t.item_lines : []) {
      const name = normItem(String(line?.item ?? ''));
      const price = Number(line?.unit_price ?? 0);
      if (!name || !Number.isFinite(price) || price <= 0) continue;
      const list = obs.get(name) ?? [];
      list.push({ when: ms, price, unit: line?.unit ?? null });
      obs.set(name, list);
    }
  }
  const price_trends: PriceTrendRow[] = [...obs.entries()]
    .map(([name, points]) => {
      points.sort((a, b) => a.when - b.when);
      const half = points.length >> 1;
      const first = points.slice(0, half).map((p) => p.price);
      const second = points.slice(half).map((p) => p.price);
      if (first.length < INSIGHTS_PRICE_MIN_OBS || second.length < INSIGHTS_PRICE_MIN_OBS) return null;
      const m1 = insightMedian(first);
      const m2 = insightMedian(second);
      if (!(m1 > 0)) return null;
      const pct = Math.round(((m2 - m1) / m1) * 1000) / 10;
      const direction: PriceTrendRow['direction'] =
        pct >= INSIGHTS_PRICE_FLAT_PCT ? 'up' : pct <= -INSIGHTS_PRICE_FLAT_PCT ? 'down' : 'flat';
      return {
        item: name,
        unit: points[0].unit,
        first_median: Math.round(m1 * 100) / 100,
        second_median: Math.round(m2 * 100) / 100,
        pct_change: pct,
        direction,
        note,
      };
    })
    .filter((r): r is PriceTrendRow => r !== null)
    .sort((a, b) => Math.abs(b.pct_change) - Math.abs(a.pct_change) || a.item.localeCompare(b.item))
    .slice(0, INSIGHTS_PRICE_MAX);

  return { demand_timing, restock_now, price_trends };
}

/* ---- Credit Readiness preview (DRAFT shape — see types/schema.ts header) -----
   Derived transparently from the mock transactions. The real endpoint runs
   whatever MODEL_REASONING the server config points at (schema.md §4 GET
   /api/merchants/{id}/report/preview) — a free-tier demo model today, Qwen
   on Alibaba Cloud Model Studio as the production path; the scoring
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
        by_source: { voice: { entries: 0, avg_confidence: null }, photo: { entries: 0, avg_confidence: null }, text: { entries: 0, avg_confidence: null }, manual: { entries: 0, avg_confidence: null } },
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
      .reduce((s, t) => s + t.amount_pkr, 0);
    const outflow = rows
      .filter((t) => t.kind === 'expense' || t.kind === 'udhar_given')
      .reduce((s, t) => s + t.amount_pkr, 0);
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

  const bySource = (type: SourceType) => {
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
        t.amount_pkr >= 5000 ||
        t.kind === 'udhar_settlement',
    )
    .slice(-14)
    .map((t) => ({
      transaction_id: t.id,
      label: lineLabel(t),
      label_ur: lineLabelUr(t),
      month: monthKey(t.occurred_at),
      amount_pkr: t.amount_pkr,
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
    model: null, // mock — the live preview names the reasoning model actually used
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
      by_source: { voice: bySource('voice'), photo: bySource('photo'), text: bySource('text'), manual: bySource('manual') },
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
