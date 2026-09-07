# INSIGHTS FINDINGS — demand timing / restock / price movers (phase 1, before code)

Scope ruling (demo tomorrow): all three insights are **DERIVED from existing
data** — `item_lines` + `occurred_at` + `unit_price` only. Zero new tables,
zero migrations, no forecasting claims, no ML. Patterns are presented AS
patterns ("Based on your last N days"), never predictions. Agent: insights
agent, branch `agent4/insights`, worktree `.worktrees4/insights`.

## (a) Reliable item_lines fields (what the code can actually count on)

- **Store**: `server/app/db.py:161` — `item_lines: Mapped[list | None] =
  mapped_column(JSONVariant)`; mirror twin `credit-agent/credit_agent/db_view.py:62`.
  Nullable, untyped contents → reads must be defensive.
- **Wire shape** (`server/app/schemas.py:38-45`, `ItemLine`): `item: str`
  (the ONLY guaranteed field), `qty/unit/unit_price/line_total` all optional
  (default None). Canonical example `server/schema.md §1`:
  `{"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700}`.
- **Who writes them**: `server/app/dispatch.py:510` persists
  `item_lines=[line.model_dump() for line in parsed.item_lines]` — BOTH the
  voice path and the OCR path can carry lines; the §4/§6.5 contract is
  "`item_lines` present for OCR-parsed expenses; often not on voice sales"
  (server/app/INVENTORY_FINDINGS.md §d-2 — goods-OUT is systematically
  undercounted; accepted, disclosed via the shared note).
- **The demo seeder writes NO item_lines** — `credit-agent/credit_agent/seed.py:156-173`
  (`add_tx` → `Transaction(...)`) passes none; expenses only carry a
  description like `"supplier: {item} {qty} {unit}"` (seed.py:262). Consequence
  (verified, not assumed): a freshly seeded demo DB yields EMPTY insight lists —
  the honest "Not enough history yet" state. The dashboard card therefore ships
  labeled mock fixtures (same pattern as `deriveInventory`, mockData.ts:396) so
  the feature is demoable offline, and live flows (dispatch persist path) feed
  the real endpoint. Tests seed explicit deterministic item_lines — they must
  not depend on seed.py's RNG profile for line data.
- **Read guards** (copied contract from `data_quality.py:46-48` +
  `inventory.py:100-114`): `isinstance(item_lines, list)`; per line
  `isinstance(line, dict)`; `str(line.get("item"))` normalized; `qty` and
  `unit_price` via `float()` inside try/except (TypeError/ValueError → skip);
  qty ≤ 0 or price ≤ 0 → skip; `status == "rejected"` rows excluded
  (`data_quality.py:58`, udhar-radar convention).

## (b) Normalization rule (reused, not duplicated)

`credit-agent/credit_agent/data_quality.py:39-43` `_norm_item`:

    NFC normalize → casefold → Urdu digits ۰-۹ → ASCII → collapse whitespace
    → strip punctuation [^\w\s] → strip

`server/app/inventory.py:46-74` already lazy-imports exactly this (tolerant
fallback twin if the package is missing) — insights reuses `_norm_item` the
same way: demand timing, restock ranking and price trends all key items off the
SAME normalized names the inventory endpoint reports, so the cards can never
disagree about what an item is. Deliberately NO fuzzy matching: "atta 10kg" vs
"atta 20kg" stay separate (merging pack sizes would corrupt quantities —
INVENTORY_FINDINGS.md §c).

## (c) Exact metric definitions

Common window: the transactions handed in (endpoint: last 90 days by
`occurred_at`; report: its own period). `span_days = (max occurred − min
occurred).days + 1` over the non-rejected txs used. Dayparts and day-of-week
come from `occurred_at` converted to PKT (UTC+5; SQLite rows are naive-UTC —
dispatch.py:255-264 normalizes to UTC before storage, aggregates.py:46 treats
naive as UTC — so naive input is read as UTC then shifted +5).

### 1. demand_timing — "when your items sell"

Per item over `sale` + `udhar_given` item_lines (goods OUT — schema.md §1):
- `units` = Σ `qty` per normalized item; day-of-week buckets from PKT weekday;
  daypart buckets: morning `hour < 12`, afternoon `12 ≤ hour < 17`, evening
  `hour ≥ 17` (PKT hour).
