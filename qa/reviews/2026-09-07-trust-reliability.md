# Trust-Reliability Sweep — final pre-demo pass (2026-09-07 22:48 PKT)

Scope: dashboard/src (all screens/components/api/lib/types), the demo path
`credit-agent/scripts/seed_demo.py` → `server.app.main:app` on :8010 → dashboard
screens, against REAL seeded payloads (Al-Madina Kiryana Store 96/ready, Bilal Ki
Dukan 73/nearly; 174 + 23 sealed transactions). Every finding below was reproduced
against the live server, not fixtures. Findings already fixed in Phase 2 are marked
[FIXED]; the rest are documented with the smallest safe fix sketched.

Method: fresh `BIZRO_OFFLINE=1 python credit-agent/scripts/seed_demo.py` (no argv,
default `sqlite:///./bizro.db`), rerun without deleting (idempotency probe), uvicorn
on :8010, curl of every endpoint the screens consume (/api/merchants, transactions,
udhar, report/preview, inventory, streak, ledger/verify, report/history, settings,
outbound, media/{id}), numeric cross-checks derived in Python from those payloads.

---

## P0 — demo-breaking

- [P0][FIXED] `credit-agent/scripts/seed_demo.py:106,108` — seed is NOT idempotent and the
  report step reads a DIFFERENT database than the one it seeds.
  Evidence: 2nd run without deleting the DB crashes `sqlite3.IntegrityError: UNIQUE
  constraint failed: merchants.wa_id` (server/app/db.py:54 declares `wa_id` unique;
  the seeder inserts fixed wa_ids `923009999888`/`923009111222` under a fresh UUID).
  Separately, `generate_report(mid, period="last_90_days")` is called WITHOUT
  `db_url`, so it resolves `DATABASE_URL`/`sqlite:///./bizro.db` on its own — an
  explicit argv DB (or a divergent env var) seeds one file and scores another
  (reproduced: `no such table: merchants`). On demo morning, "run the seed twice to
  be safe" kills the demo.
  Fix: in scripts/seed_demo.py (only), look up an existing merchant by
  display_name and reuse it (skip reseed + skip duplicate history rows), and pass
  `db_url=db` to generate_report. Verified: two consecutive runs, then a third —
  exit 0, same merchant ids, one set of trend rows.

## P1 — wrong / contradictory user-visible results on the demo path

- [P1][FIXED] `dashboard/src/api/reportAdapter.ts:38-69` — the canonical→screen adapter
  DROPS the credit-agent's entire trust block: `trust`, `officer`, `limitations`
  are never copied onto the adapted report. Evidence: live payload carries
  `trust.corroboration_pct=14.3`, `officer.aging={buckets:[...],
  total_outstanding:100378.03}`, `officer.collection.rate=0.491`,
  `officer.concentration={top_share:81.8, warn:true}`,
  `officer.activity.weeks=[...]`, `limitations=[4 strings]` — but
  `adaptCanonicalReport` returns none of them, so on /credit the whole OfficerPack
  section hides (`officerPackHasContent` sees nothing), the corroboration headline
  never renders, and on /officer the "Avg corroboration" strip shows "Not in these
  reports yet" and /committee loses Corroboration 14%, Collection rate 49%, the
  aging bars and the payload's own Limitations. The flagship v0.7 trust evidence is
  invisible on the live demo path (it renders only for hand-built gallery
  fixtures). Fix: map `trust`/`limitations` verbatim and normalize the canonical
  officer object shapes (`aging.buckets[].total→amount_pkr`, `customers.length→count`,
  `collection.rate→collection_rate`, `concentration.top_share→
  top_debtor_concentration_pct`, `activity.weeks[].count→weekly_activity[].entries`)
  onto the screen block the renderers already accept.

- [P1][FIXED] `dashboard/src/components/UdharRadar.tsx:29` vs
  `dashboard/src/components/OfficerReviewScreen.tsx:252` /
  `dashboard/src/screens/CommitteePrintScreen.tsx:92` — two different "outstanding
  udhar" numbers for the same merchant on the same walk. Evidence (live): the
  server's /udhar lists 9 customers including 5 with NEGATIVE balances (over-
  settled credit), `total_outstanding_pkd=71148.89` (net); the radar sums all rows
  → Rs 71,148.89. The officer card and committee pack derive positives-only via
  `deriveUdhar` (`.filter(outstanding_pkd > 0)`) → Rs 100,378.03, which is ALSO
  what the report's own `officer.aging.total_outstanding` and its
  `collection.note_en` ("PKR 100,378 outstanding") state. Ledger radar: Rs 71,149 —
  report + officer + committee: Rs 100,378. Fix (dashboard-side, server untouched):
  radar total = Σ max(outstanding, 0) — "who owes you" is the sum of customers who
  actually owe; overpaid credit balances are not displayed anywhere as a number, so
  no second figure remains on screen. Verified: all four surfaces now say
  Rs 100,378.