- Top `DEMAND_TOP_ITEMS = 5` items by total units, then only items with
  `units ≥ DEMAND_MIN_UNITS = 3` (below that a "best day" is noise, not a
  pattern).
- `best_day` = day-of-week with max units (tie → earliest weekday);
  `best_window` = daypart with max units (tie → morning < afternoon < evening).
- `weekly_units` = round(units × 7 / span_days, 1) — an average rate, NOT a
  forecast.
- Row shape: `{"item", "best_day", "best_window", "weekly_units", "note"}`;
  `note = f"Based on your last {span_days} days"` (spec example: chai patti /
  Saturday / evening / 34).

### 2. restock_now — "what to buy" (CONSUMES inventory math, zero duplication)

- Stock levels come straight from
  `server/app/inventory.py::compute_inventory` (imported — lazily, with the
  same tolerance pattern inventory.py:46-60 uses for `_norm_item`; if the
  server package is unreachable the list degrades to `[]`, never a 500). The
  bought/sold/flag arithmetic is NEVER reimplemented here.
- Items with `flag in ("low", "negative")` are ranked by **recent weekly
  demand**: units over the most recent `RECENT_DAYS = 28` days of the window
  (sale + udhar_given lines, same normalization) ÷ weeks covered
  (min(28, span_days)/7), rounded to 1; items with no recent lines rank last
  with `weekly_demand = 0`. Tie order: demand desc → negative before low →
  name.
- Row shape: `{"item", "unit", "in_stock", "flag", "weekly_demand", "note"}`
  (spec-required four: item/in_stock/weekly_demand/note). Cap 8 rows.

### 3. price_trends — "what your costs are doing"

Per item over `expense` item_lines only (supplier receipts — the lines that
reliably carry `unit_price`):
- An observation = one line with a usable `unit_price > 0` and its tx's
  `occurred_at`.
- Period split at the midpoint timestamp of that item's own observations:
  first half vs second half medians. Require ≥ `PRICE_MIN_OBS = 2` observations
  in EACH half (a single receipt flip is noise, not a trend).
- `pct_change = round((median_second − median_first) / median_first × 100, 1)`;
  `direction` = "up" (≥ +1%), "down" (≤ −1%), else "flat" (within ±1% = no
  signal worth printing). Sort by |pct_change| desc; cap 6 rows.
- Row shape: `{"item", "unit", "first_median", "second_median", "pct_change",
  "direction", "note"}` (spec example renders as "up 8%").
- Median = plain sorted-list median (even count → mean of middle two). No
  vision-agent import; no numpy.

## (d) Where the outputs land

- `report_json["insights"] = {"demand_timing": [...], "restock_now": [...],
  "price_trends": [...]}` — added in `generate_report`
  (credit-agent/credit_agent/report.py) immediately BEFORE the
  `row = CreditReport(...)` persistence (report.py:214) so it rides every
  persisted report; empty ledger → exactly the three empty lists, never
  invented.
- `GET /api/merchants/{merchant_id}/insights` appended at the FOOT of
  `server/app/api.py` (after the inventory endpoint, api.py:1199-1203),
  following its pattern: `db_session()` + `_get_merchant` → 400/404, `me`
  sentinel resolves; 90-day tx query + `compute_inventory` + lazy
  `credit_agent.insights.compute_insights` (missing package → honest empty
  lists, same tolerance as inventory.py's norm-item fallback).
- Dashboard: `InsightsCard` on the ledger screen — restock FIRST (the action),
  then demand timing, then price movers; icon+word signals (§4.7), Khata
  Modern tokens, rule-lines not shadows; empty state "Not enough history yet —
  keep sending voice notes and receipts"; labeled mock fixtures via the
  client's optional-endpoint pattern (absence → card hidden, never an error).

## (e) Risks / honest limits

1. **Item-line sparsity** (§a): voice sales usually have no lines → demand
   timing reads OCR'd expenses + the minority of voice sales that do carry
   lines. The card says "based on your last N days", never "your peak hours".
2. **Mixed units per item name** (first-seen unit wins — inventory.py:112-114
   convention) — an approximation, carried in the shared note.
3. **PKT day edges**: 19:00-23:59 UTC entries become the NEXT PKT day —
   intentional (the merchant's local day is the truth), deterministic.
4. **Price medians from OCR prices** — a misread receipt (price_anomaly flags
   exist, seed.py:251-262) can skew one observation; medians (not means) keep
   single outliers from dominating.