- [P1][FIXED] `dashboard/src/components/AuditTrail.tsx:42-51,133` — the demo-row audit
  panel contradicts itself. Evidence: for every seeded row (all 174 are
  `source.raw_output.mock=true`) the panel prints "Demo entry — Seeded example
  data — no voice note, photo, or model call is behind this row", then
  unconditionally renders `<SourceMedia>`, which (api.mock=false on the live
  server) fetches GET /api/media/{id} and displays "Original voice note" with a
  working audio player / "Original receipt photo" with a thumbnail — the seed DID
  write real blob bytes (reproduced: GET /api/media/37425e98… → 200 audio/wav,
  4,844 bytes). A judge expanding any ledger row sees both claims at once. Fix:
  skip SourceMedia for demo rows and state the seeded-media fact in the Source
  line ("seeded example — generated demo media only"), keeping the existing honest
  note for real rows.

- [P1][FIXED] `dashboard/src/screens/CreditReadinessScreen.tsx:447-477` — the AI-sourcing
  card claims "100% of entries AI-parsed & confirmed · avg confidence 92% across
  174/174 entries" directly above "Sourced line items" where EVERY line carries the
  dashed "demo — no model ran" chip. Evidence: derived sourcing is computed
  client-side from loaded rows with no demo-markedness check; on the seeded path
  every row is `mock:true`, so the headline asserts parses that the same screen
  says never happened. Fix: when every loaded non-rejected row is demo-marked, the
  card shows the ledger's honest line ("Demo data — seeded example entries. Not
  stamped from real voice notes or photos.") instead of the sourcing claim; mixed
  ledgers keep the numbers plus an "(includes seeded demo entries)" qualifier.

## P2 — real but safe to ship; smallest safe fix sketched, left as roadmap

- [P2] credit-agent provenance buckets vs dashboard sourcing card: the canonical
  payload counts the 25 `text` (typed WhatsApp) entries under `manual_pct`
  (voice 78.0 + photo 7.5 + manual 14.5 = 100), while the dashboard counts text as
  AI-sourced ("Typed notes 25", "100% AI-parsed"). The printed HTML report and the
  screen disagree for a judge reading both. Smallest safe fix: rename the bucket in
  the printed provenance ("typed/manual") or align credit_agent provenance to the
  §11 source taxonomy — credit-agent territory, not touched here.
- [P2] `CreditReadinessScreen.tsx:265-274` — one-day PKT/UTC seam: the report's
  canonical `period.end` is UTC-derived (2026-10-23) while its own `end_display`
  says Oct 24; the coverage-vs-score comparison then appends "The score uses Jul 26,
  2026 - Oct 23, 2026" for a one-day difference — honest but noisy on demo day.
  Smallest safe fix: prefer canonical `period.start_display/end_display` for
  `scoredRangeLabel` when present.
- [P2] `MonthlyLedgerScreen.tsx:337-339` — "% of entries stamped from voice or
  photos" counts typed WhatsApp notes (non-manual share); the label overstates the
  medium. Copy-only fix: "stamped automatically (voice, photos, chats)".
- [P2] `CreditReadinessScreen.tsx:455` — "AI-parsed & confirmed" ignores the 2
  pending rows (they are parsed, not confirmed). Copy-only fix: "AI-parsed (2
  awaiting confirmation)". On the demo path this line is replaced by the P1 fix
  above anyway.
- [P2] Inventory on the demo path: seeded transactions carry NO item_lines, so
  GET /inventory returns `items: []` and the Stock-on-hand card renders its
  empty-state under the Udhar Radar despite 174 entries. Honest, but a wasted hero
  card. Roadmap: seed a few item_lines (credit-agent/seed.py, not touched here).
- [P2] `client.ts:296` (fetchReportHistory) — history `generated_at` values are
  naive ISO (no timezone); `new Date()` parses them as local time. Correct in PKT
  demo machines, fragile elsewhere. Roadmap: server should emit offsets.

## ROADMAP

- `OfficerPack.tsx:27 (toPct)` — the `v <= 1 → ×100` heuristic misreads a literal
  `1` (1% intended, read as 100%). Demo payloads avoid the edge (14.3, 0.491, 0.0,
  81.8); a `0 <= v <= 1` documented convention or an explicit `_pct`-only contract
  would remove the ambiguity.
- Officer cards derive weekly activity client-side (PKT-Monday weeks) while the
  credit-agent's `activity.weeks` are seeded-now-anchored 7-day buckets — the two
  bar sets can differ slightly in shape. Both honest; unify on the server weeks
  when the officer pack lands fully.
- `MonthlyLedgerScreen` opens on the UTC month (`monthOf(new Date().toISOString())`);
  near month boundaries in PKT the ledger can open one day behind. Demo runs at
  22:00+ PKT land safely inside the month.

## Security-visible checks (priority 3) — PASS

- Webhook survives garbage: POST /webhook/whatsapp `{"not":"a whatsapp payload"}` →
  200 `{"processed":0,"results":[]}` — no 500, no stack trace a judge could see.
- Bad ids clean: POST /api/transactions/nonexistent/confirm → 400 "invalid
  transaction id (not a UUID)".
- Mock-mode banner behavior: with the server DOWN the app flips to labeled fixtures
  ("Live server unreachable — showing clearly-labeled demo data"); with the live
  seeded server up, `api.mock=false` and NO false mock banner appears — the ledger
  instead shows the seeded-data disclosure ("Demo data — seeded example entries")
  driven by the rows' `raw_output.mock` marker (all 174 rows carry it; the
  security-merge persistence fix is visible end-to-end).
- Server log during the full walk: zero errors/tracebacks.
- Printed artifacts (credit_report_demo.html / credit_report_committee.html) carry
  the red "MOCK DATA — synthesized without live model calls" banner.

## Reliability checks (priority 2) — PASS (after the P0 fix)

- Every optional endpoint absent/failing degrades to nothing: streak, inventory,
  ledger/verify, report/history all 404-safe client-side (null → chip/card/sparkline
  hidden); verified the real payloads render them: streak "10 week streak",
  verify "Chain intact · 174 sealed", history sparkline 58→77→96.
- GET /api/media/{id} 200 audio/wav for seeded blobs; outbound (simulator) 200;
  settings 200 defaults.
- Integrity chip, trust-tier badges, corroboration (after fix), committee
  integrity line all render against REAL server payloads, not fixtures.

## Per-screen verdict (live seeded data, post-fix)

- /ledger — PASS. Hero (Oct: in Rs 66,774.88 / out Rs 31,873.57 / net kept), split
  cells, Udhar Radar (top-3 Rahmat/Nasir/Sana, total now consistent at Rs 100,378),
  integrity chip "Chain intact · 174 sealed", streak chip, demo disclosure line,
  demo chips on rows. Stock card honestly empty (P2 note).
- /credit — PASS after fixes. Verdict 96 "Loan-ready", gauge + rising sparkline,
  coverage sentence (4 months), cash-flow bars + print table, flags with refs,
  OfficerPack now renders (Corroboration 14%, collection 49%, concentration 82%
  HIGH with the warning line, aging bars, weekly bars), line items honest
  ("demo — no model ran"), sourcing card no longer contradicts them, demo footer.
- /officer — PASS after fixes. Both applicants, per-card corroboration (14% / 0%),
  entries, red flags (2 / 3), udhar out (now agreeing with the report), 8-week
  activity bars, visit checklist, "Demo fixtures" banner.
- /committee/:id — PASS after fixes. Corroboration line, integrity statement
  ("174 entries hash-sealed, chain intact… Tamper-evident, not tamper-proof"),
  top metrics (now incl. Collection rate 49% + Udhar outstanding consistent),
  aging bars + weekly bars render, limitations from the payload, "Demo fixture —
  no real merchant" stamp.
- /simulator — PASS (endpoints verified: webhook POST, outbound poll, media,
  tts optional). Not live-fired end-to-end here (would consume AI budget); error
  paths verified (garbage webhook graceful, per-cause failure copy in code).
- /settings — PASS (account card, English-only per owner directive).
- /dev/components — dev-only, unlinked (not re-audited).
